"""S3-2：公告草稿状态 —— 可见性、发布接口、通知、Dashboard、迁移回填。"""

import importlib

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from events.models import Announcement
from notifications.models import Notification

URL = "/api/events/announcements/"


def make_user(username, group=None):
    user = get_user_model().objects.create_user(username=username, password="x")
    if group:
        user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def ids(response):
    data = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
    return [row["id"] for row in data]


@pytest.fixture
def admin(db):
    return make_user("ann-admin", "Admin")


@pytest.fixture
def staff(db):
    return make_user("ann-staff")


@pytest.fixture
def draft(admin):
    return Announcement.objects.create(title="草稿", content="c", author=admin, status=Announcement.STATUS_DRAFT)


@pytest.fixture
def published(admin):
    return Announcement.objects.create(title="已发布", content="c", author=admin)


@pytest.mark.django_db
class TestModelAndNotifications:
    def test_page_created_announcement_is_published_and_notifies(self, admin, staff):
        response = client_for(admin).post(URL, {"title": "t", "content": "c"}, format="json")
        assert response.status_code == 201
        assert response.data["status"] == "published" and response.data["published_at"]
        assert Notification.objects.filter(user=staff, type="announcement").count() == 1

    def test_draft_does_not_notify(self, draft, staff):
        assert draft.published_at is None
        assert not Notification.objects.filter(type="announcement").exists()

    def test_status_is_read_only_via_api(self, admin, draft):
        response = client_for(admin).patch(f"{URL}{draft.pk}/", {"status": "published", "title": "新"}, format="json")
        assert response.status_code == 200
        draft.refresh_from_db()
        assert draft.status == "draft" and draft.title == "新"
        created = client_for(admin).post(URL, {"title": "t", "content": "c", "status": "draft"}, format="json")
        assert created.data["status"] == "published"


@pytest.mark.django_db
class TestVisibility:
    def test_list_hides_drafts_by_default_even_for_admin(self, admin, staff, draft, published):
        assert ids(client_for(staff).get(URL)) == [published.pk]
        assert ids(client_for(admin).get(URL)) == [published.pk]

    def test_admin_include_drafts_lists_drafts_first(self, admin, draft, published):
        assert ids(client_for(admin).get(URL, {"include_drafts": "1"})) == [draft.pk, published.pk]

    def test_staff_include_drafts_is_ignored(self, staff, draft, published):
        assert ids(client_for(staff).get(URL, {"include_drafts": "1"})) == [published.pk]

    def test_draft_detail(self, admin, staff, draft):
        assert client_for(admin).get(f"{URL}{draft.pk}/").status_code == 200
        assert client_for(staff).get(f"{URL}{draft.pk}/").status_code == 404

    def test_hr_sees_drafts(self, draft):
        hr = make_user("ann-hr", "Manager")
        assert ids(client_for(hr).get(URL, {"include_drafts": "1"})) == [draft.pk]


@pytest.mark.django_db
class TestPublish:
    def test_publish_notifies_once_and_repeat_is_409(self, admin, staff, draft):
        other_admin = make_user("ann-admin-2", "Admin")
        response = client_for(other_admin).post(f"{URL}{draft.pk}/publish/")
        assert response.status_code == 200
        assert response.data["status"] == "published" and response.data["published_at"]
        draft.refresh_from_db()
        assert draft.status == "published" and draft.published_at is not None
        # 作者本人不收；其他人各收一条
        assert Notification.objects.filter(type="announcement", user=staff).count() == 1
        assert not Notification.objects.filter(type="announcement", user=admin).exists()

        again = client_for(other_admin).post(f"{URL}{draft.pk}/publish/")
        assert again.status_code == 409
        assert Notification.objects.filter(type="announcement", user=staff).count() == 1

    def test_staff_cannot_publish(self, staff, draft):
        assert client_for(staff).post(f"{URL}{draft.pk}/publish/").status_code in (403, 404)
        draft.refresh_from_db()
        assert draft.status == "draft"

    def test_published_moves_to_top_of_public_list(self, admin, staff, draft, published):
        client_for(admin).post(f"{URL}{draft.pk}/publish/")
        assert ids(client_for(staff).get(URL)) == [draft.pk, published.pk]


@pytest.mark.django_db
def test_dashboard_excludes_drafts(admin, draft, published):
    response = client_for(admin).get("/api/dashboard/stats/")
    assert response.status_code == 200
    assert [row["id"] for row in response.data["recent_announcements"]] == [published.pk]


@pytest.mark.django_db
def test_migration_backfills_published_at(admin):
    Announcement.objects.create(title="旧", content="c", author=admin)
    Announcement.objects.update(published_at=None)
    module = importlib.import_module("events.migrations.0006_announcement_status_published_at")
    module.backfill_published_at(django_apps, None)
    row = Announcement.objects.get()
    assert row.published_at == row.created_at
