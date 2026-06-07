"""Tests for smart_assistant.agent.prompt_builder — 覆盖率补齐.

目标:agent/prompt_builder.py 24% → 80%+。
覆盖 format_history 函数(全部 16 行未覆盖) + 4 个 prompt 常量的格式契约。
"""

import pytest

from smart_assistant.agent.prompt_builder import (
    SYSTEM_PROMPT,
    INTENT_PROMPT,
    TOOL_CHAIN_PROMPT,
    TOOL_CHAIN_SYNTHESIS_PROMPT,
    format_history,
)


# =============================================================================
# format_history
# =============================================================================


class TestFormatHistory:
    """format_history: 将对话历史格式化为 LLM prompt 上下文."""

    def test_empty_history_returns_empty_string(self):
        """空历史 → 返回空字符串."""
        assert format_history([]) == ""

    def test_none_history_returns_empty_string(self):
        """None 历史 → 返回空字符串."""
        assert format_history(None) == ""

    def test_short_history_includes_all_messages(self):
        """短于 max_turns*2 的历史 → 全部包含."""
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好,我是智能助手"},
        ]
        result = format_history(history, max_turns=5)
        assert "用户: 你好" in result
        assert "助手: 您好,我是智能助手" in result
        assert result.startswith("\n\n对话历史：\n")
        assert result.endswith("\n\n当前问题：")

    def test_long_history_truncated_to_max_turns(self):
        """超过 max_turns*2 的历史 → 只保留最近 N 轮."""
        history = []
        for i in range(20):
            history.append({"role": "user", "content": f"旧问题{i}"})
            history.append({"role": "assistant", "content": f"旧回答{i}"})
        # 追加最近 2 轮
        history.append({"role": "user", "content": "最近问题"})
        history.append({"role": "assistant", "content": "最近回答"})

        result = format_history(history, max_turns=2)
        # 旧内容应被截断
        assert "旧问题0" not in result
        assert "旧回答0" not in result
        # 最近 2 轮保留
        assert "最近问题" in result
        assert "最近回答" in result

    def test_user_role_prefix(self):
        """role=user → 显示'用户'前缀."""
        history = [{"role": "user", "content": "测试"}]
        assert "用户: 测试" in format_history(history)

    def test_assistant_role_prefix(self):
        """role=assistant → 显示'助手'前缀."""
        history = [{"role": "assistant", "content": "好的"}]
        assert "助手: 好的" in format_history(history)

    def test_other_role_treated_as_assistant(self):
        """非 user 角色 → 默认按助手处理."""
        history = [{"role": "system", "content": "sys"}]
        assert "助手: sys" in format_history(history)

    def test_missing_content_uses_empty_string(self):
        """消息无 content 字段 → 使用空字符串."""
        history = [{"role": "user"}]  # 缺 content
        result = format_history(history)
        assert "用户: " in result

    def test_thinking_tags_stripped(self):
        """<thinking>...</thinking> 标签内容被去除."""
        history = [
            {"role": "assistant", "content": "好的<thinking>这是内部推理</thinking>答案"},
        ]
        result = format_history(history)
        assert "这是内部推理" not in result
        assert "好的" in result
        assert "答案" in result

    def test_partial_thinking_tags_kept_as_is(self):
        """只有起始标签但无结束标签 → 保留原内容(不破坏文本)."""
        history = [
            {"role": "assistant", "content": "普通回答<thinking>未闭合"},
        ]
        result = format_history(history)
        # 没有 think_end 时,find 返回 -1,条件不满足,内容保留
        assert "普通回答" in result
        assert "未闭合" in result

    def test_content_with_whitespace_stripped(self):
        """内容前后空白被 strip."""
        history = [
            {"role": "user", "content": "  带空白的文本  "},
        ]
        result = format_history(history)
        assert "用户: 带空白的文本" in result
        assert "  带空白的文本  " not in result

    def test_max_turns_one_keeps_last_two_messages(self):
        """max_turns=1 → 保留最近 2 条(1 轮=user+assistant)."""
        history = [
            {"role": "user", "content": "old_q"},
            {"role": "assistant", "content": "old_a"},
            {"role": "user", "content": "new_q"},
            {"role": "assistant", "content": "new_a"},
        ]
        result = format_history(history, max_turns=1)
        assert "old_q" not in result
        assert "old_a" not in result
        assert "new_q" in result
        assert "new_a" in result

    def test_messages_joined_by_newline(self):
        """多条消息以换行符连接."""
        history = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
        ]
        result = format_history(history)
        # parts 之间用 \n 连接
        assert "用户: 问题1\n助手: 回答1" in result


# =============================================================================
# 常量模板格式契约(确保模板占位符正确)
# =============================================================================


class TestPromptConstants:
    """4 个 prompt 常量应包含正确的占位符与说明文字."""

    def test_system_prompt_has_placeholders(self):
        """SYSTEM_PROMPT 包含 4 个占位符."""
        assert "{user_query}" in SYSTEM_PROMPT
        assert "{intent}" in SYSTEM_PROMPT
        assert "{tool_name}" in SYSTEM_PROMPT
        assert "{tool_result}" in SYSTEM_PROMPT

    def test_system_prompt_chinese_natural(self):
        """SYSTEM_PROMPT 是中文 prompt,包含'智能助手'."""
        assert "智能助手" in SYSTEM_PROMPT

    def test_intent_prompt_has_tool_schemas_placeholder(self):
        """INTENT_PROMPT 包含 {tool_schemas} 占位符."""
        assert "{tool_schemas}" in INTENT_PROMPT

    def test_intent_prompt_lists_intent_types(self):
        """INTENT_PROMPT 列出常见意图类型关键词."""
        assert "schedule_query" in INTENT_PROMPT
        assert "personnel_query" in INTENT_PROMPT
        assert "knowledge_qa" in INTENT_PROMPT
        assert "general_chat" in INTENT_PROMPT

    def test_tool_chain_prompt_has_placeholders(self):
        """TOOL_CHAIN_PROMPT 包含 {tool_schemas} 和 {user_query}."""
        assert "{tool_schemas}" in TOOL_CHAIN_PROMPT
        assert "{user_query}" in TOOL_CHAIN_PROMPT

    def test_tool_chain_synthesis_prompt_has_placeholders(self):
        """TOOL_CHAIN_SYNTHESIS_PROMPT 包含 {user_query} 和 {tool_results}."""
        assert "{user_query}" in TOOL_CHAIN_SYNTHESIS_PROMPT
        assert "{tool_results}" in TOOL_CHAIN_SYNTHESIS_PROMPT
