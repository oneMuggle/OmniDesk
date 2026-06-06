"""SP2: ScheduleSwapRequest API 集成测试(RED 阶段)

覆盖:
- 5 个 Serializer 字段白名单
- ViewSet 5 action(accept/reject/approve/cancel/standard list/retrieve/create)
- 三层防护(L1 序列化器 + L2 ViewSet + L3 Model.clean)
- MyScheduleView 自助查询
- 行级权限三视角
"""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from events.models import Schedule, ScheduleSwapRequest
from personnel.models import Personnel


# ---- helpers ----


def _link(user, personnel):
    user.personnel = personnel
    user.save()


def _setup_duty_pair(duty_date, person_a, person_b=None):
    a = Schedule.objects.create(duty_date=duty_date, duty_person=person_a)
    b = None
    if person_b is not None:
        b = Schedule.objects.create(
            duty_date=duty_date + datetime.timedelta(days=1), duty_person=person_b
        )
    return a, b


LIST_URL = "/api/events/swap-requests/"


def _detail_url(pk):
    return f"/api/events/swap-requests/{pk}/"


def _action_url(pk, action):
    return f"/api/events/swap-requests/{pk}/{action}/"


ME_SCHEDULE_URL = "/api/events/me/schedule/?days=60"


# ---- fixtures ----


@pytest.fixture
def duty_date():
    return (timezone.now() + datetime.timedelta(days=7)).date()


@pytest.fixture
def person_a(regular_user_obj):
    p = Personnel.objects.create(name=regular_user_obj.username)
    _link(regular_user_obj, p)
    return p


@pytest.fixture
def person_b(db):
    return Personnel.objects.create(name="李四")


@pytest.fixture
def person_c(db):
    return Personnel.objects.create(name="王五")


@pytest.fixture
def schedule_a(regular_user_obj, person_a, duty_date, db):
    return Schedule.objects.create(duty_date=duty_date, duty_person=person_a)


# ---- 三层防护 + 创建 ----


