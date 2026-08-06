"""chat 接口附件上传测试。

验证三个契约：
1. multipart 上传 docx → 附件文本注入到 conversation_history 的 system 消息
2. 上传不支持格式（.doc 旧版 OLE）→ 400 + 中文不支持提示
3. 无附件时仍走 JSON 请求
"""
import io
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


def _make_docx() -> bytes:
    from docx import Document

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("附件里的合同条款")
    doc.save(buf)
    return buf.getvalue()


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="tester", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestChatAttachment:
    @patch("smart_assistant.agent.orchestrator.AgentOrchestrator.process")
    def test_upload_attachment_injects_into_history(self, mock_process, client):
        mock_process.return_value = {
            "answer": "ok", "intent": "general_chat", "tool_used": None,
            "tool_result": None, "sources": None, "usage": {},
        }
        docx = SimpleUploadedFile(
            "合同.docx", _make_docx(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "合同里写了什么？", "attachment": docx},
            format="multipart",
        )
        assert resp.status_code == 200
        _, kwargs = mock_process.call_args
        history = kwargs["conversation_history"]
        assert any(
            m.get("role") == "system" and "附件里的合同条款" in m.get("content", "")
            for m in history
        )

    def test_invalid_extension_rejected(self, client):
        bad = SimpleUploadedFile("旧版.doc", b"\xd0\xcf\x11\xe0", content_type="application/msword")
        resp = client.post(
            "/api/smart-assistant/chat/",
            {"query": "x", "attachment": bad},
            format="multipart",
        )
        assert resp.status_code == 400
        assert "不支持" in resp.data["detail"]

    def test_no_attachment_still_json(self, client):
        with patch("smart_assistant.agent.orchestrator.AgentOrchestrator.process") as mock_process:
            mock_process.return_value = {
                "answer": "ok", "intent": "general_chat", "tool_used": None,
                "tool_result": None, "sources": None, "usage": {},
            }
            resp = client.post("/api/smart-assistant/chat/", {"query": "你好"}, format="json")
        assert resp.status_code == 200
