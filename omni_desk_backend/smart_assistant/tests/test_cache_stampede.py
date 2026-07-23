"""缓存击穿防护测试 — singleflight 单飞模式。

Task 3 of feat/sa-perf-ux: 同一时刻同 key 只查一次 DB/LLM。
"""
import threading
import time

from smart_assistant.cache import singleflight_get_or_set


class TestSingleflight:
    def test_concurrent_calls_only_execute_loader_once(self):
        """50 个并发同 key 调用,loader 只执行 1 次。"""
        call_count = {"n": 0}
        call_lock = threading.Lock()

        def slow_loader():
            with call_lock:
                call_count["n"] += 1
            time.sleep(0.1)
            return "loaded_value"

        def worker():
            return singleflight_get_or_set("test_key", slow_loader, ttl=60)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert call_count["n"] == 1, f"loader 期望调用 1 次,实际 {call_count['n']} 次"

    def test_sequential_calls_each_invoke_loader(self):
        """顺序调用,cache 命中后 loader 不再执行。"""
        call_count = {"n": 0}

        def loader():
            call_count["n"] += 1
            return f"v{call_count['n']}"

        v1 = singleflight_get_or_set("seq_key", loader, ttl=60)
        assert v1 == "v1"
        # cache hit, 不调 loader
        v2 = singleflight_get_or_set("seq_key", lambda: "v_new", ttl=60)
        assert v2 == "v1"
        assert call_count["n"] == 1

    def test_exception_propagates_to_all_waiters(self):
        """leader 的 loader 抛异常时,所有等待者也应收该异常。"""
        call_count = {"n": 0}
        call_lock = threading.Lock()
        exceptions_caught = []
        exceptions_lock = threading.Lock()

        def failing_loader():
            with call_lock:
                call_count["n"] += 1
            time.sleep(0.1)  # 模拟延迟,确保其他线程进入等待
            raise ValueError("loader 失败")

        def worker():
            try:
                singleflight_get_or_set("error_key", failing_loader, ttl=60)
            except ValueError as e:
                with exceptions_lock:
                    exceptions_caught.append(str(e))

        # 启动 10 个并发线程
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # loader 应只调用 1 次(leader)
        assert call_count["n"] == 1, f"loader 期望调用 1 次,实际 {call_count['n']} 次"
        # 所有 10 个线程都应捕获到异常
        assert len(exceptions_caught) == 10, f"期望 10 个线程捕获异常,实际 {len(exceptions_caught)}"
        # 所有异常消息应一致
        assert all(msg == "loader 失败" for msg in exceptions_caught)
