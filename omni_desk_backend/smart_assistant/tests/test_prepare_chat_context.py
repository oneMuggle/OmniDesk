"""prepare_chat_context 单元测试(R5-D3 chat 前置上下文合并)。

覆盖契约:
1. 正常路径:query/tool_context/history/session/conversation_id 齐备,err=None
2. serializer 无效 → err=(Response, 400),其余元素全 None
3. 会话缺失:require_session=True → err=(Response, 404);
   require_session=False(stream 语义)→ 继续执行,session=None 不报错
4. 附件抽取成功 → 注入历史头部 system 消息 + tool_context.attachment 携带元数据
5. 附件抽取失败 → 400,且优先于 short_circuit(与原 sync 视图顺序一致)
6. short_circuit 返回 Response 时立即短路,不再加载会话/构造 ToolContext
   (对应 sync 路径 confirm-replay 在 load_session 之前返回的原语义)
"""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from smart_assistant.scope import SmartAssistantScope
from smart_assistant.views import conversation_manager
from smart_assistant.views.conversation_manager import prepare_chat_context

pytestmark = pytest.mark.django_db

FACTORY = APIRequestFactory()

# 与 SmartChatViewSet.parser_classes 同型(裸 Request 不继承 ViewSet 的解析器)
PARSERS = [JSONParser(), MultiPartParser(), FormParser()]


def _make_user(**kwargs):
    User = get_user_model()
    params = {"username": "u1", "password": "x"}
    params.update(kwargs)
    return User.objects.create_user(**params)


def _make_request(payload, user=None):
    """构造可直接传入 prepare_chat_context 的 DRF Request。"""
    django_request = FACTORY.post("/api/smart-assistant/chat/", payload, format="json")
    request = Request(django_request, parsers=PARSERS)
    if user is not None:
        request.user = user
    return request


class TestPrepareChatContextNormalPath:
    def test_no_conversation_id_returns_empty_session(self):
        """无 conversation_id:session/conversation_id 为 None,err 为 None。"""
        user = _make_user()
        request = _make_request({"query": "你好"}, user=user)

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=True
        )

        assert err is None
        assert query == "你好"
        assert session is None
        assert conversation_id is None
        # load_session 无会话时返回 (None, None):history 为 None(原行为)
        assert history is None
        assert tool_context.user is user
        assert tool_context.scope == SmartAssistantScope.SELF
        assert tool_context.attachment is None

    def test_existing_session_loaded_with_history(self):
        """有效 conversation_id:加载会话并构建历史。"""
        from smart_assistant.models import SmartAssistantSession

        user = _make_user()
        messages = [
            {"role": "user", "content": "上一问"},
            {"role": "assistant", "content": "上一答"},
        ]
        session_obj = SmartAssistantSession.objects.create(user=user, title="t", messages=messages, turn_count=2)
        request = _make_request({"query": "继续", "conversation_id": session_obj.id}, user=user)

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=True
        )

        assert err is None
        assert query == "继续"
        # load_session 重新 get,实例不同但主键一致
        assert session.pk == session_obj.pk
        assert conversation_id == session_obj.id
        assert history == messages

    def test_attachment_extracted_and_injected(self):
        """带附件:注入历史头部 system 消息,tool_context.attachment 携带元数据。"""
        user = _make_user()
        upload = SimpleUploadedFile("notes.txt", "附件正文内容".encode("utf-8"), content_type="text/plain")
        django_request = FACTORY.post(
            "/api/smart-assistant/chat/", {"query": "总结附件", "attachment": upload}, format="multipart"
        )
        request = Request(django_request, parsers=PARSERS)
        request.user = user

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=False
        )

        assert err is None
        assert tool_context.attachment["filename"] == "notes.txt"
        assert "附件正文内容" in tool_context.attachment["text"]
        assert len(history) == 1
        assert history[0]["role"] == "system"
        assert "附件正文内容" in history[0]["content"]


