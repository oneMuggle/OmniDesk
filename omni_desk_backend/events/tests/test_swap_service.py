"""swap_service 单元测试"""

from datetime import date, timedelta

import pytest
from django.conf import settings
from django.utils import timezone
from unittest.mock import MagicMock

from events.models import Schedule, ScheduleSwapRequest
from events.services import swap_service
from events.services.swap_service import (
    SwapServiceError,
    SwapPermissionError,
    SwapNotFoundError,
)
from personnel.models import Personnel


class TestSwapServiceExceptions:
    """异常类可正确实例化 + 抛出/捕获语义正确"""

    def test_swap_service_error_inherits_exception(self):
        """SwapServiceError 是 Exception 子类"""
        assert issubclass(SwapServiceError, Exception)

    def test_swap_permission_error_inherits_exception(self):
        """SwapPermissionError 是 Exception 子类"""
        assert issubclass(SwapPermissionError, Exception)

    def test_swap_not_found_error_inherits_exception(self):
        """SwapNotFoundError 是 Exception 子类"""
        assert issubclass(SwapNotFoundError, Exception)

    def test_swap_service_error_catchable(self):
        """SwapServiceError 可被 except Exception 捕获"""
        with pytest.raises(SwapServiceError, match="业务错误"):
            raise SwapServiceError("业务错误")

    def test_swap_permission_error_distinct_from_service(self):
        """SwapPermissionError 不是 SwapServiceError 子类(独立异常层级)"""
        assert not issubclass(SwapPermissionError, SwapServiceError)

    def test_swap_not_found_error_distinct_from_service(self):
        """SwapNotFoundError 不是 SwapServiceError 子类"""
        assert not issubclass(SwapNotFoundError, SwapServiceError)


@pytest.fixture
def personnel_a(db):
    return Personnel.objects.create(name="张三")


@pytest.fixture
def personnel_b(db):
    return Personnel.objects.create(name="李四")


@pytest.fixture
def schedule_a(db, personnel_a):
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=7),
        duty_person=personnel_a,
    )


@pytest.fixture
def schedule_b(db, personnel_b):
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=8),
        duty_person=personnel_b,
    )


@pytest.fixture
def user_a(db, personnel_a):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username="user_a", password="test", personnel=personnel_a)


@pytest.fixture
def user_b(db, personnel_b):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username="user_b", password="test", personnel=personnel_b)


@pytest.fixture
def swap_request(db, personnel_a, personnel_b, schedule_a):
    return ScheduleSwapRequest.objects.create(
        requester=personnel_a,
        target_personnel=personnel_b,
        original_schedule=schedule_a,
        reason="测试换班",
        expires_at=timezone.now() + timedelta(hours=48),
    )


@pytest.fixture
def target_personnel(db):
    """测试目标 personnel(王五)"""
    return Personnel.objects.create(name="王五")


@pytest.fixture
def future_schedule(db, personnel_a):
    """personnel_a 未来 14 天后的排班(用于测试创建 swap)"""
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=14),
        duty_person=personnel_a,
    )


@pytest.mark.django_db
class TestCreateSwapFromSerializer:
    """create_swap_from_serializer:从 DRF serializer 创建 swap"""

    def test_create_success(self, swap_request, target_personnel, schedule_a, future_schedule):
        """正常路径:serializer 注入完整 validated_data,成功创建"""
        mock_serializer = MagicMock()
        mock_serializer.validated_data = {
            "requester": swap_request.requester,
            "target_personnel": target_personnel,
            "original_schedule": future_schedule,
            "target_schedule": None,
            "scope": "duty_person",
            "reason": "测试换班",
        }

        result = swap_service.create_swap_from_serializer(serializer=mock_serializer)

        assert isinstance(result, ScheduleSwapRequest)
        assert result.id is not None
        assert result.status == ScheduleSwapRequest.STATUS_PENDING
        assert result.reason == "测试换班"
        ttl = getattr(settings, "SWAP_REQUEST_TTL_HOURS", 48)
        assert result.expires_at > timezone.now()
        assert result.expires_at <= timezone.now() + timedelta(hours=ttl + 1)

    def test_create_without_target_schedule(self, swap_request, target_personnel, future_schedule):
        """target_schedule 为 None 时单方面替班"""
        mock_serializer = MagicMock()
        mock_serializer.validated_data = {
            "requester": swap_request.requester,
            "target_personnel": target_personnel,
            "original_schedule": future_schedule,
            "target_schedule": None,
            "scope": "duty_person",
            "reason": "单方面替班",
        }

        result = swap_service.create_swap_from_serializer(serializer=mock_serializer)

        assert result.target_schedule_id is None


@pytest.mark.django_db
class TestCreateSwapByQuery:
    """create_swap_by_query:从 query 参数(姓名/日期)创建 swap"""

    def test_create_success(self, swap_request, target_personnel, future_schedule):
        """正常路径:姓名 + 日期都能解析到"""
        result = swap_service.create_swap_by_query(
            requester=swap_request.requester,
            target_name="王五",
            duty_date=future_schedule.duty_date,
            reason="测试",
        )
        assert result.id is not None
        assert result.status == ScheduleSwapRequest.STATUS_PENDING

    def test_target_not_found(self, swap_request, schedule_a):
        """目标人不存在 → SwapServiceError"""
        with pytest.raises(SwapServiceError, match="未找到 '不存在的名字' 该人员"):
            swap_service.create_swap_by_query(
                requester=swap_request.requester,
                target_name="不存在的名字",
                duty_date=schedule_a.duty_date,
            )

    def test_schedule_not_found(self, swap_request, target_personnel):
        """该日不存在 requester 排班 → SwapServiceError"""
        past_date = date.today() - timedelta(days=30)
        with pytest.raises(SwapServiceError, match=f"找不到您 {past_date} 的排班记录"):
            swap_service.create_swap_by_query(
                requester=swap_request.requester,
                target_name="王五",
                duty_date=past_date,
            )

    def test_self_swap(self, target_personnel):
        """target == requester → SwapServiceError"""
        # 创建 target_personnel 自己的排班,这样会进入 self-swap 检查
        target_schedule = Schedule.objects.create(
            duty_date=date.today() + timedelta(days=20),
            duty_person=target_personnel,
        )
        with pytest.raises(SwapServiceError, match="不能把班换给自己"):
            swap_service.create_swap_by_query(
                requester=target_personnel,
                target_name="王五",
                duty_date=target_schedule.duty_date,
                reason="测试自己换自己",
            )
