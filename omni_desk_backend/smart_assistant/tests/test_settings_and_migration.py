"""原生 Function Calling 协议 settings + 模型字段迁移验证测试

L1 spec:docs/superpowers/specs/2026-08-06-native-function-calling-design.md
本文件覆盖 Task 1:settings 默认值 + AgentLog / LlmEndpoint 字段 + 迁移。
"""

from django.conf import settings

from smart_assistant.models import AgentLog, LlmEndpoint


# === settings 默认值 ===

def test_use_native_tool_calls_default_true():
    """L1 默认开启原生 Function Calling(可通过 env var 关)"""
    assert settings.USE_NATIVE_TOOL_CALLS is True


def test_max_tool_calls_rounds_default_3():
    """单会话内最大 tool_calls 轮数防无限循环"""
    assert settings.MAX_TOOL_CALLS_ROUNDS == 3


def test_tool_calls_timeout_default_30():
    """单次工具调用超时(秒),失败则走降级路径"""
    assert settings.TOOL_CALLS_TIMEOUT_SECONDS == 30


# === AgentLog 决策日志字段 ===

def test_agentlog_has_tool_call_fields():
    """tool_call_path / tool_calls_meta / tool_calls_rounds 三字段必须存在"""
    field_names = {f.name for f in AgentLog._meta.get_fields()}
    assert "tool_call_path" in field_names
    assert "tool_calls_meta" in field_names
    assert "tool_calls_rounds" in field_names


# === LlmEndpoint 端点能力探测字段 ===

def test_llmendpoint_has_model_capabilities():
    """端点模型能力缓存字段(由 doctor.py 检测写入)"""
    field_names = {f.name for f in LlmEndpoint._meta.get_fields()}
    assert "model_capabilities" in field_names
