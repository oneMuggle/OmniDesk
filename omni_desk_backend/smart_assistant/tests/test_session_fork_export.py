"""智能助手会话 fork（复制）/ export（Markdown 导出）API 测试。

覆盖:
- fork: 全量复制完整性 / at_message 截断 / 自定义标题 / 他人会话 404 / 非法参数 400
- export: 200 + content-type + Content-Disposition / 内容含标题与消息文本 / 他人会话 404
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from smart_assistant.models import SmartAssistantSession
from users.models import CustomUser

SAMPLE_MESSAGES = [
    {"role": "user", "content": "明天谁值班？"},
    {"role": "assistant", "content": "明天张三值班。"},
    {"role": "user", "content": "后天的安排呢？"},
    {"role": "assistant", "content": "后天上午有项目例会。"},
]


class SessionForkExportTestBase(TestCase):
    """公共 setUp:双用户 + 本人会话 + 他人会话。"""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="fork_user",
            password="password123",
        )
        self.other_user = CustomUser.objects.create_user(
            username="other_user",
            password="password123",
        )
        self.session = SmartAssistantSession.objects.create(
            user=self.user,
            title="值班咨询",
            messages=SAMPLE_MESSAGES,
            turn_count=2,
        )
        self.other_session = SmartAssistantSession.objects.create(
            user=self.other_user,
            title="他人会话",
            messages=[{"role": "user", "content": "隐私内容"}],
            turn_count=1,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def fork_url(self, session_id):
        return f"/api/smart-assistant/sessions/{session_id}/fork/"

    def export_url(self, session_id):
        return f"/api/smart-assistant/sessions/{session_id}/export/"


class TestSessionFork(SessionForkExportTestBase):
    """fork @action 测试。"""

    def test_fork_full_copy(self):
        """缺省全量复制:消息/归属/标题后缀/轮数。"""
        response = self.client.post(self.fork_url(self.session.pk))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_id = response.data["id"]
        self.assertNotEqual(new_id, self.session.pk)

        new_session = SmartAssistantSession.objects.get(pk=new_id)
        self.assertEqual(new_session.user, self.user)
        self.assertEqual(new_session.title, "值班咨询（副本）")
        self.assertEqual(new_session.messages, SAMPLE_MESSAGES)
        self.assertEqual(new_session.turn_count, 2)
        # 原会话不受影响
        self.session.refresh_from_db()
        self.assertEqual(len(self.session.messages), 4)

        # 响应体为完整会话序列化
        self.assertEqual(response.data["title"], "值班咨询（副本）")
        self.assertEqual(response.data["messages"], SAMPLE_MESSAGES)

    def test_fork_at_message_truncation(self):
        """at_message=N 仅复制前 N 条消息,turn_count 按截断结果重算。"""
        response = self.client.post(self.fork_url(self.session.pk), {"at_message": 2}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_session = SmartAssistantSession.objects.get(pk=response.data["id"])
        self.assertEqual(new_session.messages, SAMPLE_MESSAGES[:2])
        # 截断后仅剩 1 条 user 消息 → 1 轮
        self.assertEqual(new_session.turn_count, 1)

    def test_fork_at_message_zero_yields_empty(self):
        """at_message=0 复制空消息列表。"""
        response = self.client.post(self.fork_url(self.session.pk), {"at_message": 0}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_session = SmartAssistantSession.objects.get(pk=response.data["id"])
        self.assertEqual(new_session.messages, [])
        self.assertEqual(new_session.turn_count, 0)

    def test_fork_custom_title(self):
        """请求传 title 时使用自定义标题。"""
        response = self.client.post(
            self.fork_url(self.session.pk),
            {"title": "分支探索-方案A"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "分支探索-方案A")

    def test_fork_other_user_session_404(self):
        """fork 他人会话返回 404（queryset 限定本人）。"""
        response = self.client.post(self.fork_url(self.other_session.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_fork_invalid_at_message_400(self):
        """at_message 非法（负数/非整数）返回 400。"""
        response = self.client.post(
            self.fork_url(self.session.pk),
            {"at_message": -1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.fork_url(self.session.pk),
            {"at_message": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fork_unauthenticated_401(self):
        """未认证请求返回 401。"""
        self.client.force_authenticate(user=None)
        response = self.client.post(self.fork_url(self.session.pk))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestSessionExport(SessionForkExportTestBase):
    """export @action 测试。"""

    def test_export_markdown_response(self):
        """200 + text/markdown + 附件 Content-Disposition。"""
        response = self.client.get(self.export_url(self.session.pk))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/markdown", response["Content-Type"])
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        # RFC 5987 编码的中文文件名（标题 + 日期）
        self.assertIn("filename*=UTF-8''", disposition)
        self.assertIn(".md", disposition)

    def test_export_markdown_content(self):
        """内容含标题/元信息/逐条消息文本与角色标签。"""
        response = self.client.get(self.export_url(self.session.pk))
        content = response.content.decode("utf-8")

        self.assertIn("# 值班咨询", content)
        self.assertIn("创建时间：", content)
        self.assertIn("对话轮数：2", content)
        self.assertIn("**用户**:", content)
        self.assertIn("**助手**:", content)
        self.assertIn("明天谁值班？", content)
        self.assertIn("明天张三值班。", content)

    def test_export_other_user_session_404(self):
        """导出他人会话返回 404。"""
        response = self.client.get(self.export_url(self.other_session.pk))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_unauthenticated_401(self):
        """未认证请求返回 401。"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.export_url(self.session.pk))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
