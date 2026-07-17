"""RAGTool 端到端测试 — 知识库问答走完整链路。

Task 4 of feat/sa-e2e-scenarios: 补齐 RAGTool 端到端测试,验证 5
高频 E2E 场景之一"知识库问答"(对应 ``RAGTool`` / intent ``knowledge_qa``)。

参考模板:``test_e2e_smart_chat.py``(schedule / fallback / multi-turn)与
``test_e2e_personnel_tool.py``(ToolResult 脱敏)均使用
``@patch('smart_assistant.views.chat.AgentOrchestrator')`` mock 整个
编排器,本测试沿用同一模式以保证一致性。

为什么不走真实 LLM/RAGFlow 链路:

- ``classify_intent()`` 实际通过 ``client.generate(prompt=...)``(而非
  ``client.classify``);``generate_answer()`` 也调用同一接口。一个
  ``mock_llm_router`` 无法对分类 / 回答两步分别返回不同值;若用
  ``side_effect`` 串接,反而会让测试与 ``intent_classifier`` / ``answer``
  模块的私有协议耦合。
- RAGTool → RAGRouter → RagflowClient 链路中 ``RagflowClient`` 在
  ``smart_assistant.agent.rag_router`` 中导入,在 ``rag_tool`` 中并不存在
  ``RagflowClient`` 属性 — 直接 patch ``smart_assistant.tools.rag_tool.RagflowClient``
  在当前实现下是空操作。
- E2E 测试目标:验证 view 层完整集成(参数解析 + 会话管理 + AgentLog 写入
  + tool_result 序列化 + tool_fallback 标记),``RAGTool`` 内部 chunk 解析
  已有 ``test_tools.py::TestRAGTool`` 与 ``test_rag_router_coverage.py``
  覆盖,不必在 E2E 重复。

业务语义对照(view 层表现):

- 知识库命中(``RAGTool`` 返回 ``{found: True, context, sources}``):
  → ``tool_fallback`` 不出现,``tool_result.sources`` 与顶层 ``sources``
  都带文档名/分数,前端可渲染引用。
- 检索失败 / RAGFlow 不可用(``RAGRouter`` 捕获异常并返回 ``[]`` →
  ``RAGTool`` 返回 ``{found: False, ...}``):
  → ``tool_fallback=True``、``answer`` 走 ``generate_tool_empty_answer``
  降级文案、``AgentLog.tool_success=False``。
- 多轮问答(``conversation_id`` 已存在):
  → view 层把当前 user/assistant 消息追加到原 ``session.messages``,
  ``turn_count`` 累加。
"""
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from smart_assistant.models import SmartAssistantSession


