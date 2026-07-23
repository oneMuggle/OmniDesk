"""验证 13 个工具都实现 build_base_queryset + _scope_self,用于启动时校验"""
import pytest
from smart_assistant.tools.registry import ToolRegistry


EXPECTED_TOOLS = [
    "schedule_query",
    "meeting_room_query",
    "announcement_query",
    "memo_query",
    "personnel_query",
    "document_search",  # DocumentTool uses intent_type="document_search" (not "document_query")
    "event_query",
    "news_search",      # NewsTool uses intent_type="news_search" (not "news_query")
    "project_status",   # ProjectTool uses intent_type="project_status" (not "project_query")
    "sensor_query",
    "compliance_query",
    "external_link_query",
    "knowledge_qa",     # RAGTool uses intent_type="knowledge_qa" (not "rag_query")
]


@pytest.mark.parametrize("intent_type", EXPECTED_TOOLS)
def test_tool_implements_build_base_queryset(intent_type):
    tool = ToolRegistry.get_tool(intent_type)
    assert tool is not None, f"Tool {intent_type} not registered"
    assert hasattr(tool, "build_base_queryset"), f"{intent_type} missing build_base_queryset"
    qs = tool.build_base_queryset()
    assert qs is not None


@pytest.mark.parametrize("intent_type", EXPECTED_TOOLS)
def test_tool_implements_scope_self(intent_type, regular_user_obj):
    tool = ToolRegistry.get_tool(intent_type)
    assert tool is not None
    assert hasattr(tool, "_scope_self"), f"{intent_type} missing _scope_self"
    # 调一次不报错即视为通过(具体行为由各工具单独测试)
    # 注:brief 原使用 type("U", (), {})() 作为占位 user,但 Django FK lookup 在
    # .filter(user=<bare>) 时会立即调用 int(value) 验证,无 pk 属性的对象会 TypeError;
    # Mock() 也不行 —— 默认所有属性返回 Mock,会触发 Django 的 resolve_expression 检查。
    # 故改用 regular_user_obj 真实 CustomUser,既满足 FK lookup 又无需手工构造 mock。
    from smart_assistant.scope import SmartAssistantScope
    from smart_assistant.tools.tool_context import ToolContext
    ctx = ToolContext(user=regular_user_obj, scope=SmartAssistantScope.SELF)
    base_qs = tool.build_base_queryset()
    result = tool._scope_self(base_qs, ctx)
    assert result is not None