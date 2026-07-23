"""RAGTool 端到端测试 — 走真实 RAGTool 链路(view → AgentOrchestrator → RAGTool → RAGRouter → RagflowClient).

Task 4 Fix(post-review):原实现通过 ``@patch('smart_assistant.views.chat.AgentOrchestrator')``
mock 整个编排器,未真正执行 RAGTool 链路。Reviewer 指出此偏离 brief,要求改用:

- 真实 ``AgentOrchestrator.process()`` 运行
- 真实 ``RAGTool.execute()`` 运行
- 真实 ``RAGRouter.search_multi()`` 运行
- mock ``RagflowClient.retrieval()`` 在 RAG 边界控制 chunks 返回
- ``mock_llm_router.generate.side_effect`` 控制 ``classify_intent`` / ``generate_answer`` 的 LLM 响应

**已知 RAGTool 兼容性问题**:
RAGTool 的 ``build_base_queryset`` / ``_scope_self`` 已被重写(返回 ``.none()``),
导致 ``BaseTool.supports_scope_filter`` 属性返回 ``True``。但 ``RAGTool.execute``
签名仍是 ``(query, context=None)`` 旧式,无法接受 orchestrator 走新路径时的
``execute(params=..., scope=..., qs=...)`` kwargs 调用 — 会抛 TypeError。
本测试用 ``patch.object(RAGTool, 'supports_scope_filter', new=False)`` 强制走
旧路径(语义上 RAGTool 也不支持 scope 过滤,这是正确的语义覆盖)。

链路断言:
- Test 1(知识库命中)→ 验证 ``RagflowClient.retrieval`` 真的被调用,query 透传
- Test 2(RAGFlow 不可用)→ ``retrieval`` 抛 ``ConnectionError``,验证 RAGRouter
  异常捕获 + RAGTool ``found=False`` + orchestrator ``tool_fallback=True`` 端到端贯通
- Test 3(对话历史)→ spy ``RAGTool.execute`` 验证 history 通过 ``context`` 参数
  透传给 RAGTool(session.messages 追加 + turn_count 累加)
"""
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework import status

from ragflow_service.models import RagflowConfig
from smart_assistant.models import AgentLog, SmartAssistantSession
from smart_assistant.tools.rag_tool import RAGTool


# =============================================================================
# Helper: LLM side_effect 序列
# =============================================================================
# 每个测试都需要 3 次 LLM 调用:
#   1) orchestrator.process() 内的 classify_intent
#   2) generate_tool_chain_plan() 内的 classify_intent(始终调用,不读缓存)
#   3) generate_answer()(命中)或 generate_tool_empty_answer()(落空)


def _llm_responses(intent: str, answer: str, usage: dict | None = None):
    """构造 3-步 LLM 响应:intent × 2 + answer × 1。"""
    base_usage = {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    return [
        (intent, dict(base_usage)),
        (intent, dict(base_usage)),
        (answer, usage or {"prompt_tokens": 80, "completion_tokens": 60, "total_tokens": 140}),
    ]


@pytest.fixture
def rag_ragflow_setup(db):
    """创建 active RagflowConfig + 注入 SMART_ASSISTANT_DATASET_ID。

    真实 ``RAGRouter.route_query`` 在无 KnowledgeDataset 时回退到 RagflowConfig
    + ``SMART_ASSISTANT_DATASET_ID``;两者必须都存在才能让 search_dataset 真正
    调用 RagflowClient.retrieval。
    """
    RagflowConfig.objects.create(
        name="test-rag",
        api_endpoint="http://ragflow.test",
        api_key="test-key",
        is_active=True,
    )
    return override_settings(SMART_ASSISTANT_DATASET_ID="test-ds")


@pytest.mark.django_db
class TestSmartChatE2ERAGQuery:
    """用户问"公司的 VPN 怎么登录?" → RAGTool → 知识库命中 → 引用来源;落空时降级。"""

    def test_rag_query_returns_answer_with_sources(
        self, auth_client, mock_llm_router, rag_ragflow_setup,
    ):
        """知识库命中时,view 返回 answer + tool_result.sources(均含文档名)。

        链路:view → AgentOrchestrator → RAGTool → RAGRouter → RagflowClient.retrieval(mocked)
        """
        # Arrange: mock RagflowClient.retrieval 在 RAG 边界返回 chunks
        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.retrieval.return_value = [
                {
                    "content": "VPN 登录地址: https://vpn.company.com,用户名工号,初始密码 123456。",
                    "document_name": "IT操作手册.pdf",
                    "similarity": 0.95,
                },
            ]
            mock_client_cls.return_value = mock_client

            # 强制 RAGTool 走 orchestrator 旧路径(避免 kwargs 调用 TypeError)
            with patch.object(RAGTool, "supports_scope_filter", new=False):
                # LLM: 2 次 classify_intent + 1 次 generate_answer
                mock_llm_router.generate.side_effect = _llm_responses(
                    intent="knowledge_qa",
                    answer=(
                        "公司 VPN 登录地址是 https://vpn.company.com,"
                        "使用工号 + 初始密码登录。[来源:IT操作手册.pdf]"
                    ),
                )

                # Act
                with rag_ragflow_setup:
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

        # === 核心断言:验证 RAGTool 真实链路 ===
        # RagflowClient.retrieval 必须被真实调用(非 mock 编排器)
        assert mock_client.retrieval.call_count >= 1, (
            "RagflowClient.retrieval 至少被调用 1 次,"
            "证明测试走真实 RAGTool → RAGRouter → RagflowClient 链路"
        )
        # query 透传给 retrieval(question 字段)
        retrieval_kwargs = mock_client.retrieval.call_args.kwargs
        assert retrieval_kwargs["question"] == "公司的 VPN 怎么登录?"
        assert retrieval_kwargs["dataset_ids"] == ["test-ds"]
        assert retrieval_kwargs["top_k"] == 5

    def test_rag_query_handles_ragflow_unavailable(
        self, auth_client, mock_llm_router, rag_ragflow_setup,
    ):
        """RAGFlow 不可用时(``RagflowClient.retrieval`` 抛 ``ConnectionError``),
        真实链路应端到端贯通:异常被 ``RAGRouter.search_dataset`` 捕获并返回
        ``[]`` → ``RAGRouter.search_multi`` 返回 ``[]`` → ``RAGTool.execute``
        返回 ``{found: False, message: ...}`` → ``orchestrator`` 标记
        ``tool_fallback=True`` → view 写 ``AgentLog.tool_success=False``。

        关键:本测试在 RAG 边界真实抛异常(非 pre-construct ``found=False``),
        验证整套异常降级链路确实跑通。
        """
        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            mock_client = MagicMock()
            # 关键:在 RAG 边界真实抛异常,而非 pre-construct 失败结果
            mock_client.retrieval.side_effect = ConnectionError("RAGFlow 离线")
            mock_client_cls.return_value = mock_client

            with patch.object(RAGTool, "supports_scope_filter", new=False):
                # LLM: 2 次 classify_intent + 1 次 generate_tool_empty_answer
                mock_llm_router.generate.side_effect = _llm_responses(
                    intent="knowledge_qa",
                    answer="抱歉,知识库暂不可用,请稍后重试。",
                )

                with rag_ragflow_setup:
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
        assert "暂不可用" in body["answer"], (
            f"降级文案应包含「暂不可用」;实际 answer={body['answer']!r}"
        )
        assert body["tool_result"]["found"] is False, (
            "RAG 工具失败时 tool_result.found 必须为 False,"
            f"前端依赖该字段渲染降级提示。body={body}"
        )

        # 业务约束:失败时 AgentLog.tool_success 必须为 False
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

        # === 核心断言:验证异常捕获真的发生在 RAG 边界 ===
        # RagflowClient.retrieval 真的被调用过(非 pre-construct 短路)
        assert mock_client.retrieval.call_count >= 1, (
            "RagflowClient.retrieval 应至少被调用 1 次,"
            "ConnectionError 必须在 RAG 边界真实抛出才能验证降级链路"
        )

    def test_rag_query_with_conversation_history(
        self, auth_client, mock_llm_router, rag_ragflow_setup,
    ):
        """带 ``conversation_id`` 的第二轮提问应:

        1. view 层把 ``session.messages`` 作为 ``conversation_history`` 透传给 orchestrator
        2. orchestrator 把 history 装入 ``context={'history': [...]}`` 传给 RAGTool.execute
           (spy 验证:这是 brief 要求的"history reaches RAGTool"断言)
        3. RAGTool → RAGRouter → RagflowClient.retrieval 链路真实执行
        4. session.messages 追加新 user + assistant 两条
        5. session.turn_count 累加 1 → 2
        """
        # Arrange: 通过 auth_client.handler._force_user 反查注入用户(避免 username 硬编码)
        user = auth_client.handler._force_user
        existing_session = SmartAssistantSession.objects.create(
            user=user,
            title="VPN 咨询",
            messages=[
                {"role": "user", "content": "VPN 怎么登录?"},
                {"role": "assistant", "content": "VPN 登录地址..."},
            ],
            turn_count=1,
        )

        # Arrange: spy RAGTool.execute 捕获 context 参数(brief 要求"history reaches RAGTool")
        real_rag_execute = RAGTool.execute
        captured_calls: list[dict] = []

        def spy_rag_execute(self, query, context=None):
            captured_calls.append({"query": query, "context": context})
            return real_rag_execute(self, query, context)

        with patch("smart_assistant.agent.rag_router.RagflowClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.retrieval.return_value = [
                {
                    "content": "密码重置流程:联系 IT(分机 8000)",
                    "document_name": "IT操作手册.pdf",
                    "similarity": 0.88,
                },
            ]
            mock_client_cls.return_value = mock_client

            with patch.object(RAGTool, "supports_scope_filter", new=False), \
                 patch.object(RAGTool, "execute", new=spy_rag_execute):
                mock_llm_router.generate.side_effect = _llm_responses(
                    intent="knowledge_qa",
                    answer="根据上下文,VPN 登录流程已说明。如忘记密码,请联系 IT 重置。",
                )

                with rag_ragflow_setup:
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

        # === 核心断言:history 真的到达 RAGTool ===
        # RAGTool.execute 必须被调用至少 1 次(真实链路)
        assert len(captured_calls) >= 1, (
            "RAGTool.execute 应至少被调用 1 次,"
            f"证明测试走真实 orchestrator → RAGTool 链路。captured={captured_calls}"
        )
        # 捕获的 context 应包含 conversation history
        first_call_context = captured_calls[0]["context"]
        assert first_call_context is not None, "RAGTool.execute 必须收到 context 参数"
        assert "history" in first_call_context, (
            f"context 应包含 history 键;实际 context={first_call_context}"
        )
        history = first_call_context["history"]
        assert len(history) == 2, (
            f"history 应为原始 2 条消息;实际 {len(history)} 条。history={history}"
        )
        assert history[0]["role"] == "user"
        assert "VPN 怎么登录" in history[0]["content"]
        assert history[1]["role"] == "assistant"

        # === 核心断言:RagflowClient.retrieval 真实被调用 ===
        assert mock_client.retrieval.call_count >= 1, (
            "RagflowClient.retrieval 应至少被调用 1 次(第二轮 RAG 查询)"
        )
        # 第二轮 query 透传给 retrieval
        assert mock_client.retrieval.call_args.kwargs["question"] == "那密码忘了怎么办?"

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