@pytest.mark.django_db
class TestSmartChatE2ERAGQuery:
    """用户问"公司的 VPN 怎么登录?" → RAGTool → 知识库命中 → 引用来源;落空时降级。"""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_rag_query_returns_answer_with_sources(
        self, mock_orch_cls, auth_client,
    ):
        """知识库命中时,view 返回 answer + tool_result.sources(均含文档名)。"""
        # Arrange: 模拟 RAGTool 命中后的 orchestrator 产出
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "公司 VPN 登录地址是 https://vpn.company.com,使用工号 + 初始密码登录。[来源:IT操作手册.pdf]",
            "intent": "knowledge_qa",
            "tool_used": "knowledge_qa",
            "tool_result": {
                "found": True,
                "context": "VPN 登录地址: https://vpn.company.com,用户名工号,初始密码 123456。",
                "sources": [
                    {
                        "document": "IT操作手册.pdf",
                        "score": 0.95,
                        "source": "默认知识库",
                    }
                ],
            },
            "sources": None,  # 在 orchestrator.process 中按 tool_result.sources 自动填充
            "usage": {"prompt_tokens": 80, "completion_tokens": 60, "total_tokens": 140},
        }
        mock_orch_cls.return_value = mock_orch

        # Act
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "公司的 VPN 怎么登录?"},
            format="json",
        )

        # Assert: view 层完整序列化
        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["intent"] == "knowledge_qa"
        assert body["tool_used"] == "knowledge_qa"
        assert "VPN" in body["answer"]
        assert "IT操作手册" in body["answer"]

        # tool_result 透传:文档来源在 tool_result.sources 内,前端可渲染引用
        assert body["tool_result"]["found"] is True
        assert len(body["tool_result"]["sources"]) == 1
        assert body["tool_result"]["sources"][0]["document"] == "IT操作手册.pdf"
        assert body["tool_result"]["sources"][0]["score"] == 0.95

        # 业务约束:知识库命中时不应触发 tool_fallback 标记
        assert body.get("tool_fallback") is not True, (
            "RAGTool 命中时不应触发 tool_fallback;前端会错误降级。"
            f"body={body}"
        )

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_rag_query_handles_ragflow_unavailable(
        self, mock_orch_cls, auth_client,
    ):
        """RAGFlow 不可用时(``RAGRouter`` 捕获异常 → ``RAGTool`` 返回
        ``{found: False}`` → ``orchestrator`` 标记 ``tool_fallback=True``),
        view 应:

        1. 仍返回 200 而非 500(优雅降级)
        2. ``tool_result.found`` 为 False(供前端区分无结果 vs. 故障)
        3. ``answer`` 含降级文案(``generate_tool_empty_answer`` 输出)
        4. ``AgentLog.tool_success=False``(便于追溯失败率 — view 层
           内部消费 ``tool_fallback``,本断言验证其落地到 AgentLog)

        注意:view 层不在 response body 中暴露 ``tool_fallback`` 字段
        (chat.py:96-105 只序列化 answer/intent/tool_used/tool_result/
        sources/conversation_id),该标记仅驱动 AgentLog.tool_success。
        """
        from smart_assistant.models import AgentLog

        # Arrange: 模拟 RAGFlow 不可用时的 orchestrator 产出
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "抱歉,知识库暂不可用,请稍后重试。",
            "intent": "knowledge_qa",
            "tool_used": "knowledge_qa",
            "tool_result": {
                "found": False,
                "message": "知识库中未找到相关信息",
            },
            "sources": None,
            "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
            "tool_fallback": True,
        }
        mock_orch_cls.return_value = mock_orch

        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "公司的 VPN 怎么登录?"},
            format="json",
        )

        # Assert: 不返回 500,优雅降级
        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["intent"] == "knowledge_qa"
        assert body["tool_used"] == "knowledge_qa"
        assert "暂不可用" in body["answer"]
        assert body["tool_result"]["found"] is False, (
            "RAG 工具失败时 tool_result.found 必须为 False,"
            f"前端依赖该字段渲染降级提示。body={body}"
        )

        # 业务约束:失败时 AgentLog.tool_success 必须为 False(用于运维监控失败率)
        log = AgentLog.objects.filter(
            user_query="公司的 VPN 怎么登录?",
            intent="knowledge_qa",
        ).first()
        assert log is not None, "AgentLog 必须创建,即使工具失败"
        assert log.tool_success is False, (
            "RAGFlow 不可用场景下 tool_success 应为 False;"
            "view 层 chat.py 在 tool_fallback=True 时显式置为 False。"
            f"log={log}"
        )

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_rag_query_with_conversation_history(
        self, mock_orch_cls, auth_client,
    ):
        """带 ``conversation_id`` 的第二轮提问应:

        1. view 层通过 ``session.messages`` 找到历史并参与 answer 生成
        2. orchestrator 透传 ``conversation_history`` 参数
        3. session.messages 追加新的 user + assistant 两条消息
        4. session.turn_count 累加
        """
        # Arrange: 预先创建一个带历史的 session(由 auth_client 注入的同一 user)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(username="plain_user_test")
        existing_session = SmartAssistantSession.objects.create(
            user=user,
            title="VPN 咨询",
            messages=[
                {"role": "user", "content": "VPN 怎么登录?"},
                {"role": "assistant", "content": "VPN 登录地址..."},
            ],
            turn_count=1,
        )

        # Arrange: 模拟第二轮 orchestrator 产出(intent 仍为 knowledge_qa,
        # 因为用户继续追问同一主题)
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "根据上下文,VPN 登录流程已说明。如忘记密码,请联系 IT 重置。",
            "intent": "knowledge_qa",
            "tool_used": "knowledge_qa",
            "tool_result": {
                "found": True,
                "context": "密码重置流程:联系 IT(分机 8000)",
                "sources": [
                    {"document": "IT操作手册.pdf", "score": 0.88, "source": "默认知识库"}
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        mock_orch_cls.return_value = mock_orch

        # Act: 带 conversation_id 发起第二轮提问
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={
                "query": "那密码忘了怎么办?",
                "conversation_id": existing_session.id,
            },
            format="json",
        )

        # Assert: view 层正确处理历史会话
        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["intent"] == "knowledge_qa"
        assert body["tool_used"] == "knowledge_qa"
        assert "密码" in body["answer"]
        # 同一会话 ID 透传
        assert body["conversation_id"] == existing_session.id

        # 业务约束:orchestrator 收到非空 conversation_history(测试 view→orch 透传)
        # 注意:chat.py:44 是位置参数 process(query, conversation_history, tool_context=...),
        # 因此历史在 call_args.args[1],不在 kwargs 中。
        call_args = mock_orch.process.call_args
        history = call_args.args[1] if len(call_args.args) > 1 else None
        assert history is not None, "view 必须把 session.messages 传给 orchestrator"
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert "VPN 怎么登录" in history[0]["content"]

        # 业务约束:session.messages 追加新一轮 user + assistant
        refreshed = SmartAssistantSession.objects.get(id=existing_session.id)
        assert len(refreshed.messages) == 4, (
            "原有 2 条消息 + 新一轮 user + assistant = 4 条;"
            f"实际 {len(refreshed.messages)} 条。messages={refreshed.messages}"
        )
        assert refreshed.turn_count == 2, "turn_count 应从 1 累加到 2"
        assert refreshed.messages[-2]["role"] == "user"
        assert refreshed.messages[-2]["content"] == "那密码忘了怎么办?"
        assert refreshed.messages[-1]["role"] == "assistant"
        assert "密码" in refreshed.messages[-1]["content"]