class TestPrepareChatContextErrors:
    def test_invalid_serializer_returns_400_and_nones(self):
        """缺 query:err=(Response, 400),其余元素全 None。"""
        user = _make_user()
        request = _make_request({}, user=user)

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=True
        )

        assert query is None
        assert tool_context is None
        assert history is None
        assert session is None
        assert conversation_id is None
        err_resp, err_status = err
        assert isinstance(err_resp, Response)
        assert err_status == status.HTTP_400_BAD_REQUEST
        assert err_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "query" in err_resp.data

    def test_missing_session_require_true_returns_404(self):
        """require_session=True(sync 语义):会话缺失 → 404 session not found。"""
        user = _make_user()
        request = _make_request({"query": "hi", "conversation_id": 999999}, user=user)

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=True
        )

        assert query is None
        assert tool_context is None
        err_resp, err_status = err
        assert err_status == status.HTTP_404_NOT_FOUND
        assert err_resp.data == {"detail": "session not found"}

    def test_missing_session_require_false_continues(self):
        """require_session=False(stream 语义):无效会话 id 不报错,继续流式。"""
        user = _make_user()
        request = _make_request({"query": "hi", "conversation_id": 999999}, user=user)

        query, tool_context, history, session, conversation_id, err = prepare_chat_context(
            request, require_session=False
        )

        assert err is None
        assert query == "hi"
        assert session is None
        # 原 stream 语义:无效 cid 仍透传给后续持久化分支二次 get 兜底
        assert conversation_id == 999999
        assert history is None

    def test_other_users_session_treated_as_missing(self):
        """他人会话等同不存在(require_session=True → 404)。"""
        owner = _make_user(username="owner")
        other = _make_user(username="other")
        from smart_assistant.models import SmartAssistantSession

        session_obj = SmartAssistantSession.objects.create(user=owner, title="t", messages=[], turn_count=0)
        request = _make_request({"query": "hi", "conversation_id": session_obj.id}, user=other)

        _, _, _, _, _, err = prepare_chat_context(request, require_session=True)

        err_resp, err_status = err
        assert err_status == status.HTTP_404_NOT_FOUND


class TestPrepareChatContextShortCircuit:
    def test_short_circuit_response_shortcuts_before_session_load(self, monkeypatch):
        """short_circuit 返回 Response → 立即短路,不再加载会话。

        对应 sync confirm-replay 语义:confirm 请求即使携带无效
        conversation_id 也走 replay,绝不 404。
        """
        user = _make_user()

        def _forbid_load(*args, **kwargs):
            raise AssertionError("short_circuit 短路后不应调用 load_session")

        monkeypatch.setattr(conversation_manager, "load_session", _forbid_load)

        shortcut_resp = Response({"detail": "replayed"}, status=status.HTTP_200_OK)
        request = _make_request({"query": "hi", "conversation_id": 999999}, user=user)
        _, _, _, _, _, err = prepare_chat_context(
            request,
            require_session=True,
            short_circuit=lambda validated: shortcut_resp,
        )

        err_resp, err_status = err
        assert err_resp is shortcut_resp
        assert err_status == status.HTTP_200_OK

    def test_attachment_error_precedes_short_circuit(self):
        """附件抽取失败先于 short_circuit(原 sync 顺序:附件校验在 confirm 前)。"""
        user = _make_user()
        oversized = SimpleUploadedFile("big.txt", b"x" * (10 * 1024 * 1024 + 1), content_type="text/plain")
        django_request = FACTORY.post(
            "/api/smart-assistant/chat/", {"query": "hi", "attachment": oversized}, format="multipart"
        )
        request = Request(django_request, parsers=PARSERS)
        request.user = user

        def _unexpected(validated):
            raise AssertionError("附件失败时应先于 short_circuit 返回")

        _, _, _, _, _, err = prepare_chat_context(request, require_session=True, short_circuit=_unexpected)

        err_resp, err_status = err
        assert err_status == status.HTTP_400_BAD_REQUEST
        assert "10MB" in err_resp.data["detail"]
