"""性能基准测试 — 智能助手 P95 / TTFB / 50 并发稳定性。

Task 4 of feat/sa-perf-ux: 性能基线验证。

关键设计:
- P95 和 TTFB 测试使用真实 Django test client + mock LLM
- 50 并发测试每线程独立 APIClient,force_authenticate 注入 user(不查 DB)
- 复用 ``mock_llm_router`` + ``auth_client`` fixtures
- 三个核心指标:
  1. 非流式 P95 < 1.5s
  2. 50 并发 0 失败
  3. 缓存命中 TTFB < 500ms(本地)/ < 300ms(生产)
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest


@pytest.mark.django_db
class TestChatPerformance:
    """智能助手 chat 端点性能基准。"""

    def test_non_streaming_p95_under_1500ms(self, mock_llm_router, auth_client):
        """非流式 P95 应 < 1.5s(mock LLM + SQLite)。"""
        mock_llm_router.generate.return_value = (
            "Mock LLM response",
            {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
        )

        latencies = []
        for i in range(20):
            start = time.perf_counter()
            response = auth_client.post(
                "/api/smart-assistant/chat/",
                data={"query": f"查询第{i}次"},
                format="json",
            )
            latency = (time.perf_counter() - start) * 1000
            assert response.status_code == 200, (
                f"请求 {i} 失败: {response.status_code} {response.content[:200]}"
            )
            latencies.append(latency)

        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        p95 = latencies[min(p95_idx, len(latencies) - 1)]
        p50 = latencies[len(latencies) // 2]
        print(f"\n[P95] {p95:.1f}ms | [P50] {p50:.1f}ms | "
              f"[max] {latencies[-1]:.1f}ms | [avg] {sum(latencies)/len(latencies):.1f}ms")
        assert p95 < 1500, f"P95 {p95:.1f}ms 超过 1.5s 目标"

    def test_50_concurrent_requests_zero_failure(self, mock_llm_router, auth_client):
        """50 并发请求零失败(10 线程并发)。

        每个线程创建独立 APIClient(避免 force_authenticate 竞争),
        复用 ``auth_client`` 的用户身份。
        Mock DB 写入操作避免 :memory: SQLite 表锁竞争。
        """
        from unittest.mock import patch, MagicMock

        mock_llm_router.generate.return_value = (
            "OK",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        # 提前获取用户对象(避免线程内访问 DB)
        user = auth_client.handler._force_user

        # Mock DB 写入,避免并发 INSERT 导致 SQLite 表锁
        mock_session = MagicMock()
        mock_session.id = 1
        mock_session_create = MagicMock(return_value=mock_session)
        mock_log_create = MagicMock()

        def send_request(i):
            # 每个线程创建独立 client,避免 handler 状态竞争
            from rest_framework.test import APIClient

            client = APIClient()
            client.force_authenticate(user=user)
            return client.post(
                "/api/smart-assistant/chat/",
                data={"query": f"并发第{i}个"},
                format="json",
            )

        # 在线程池外应用 patch,避免多线程竞争
        with patch("smart_assistant.views.chat.SmartAssistantSession.objects") as mock_session_objs, \
             patch("smart_assistant.views.chat.AgentLog.objects") as mock_log_objs:
            mock_session_objs.create = mock_session_create
            mock_log_objs.create = mock_log_create

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(send_request, i) for i in range(50)]
                results = [f.result() for f in as_completed(futures)]

        success = sum(1 for r in results if r.status_code == 200)
        failures = [r for r in results if r.status_code != 200]
        if failures:
            print(f"\n[50 并发] 失败: {[(r.status_code, r.content[:100]) for r in failures[:3]]}")
        print(f"\n[50 并发] 成功 {success}/50")
        assert success == 50, f"50 并发期望全部成功,实际 {success}/50"

    def test_cache_hit_ttfb_under_500ms(self, mock_llm_router, auth_client):
        """缓存命中时第二次响应应 < 500ms(本地 dev 宽松,生产 < 300ms)。

        策略:第一次请求把答案写入缓存(orchestrator 自动 cache_answer),
        第二次相同 query(无 conversation_id)直接命中缓存,跳过 LLM 回答生成。

        注意:answer cache 仅在 ``has_history=False``(无 conversation_history)时检查。
        传入 conversation_id 会加载历史,走 ``else`` 分支跳过缓存。
        因此第二次请求也**不**传 conversation_id。
        """
        mock_llm_router.generate.return_value = (
            "缓存测试回答",
            {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        )

        # Phase 1: 首次请求,预热缓存
        first_resp = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "TTFB 测试"},
            format="json",
        )
        assert first_resp.status_code == 200

        # 重置 mock 调用计数
        mock_llm_router.generate.reset_mock()

        # Phase 2: 缓存命中请求(不传 conversation_id,走 answer cache 路径)
        start = time.perf_counter()
        response = auth_client.post(
            "/api/smart-assistant/chat/",
            data={"query": "TTFB 测试"},
            format="json",
        )
        latency = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        # 缓存命中时 answer 不调 LLM,但 classify_intent + tool_chain_plan 仍会调
        # (has_history=False 时 classify 走缓存,但 tool_chain_plan 内部的
        #  classify_intent 和 generate_tool_chain_plan 自身仍调 LLM)
        answer_cache_calls = mock_llm_router.generate.call_count
        print(f"\n[缓存命中] LLM 调用次数: {answer_cache_calls}")
        print(f"\n[缓存命中 TTFB] {latency:.1f}ms (期望 < 500ms)")
        assert latency < 500, f"缓存命中 TTFB {latency:.1f}ms 超过 500ms"
