"""Regression tests: staff access does not grant global smart-assistant access."""

from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from smart_assistant.models import LlmAppConfig, LlmEndpoint
from users.models import CustomUser


class TestSmartAssistantAdminBoundaries(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = CustomUser.objects.create_user(username="support_staff", password="x", is_staff=True)
        manager, _ = Group.objects.get_or_create(name="Manager")
        self.staff.groups.add(manager)
        self.admin = CustomUser.objects.create_user(username="explicit_admin", password="x")
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin.groups.add(admin_group)
        self.endpoint = LlmEndpoint.objects.create(
            name="测试端点", api_endpoint="https://93.184.216.34", api_key="test-key"
        )
        self.config = LlmAppConfig.objects.create(
            app_name="smart_assistant", endpoint=self.endpoint, model_name="test-model"
        )

    def test_non_admin_staff_cannot_read_statistics_or_manage_models(self):
        self.client.force_authenticate(user=self.staff)
        for path in (
            "/api/smart-assistant/stats/overview/",
            "/api/smart-assistant/stats/daily/",
            "/api/smart-assistant/stats/datasets/",
            "/api/smart-assistant/endpoints/",
            f"/api/smart-assistant/endpoints/{self.endpoint.pk}/",
            "/api/smart-assistant/app-configs/",
            f"/api/smart-assistant/app-configs/{self.config.pk}/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        with patch("smart_assistant.views.llm_config.http_requests.get") as request:
            self.assertEqual(
                self.client.post(f"/api/smart-assistant/endpoints/{self.endpoint.pk}/test-endpoint/").status_code,
                403,
            )
            request.assert_not_called()
        self.assertEqual(
            self.client.patch(f"/api/smart-assistant/endpoints/{self.endpoint.pk}/", {"name": "tampered"}).status_code,
            403,
        )
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.name, "测试端点")

    def test_explicit_admin_group_works_without_staff_flag(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get("/api/smart-assistant/stats/overview/").status_code, 200)
        self.assertEqual(self.client.get("/api/smart-assistant/endpoints/").status_code, 200)
        self.assertEqual(self.client.get("/api/smart-assistant/app-configs/").status_code, 200)

    def test_superuser_without_staff_flag_is_authorized(self):
        superuser = CustomUser.objects.create_user(username="root", password="x", is_superuser=True)
        self.client.force_authenticate(user=superuser)
        self.assertEqual(self.client.get("/api/smart-assistant/stats/overview/").status_code, 200)
        self.assertEqual(self.client.get("/api/smart-assistant/endpoints/").status_code, 200)
