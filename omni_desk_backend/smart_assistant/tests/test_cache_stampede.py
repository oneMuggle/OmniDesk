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
