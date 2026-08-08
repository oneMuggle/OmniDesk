"""doctor 自检新增 native_tool_calls 检查项测试。

覆盖范围（Task 8）:
- doctor 输出 checks 中包含 ``native_tool_calls`` 名称
- 无激活端点 → warn/no_llm_endpoint（不 500）
- 激活端点且支持 tool_calls → ok，model_capabilities 缓存 native_tool_calls=True
- 激活端点但不支持 tool_calls → ok/warn，缓存 native_tool_calls=False
- 探测异常 → error/endpoint_probe_failed，不 500
- ``isinstance(cap, dict)`` 类型守卫：历史 ``default=list`` 数据兼容

TDD 流程：
- RED 阶段：先跑此文件应 fail（因 checker 未注册）
- GREEN 阶段：实现 ``native_tool_calls_checker`` + 注册到 CHECKERS
"""

from unittest.mock import patch

import pytest

from smart_assistant.models import LlmEndpoint

DOCTOR_URL = "/api/smart-assistant/doctor/"

pytestmark = pytest.mark.django_db


def _checks_by_name(response_json):
    return {c["name"]: c for c in response_json["checks"]}


def _make_endpoint(
    name="probe-端点",
    api_endpoint="http://llm.example.com",
    capabilities=None,
    is_active=True,
):
    """建立 LlmEndpoint（model_capabilities 可注入以模拟历史数据形态）。"""
    return LlmEndpoint.objects.create(
        name=name,
        api_endpoint=api_endpoint,
        api_key="sk-test",
        is_active=is_active,
        model_capabilities=capabilities if capabilities is not None else [],
    )


def _stub_probe_calls(**kwargs):
    """用 patch 替换 ``llm_service.router.LLMRouter.generate_with_tools``。

    checker 通过 ``from llm_service.router import LLMRouter`` 导入类,
    类属性 ``generate_with_tools`` 实际定义在 ``llm_service.router`` 模块,
    所以 patch 目标必须是 ``llm_service.router.LLMRouter.generate_with_tools``
    而不是 ``smart_assistant.views.doctor.LLMRouter.generate_with_tools``(后者不存在)。

    透传 ``return_value`` 或 ``side_effect`` 给 ``unittest.mock.patch``。
    """
    return patch("llm_service.router.LLMRouter.generate_with_tools", **kwargs)


# =============================================================================
# 1. 检查项存在性 + 空场景
# =============================================================================


class TestDoctorNativeToolCallsRegistered:
    """doctor 输出中应存在 native_tool_calls 检查项。"""

    def test_doctor_includes_native_tool_calls_check(self, admin_client, monkeypatch):
        """最简契约:GET /doctor/ 输出 checks 中含 native_tool_calls。"""
        # 屏蔽网络探测,避免空库场景下真实请求
        from smart_assistant.views import doctor as doctor_mod

        def _fake_probe(url, timeout=3):
            return True, "HTTP 200"

        monkeypatch.setattr(doctor_mod, "_probe_http", _fake_probe)

        resp = admin_client.get(DOCTOR_URL)

        assert resp.status_code == 200
        data = resp.json()
        check_names = {c["name"] for c in data["checks"]}
        assert "native_tool_calls" in check_names

    def test_no_active_endpoint_is_warn(self, admin_client, monkeypatch):
        """空库:无激活 LlmEndpoint → warn/no_llm_endpoint,不 500。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )

        by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        item = by_name["native_tool_calls"]
        assert item["status"] == "warn"
        assert item["kind"] == "no_llm_endpoint"
        assert "激活端点" in item["message"] or "无" in item["message"]


# =============================================================================
# 2. 探测成功（端点支持 tool_calls）
# =============================================================================


class TestNativeToolCallsProbeSuccess:
    """激活端点 + 探测返回 tool_calls → ok + 缓存 True。"""

    def test_endpoint_supports_tool_calls_ok_and_caches_true(
        self, admin_client, monkeypatch
    ):
        """探测返回 tool_calls:status=ok,缓存 native_tool_calls=True。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )

        endpoint = _make_endpoint(name="主端点")
        # checker 内部 ``from llm_service.router import LLMRouter``,
        # 类方法 ``generate_with_tools`` 定义在 llm_service.router 模块,
        # 所以 patch 目标必须是 ``llm_service.router.LLMRouter.generate_with_tools``。
        with _stub_probe_calls(
            return_value=(
                "",
                {},
                [{"id": "1", "type": "function", "function": {"name": "_ping", "arguments": "{}"}}],
            )
        ):
            by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        item = by_name["native_tool_calls"]
        assert item["status"] == "ok"
        assert item["kind"] == "ok"
        assert "True" in item["message"] or "支持" in item["message"]

        # 缓存验证
        endpoint.refresh_from_db()
        caps = endpoint.model_capabilities
        # 兼容 list[dict] 与 dict 两种历史/未来形态
        if isinstance(caps, list):
            assert any(
                isinstance(c, dict) and c.get("native_tool_calls") is True
                for c in caps
            )
        elif isinstance(caps, dict):
            assert caps.get("native_tool_calls") is True
        else:
            pytest.fail(f"未预期的 model_capabilities 类型: {type(caps)}")