@pytest.mark.django_db
class TestCreateSerializerL1:
    def test_l1_serializer_rejects_unexposed_fields(self, regular_client, person_a, person_b, schedule_a):
        """L1:request 包含 client-controlled 'status' / 'requester' / 'expires_at' 应被忽略。"""
        data = {
            "original_schedule": schedule_a.id,
            "target_personnel": person_b.id,
            "reason": "出差",
            "status": "approved",  # 客户端不能传
            "requester": person_a.id,  # 客户端不能传
            "expires_at": "2030-01-01T00:00:00Z",  # 客户端不能传
        }
        response = regular_client.post(LIST_URL, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED, f"status={response.status_code} body={response.content!r}"
        swap = ScheduleSwapRequest.objects.get(pk=response.data["id"])
        assert swap.status == "pending"  # L1 拒了客户端的"approved"
        assert swap.requester_id == person_a.id  # L2 注入当前 user.personnel

    def test_l2_viewset_injects_requester_from_session(self, regular_client, person_a, person_b, schedule_a):
        """L2:requester 强制从 request.user.personnel 取。"""
        data = {
            "original_schedule": schedule_a.id,
            "target_personnel": person_b.id,
            "reason": "生病",
        }
        response = regular_client.post(LIST_URL, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        swap = ScheduleSwapRequest.objects.get(pk=response.data["id"])
        assert swap.requester_id == person_a.id
        from django.conf import settings
        expected_ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        assert (swap.expires_at - timezone.now()) < datetime.timedelta(hours=expected_ttl + 1)

    def test_l3_model_clean_rejects_self_swap(self, regular_client, person_a, schedule_a):
        """L3:自换 → 400 with field error。"""
        data = {
            "original_schedule": schedule_a.id,
            "target_personnel": person_a.id,  # 自换
            "reason": "测试",
        }
        response = regular_client.post(LIST_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "target_personnel" in response.data

    def test_l3_model_clean_rejects_non_duty_requester(
        self, regular_user_obj, regular_client, person_a, person_b, person_c, schedule_a
    ):
        """L3:路人丙不能发起他人的换班 → 400。"""
        _link(regular_user_obj, person_c)  # 切换关联到路人丙
        data = {
            "original_schedule": schedule_a.id,
            "target_personnel": person_b.id,
            "reason": "无权限",
        }
        response = regular_client.post(LIST_URL, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "requester" in response.data


# ---- 状态机 action 端到端 ----


@pytest.mark.django_db
class TestAcceptActionE2E:
    def test_target_accepts_creates_applied_swap(self, person_a, person_b, schedule_a):
        """决策 1C:接收方 accept → status=approved,Schedule.duty_person 改为 target。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        a_client.post(
            LIST_URL,
            {
                "original_schedule": schedule_a.id,
                "target_personnel": person_b.id,
                "reason": "测试",
            },
            format="json",
        )
        swap = ScheduleSwapRequest.objects.get(original_schedule=schedule_a)

        b_user = User.objects.create_user(username="b_user_temp", password="x")
        b_user.personnel = person_b
        b_user.save()
        b_client = APIClient()
        b_client.force_authenticate(user=b_user)

        response = b_client.post(_action_url(swap.pk, "accept"), format="json")
        assert response.status_code == status.HTTP_200_OK, response.content
        swap.refresh_from_db()
        schedule_a.refresh_from_db()
        assert swap.status == "approved"  # 决策 1C
        assert schedule_a.duty_person_id == person_b.id  # 已换班

    def test_target_rejects_no_schedule_change(self, person_a, person_b, schedule_a):
        """接收方 reject → status=rejected_by_target,Schedule 不变。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        a_client.post(
            LIST_URL,
            {
                "original_schedule": schedule_a.id,
                "target_personnel": person_b.id,
                "reason": "测试",
            },
            format="json",
        )
        swap = ScheduleSwapRequest.objects.get(original_schedule=schedule_a)

        b_user = User.objects.create_user(username="b_rej", password="x")
        b_user.personnel = person_b
        b_user.save()
        b_client = APIClient()
        b_client.force_authenticate(user=b_user)

        response = b_client.post(_action_url(swap.pk, "reject"), format="json")
        assert response.status_code == status.HTTP_200_OK
        swap.refresh_from_db()
        schedule_a.refresh_from_db()
        assert swap.status == "rejected_by_target"
        assert schedule_a.duty_person_id == person_a.id  # 未换

    def test_requester_cancels_pending(self, person_a, person_b, schedule_a):
        """申请方 cancel → status=cancelled。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        a_client.post(
            LIST_URL,
            {
                "original_schedule": schedule_a.id,
                "target_personnel": person_b.id,
                "reason": "测试",
            },
            format="json",
        )
        swap = ScheduleSwapRequest.objects.get(original_schedule=schedule_a)

        response = a_client.post(_action_url(swap.pk, "cancel"), format="json")
        assert response.status_code == status.HTTP_200_OK
        swap.refresh_from_db()
        assert swap.status == "cancelled"


@pytest.mark.django_db
class TestRowLevelPermission:
    def test_requester_sees_own_in_default_list(self, person_a, person_b, schedule_a):
        """默认 list 返回与当前 user 相关的所有申请。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        a_client.post(
            LIST_URL,
            {
                "original_schedule": schedule_a.id,
                "target_personnel": person_b.id,
                "reason": "测试",
            },
            format="json",
        )
        response = a_client.get(LIST_URL)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_target_sees_in_target_filter(self, person_a, person_b, schedule_a):
        """target 视角过滤:用 ?role=target 查询。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        a_client.post(
            LIST_URL,
            {
                "original_schedule": schedule_a.id,
                "target_personnel": person_b.id,
                "reason": "测试",
            },
            format="json",
        )

        b_user = User.objects.create_user(username="b_t", password="x")
        b_user.personnel = person_b
        b_user.save()
        b_client = APIClient()
        b_client.force_authenticate(user=b_user)
        response = b_client.get(LIST_URL + "?role=target")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) >= 1

    def test_requester_cannot_cancel_other_request(self, person_a, person_b, schedule_a):
        """申请方不能 cancel 他人的申请(行级权限)。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        a_user = User.objects.get(personnel=person_a)
        a_client = APIClient()
        a_client.force_authenticate(user=a_user)
        # 创建一个不属于当前 user 的申请
        other = ScheduleSwapRequest.objects.create(
            requester=person_b,
            original_schedule=schedule_a,
            target_personnel=person_a,
            reason="他发起的",
            expires_at=timezone.now() + datetime.timedelta(hours=48),
        )
        response = a_client.post(_action_url(other.pk, "cancel"), format="json")
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# ---- MyScheduleView 自助端点 ----


@pytest.mark.django_db
class TestMyScheduleEndpoint:
    def test_returns_future_duties(self, regular_user_obj, person_a, duty_date):
        """MyScheduleView 返回当前 user 作为 duty_person 的未来排班。"""
        from datetime import timedelta

        _link(regular_user_obj, person_a)
        s_past = Schedule.objects.create(
            duty_date=timezone.now().date() - timedelta(days=3),
            duty_person=person_a,
        )
        s_future = Schedule.objects.create(duty_date=duty_date, duty_person=person_a)
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        u = User.objects.get(personnel=person_a)
        c = APIClient()
        c.force_authenticate(user=u)
        response = c.get(ME_SCHEDULE_URL)
        assert response.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in response.data]
        assert s_future.id in ids
        assert s_past.id not in ids

    def test_returns_empty_if_no_personnel(self, regular_user_obj):
        """user 无 personnel 关联 → 返回空列表(非 404)。"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        User = get_user_model()
        # regular_user_obj 默认无 personnel 关联(确认)
        assert getattr(regular_user_obj, "personnel", None) is None
        c = APIClient()
        c.force_authenticate(user=regular_user_obj)
        response = c.get(ME_SCHEDULE_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []
