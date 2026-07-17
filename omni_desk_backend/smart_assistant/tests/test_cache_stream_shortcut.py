"""验证 process_stream() 流式路径的回答缓存短路。

Task 2 of feat/sa-e2e-scenarios: 流式入口先查缓存,
命中直接 yield 完整 answer,跳过 LLM 调用。
"""
import json

import pytest

from smart_assistant.agent.orchestrator import AgentOrchestrator
from smart_assistant.tools.tool_context import ToolContext
from smart_assistant.cache import (
    cache_answer,
    bump_cache_version,
)


@pytest.mark.django_db
class TestStreamAnswerCacheShortcut:
    """流式端点(POST /chat/stream/)应在缓存命中时短路,跳过 LLM 调用。"""

    def test_stream_cache_miss_calls_llm(self, mock_llm_router, admin_user_obj):
        """缓存未命中时,流式端点走完整编排。"""
        mock_llm_router.classify.return_value = "schedule_query"
        mock_llm_router.generate.return_value = (
            "Mock LLM response",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        # 至少包含 meta + 1+ chunk + done
        types = []
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                types.append(data.get("type"))
            except (IndexError, json.JSONDecodeError):
                pass

        assert "done" in types
        assert "meta" in types

    def test_stream_cache_hit_skips_llm(self, mock_llm_router, admin_user_obj):
        """预填缓存,验证流式端点直接 yield cached answer 而不调用 LLM。"""
        # 注:让 mock LLM 的 intent 分类返回与预填缓存一致的 intent,以保证
        # cache key(query + intent + context_sig)能命中预填条目。
        mock_llm_router.generate.return_value = (
            "schedule_query",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        cache_answer(
            query="张三这周值班",
            intent="schedule_query",
            answer="张三周一、周三值班",
            context_sig=f"u{admin_user_obj.pk}_sself",
        )

        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        # 解析所有 SSE event
        full_answer = []
        saw_done = False
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                if data.get("type") == "chunk":
                    full_answer.append(data["content"])
                if data.get("type") == "done":
                    saw_done = True
            except (IndexError, json.JSONDecodeError):
                pass

        assert saw_done
        assert "".join(full_answer) == "张三周一、周三值班"

    def test_stream_cache_version_bump_invalidates(self, mock_llm_router, admin_user_obj):
        """缓存版本升级后,流式端点应当走完整编排而非返回旧缓存。"""
        cache_answer(
            query="张三这周值班",
            intent="schedule_query",
            answer="旧答案",
            context_sig=f"u{admin_user_obj.pk}_sself",
        )
        bump_cache_version()

        mock_llm_router.classify.return_value = "schedule_query"
        mock_llm_router.generate.return_value = (
            "新答案",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        orchestrator = AgentOrchestrator()
        ctx = ToolContext(user=admin_user_obj)

        chunks = list(orchestrator.process_stream("张三这周值班", tool_context=ctx))

        full_answer = []
        for c in chunks:
            try:
                payload = c.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
                data = json.loads(payload)
                if data.get("type") == "chunk":
                    full_answer.append(data["content"])
            except (IndexError, json.JSONDecodeError):
                pass

        assert "旧答案" not in "".join(full_answer)