# =============================================================================
# 3. 探测失败（端点不支持 tool_calls）
# =============================================================================


class TestNativeToolCallsProbeFailure:
    """探测未返回 tool_calls → 缓存 False + 状态文案明确。"""

    def test_endpoint_does_not_support_tool_calls_warns_and_caches_false(
        self, admin_client, monkeypatch
    ):
        """探测返回空 tool_calls:缓存 native_tool_calls=False,文案说明。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )

        endpoint = _make_endpoint(name="次端点")
        with _stub_probe_calls(return_value=("plain text answer", {}, [])):
            by_name = _checks_by_name(admin_client.get(DOCTOR_URL).json())

        item = by_name["native_tool_calls"]
        # 探测本身成功(LLM 响应了),仅能力为 False → 仍归 ok 但 message 提示不支持
        # 或归 warn:取决于实现,但绝不应 500 / error
        assert item["status"] in ("ok", "warn")
        assert "False" in item["message"] or "不支持" in item["message"]

        endpoint.refresh_from_db()
        caps = endpoint.model_capabilities
        if isinstance(caps, list):
            assert any(
                isinstance(c, dict) and c.get("native_tool_calls") is False
                for c in caps
            )
        elif isinstance(caps, dict):
            assert caps.get("native_tool_calls") is False


# =============================================================================
# 4. 探测异常降级
# =============================================================================


class TestNativeToolCallsProbeError:
    """探测异常:error/endpoint_probe_failed,不 500。"""

    def test_probe_exception_yields_error_not_500(self, admin_client, monkeypatch):
        """LLMRouter.generate_with_tools 抛异常 → error/endpoint_probe_failed。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )
        _make_endpoint(name="异常端点")

        with _stub_probe_calls(side_effect=RuntimeError("探测异常-mock")):
            resp = admin_client.get(DOCTOR_URL)

        assert resp.status_code == 200
        by_name = _checks_by_name(resp.json())
        item = by_name["native_tool_calls"]
        assert item["status"] == "error"
        assert item["kind"] == "endpoint_probe_failed"


# =============================================================================
# 5. 历史数据兼容：list[dict] 与 dict 两种形态都能正常读写
# =============================================================================


class TestNativeToolCallsLegacyDataGuard:
    """``isinstance(cap, dict)`` 类型守卫:处理 ``default=list`` 历史数据。"""

    def test_legacy_list_capabilities_dict_entry_is_updated(
        self, admin_client, monkeypatch
    ):
        """已有 ``model_capabilities=[{"native_tool_calls": True, "other": ...}]``:
        追加/更新 ``native_tool_calls`` 字段而不破坏其它键。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )

        endpoint = _make_endpoint(
            name="legacy-list-endpoint",
            capabilities=[{"native_tool_calls": True, "max_context": 8192}],
        )

        with _stub_probe_calls(return_value=("", {}, [])):  # 探测说"不支持",应覆盖旧 True
            admin_client.get(DOCTOR_URL)

        endpoint.refresh_from_db()
        caps = endpoint.model_capabilities
        assert isinstance(caps, list)
        # 找到那个 dict,确认 native_tool_calls 已被新探测结果覆盖
        target = next(
            c for c in caps if isinstance(c, dict) and "native_tool_calls" in c
        )
        assert target["native_tool_calls"] is False
        # 其它字段保留
        assert target.get("max_context") == 8192

    def test_legacy_empty_list_capabilities_dict_entry_is_appended(
        self, admin_client, monkeypatch
    ):
        """``model_capabilities=[]`` 空列表:追加 ``{"native_tool_calls": ...}``。"""
        from smart_assistant.views import doctor as doctor_mod

        monkeypatch.setattr(
            doctor_mod,
            "_probe_http",
            lambda url, timeout=3: (True, "HTTP 200"),
        )

        endpoint = _make_endpoint(name="empty-cap-endpoint", capabilities=[])

        with _stub_probe_calls(
            return_value=(
                "",
                {},
                [{"id": "1", "type": "function", "function": {"name": "_ping", "arguments": "{}"}}],
            )
        ):
            admin_client.get(DOCTOR_URL)

        endpoint.refresh_from_db()
        caps = endpoint.model_capabilities
        assert isinstance(caps, list)
        assert any(
            isinstance(c, dict) and c.get("native_tool_calls") is True
            for c in caps
        )
