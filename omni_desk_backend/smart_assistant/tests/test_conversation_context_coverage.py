"""Tests for smart_assistant.agent.conversation_context — 覆盖率补齐.

目标:agent/conversation_context.py 37% → 80%+。
覆盖 7 个核心函数:estimate_tokens, format_history_for_prompt,
build_messages_with_history, _select_recent_messages, _remove_thinking_tags,
should_summarize, count_turns。
"""

import pytest

from smart_assistant.agent.conversation_context import (
    estimate_tokens,
    format_history_for_prompt,
    build_messages_with_history,
    _select_recent_messages,
    _remove_thinking_tags,
    should_summarize,
    count_turns,
    SOFT_TOKEN_LIMIT,
    HARD_TOKEN_LIMIT,
)


# =============================================================================
# estimate_tokens
# =============================================================================


class TestEstimateTokens:
    """estimate_tokens: 中文 ~1.5 字/token, 英文/数字 ~4 字/token."""

    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_pure_chinese(self):
        # 12 个中文字符 → 12/1.5 = 8 tokens(int 截断)
        assert estimate_tokens("你好世界你好世界你好世界") == 8

    def test_pure_english(self):
        # 20 个英文字符 → 20/4 = 5 tokens
        assert estimate_tokens("helloworldhelloworld") == 5

    def test_pure_digits(self):
        # 8 个数字 → 8/4 = 2 tokens
        assert estimate_tokens("12345678") == 2

    def test_mixed_chinese_and_english(self):
        # 2 中文字符 + 8 英文字符 → 2/1.5 + 8/4 = 1.33 + 2 = 3.33 → int = 3
        assert estimate_tokens("你好abc1234") == 3

    def test_chinese_punctuation_counts_as_other(self):
        # "你好,世界" = 2 中文字符 + 2 标点(其他)
        # 2/1.5 + 2/4 = 1.33 + 0.5 = 1.83 → int = 1
        result = estimate_tokens("你好,世界")
        assert result >= 1


# =============================================================================
# format_history_for_prompt
# =============================================================================


class TestFormatHistoryForPrompt:
    """format_history_for_prompt: 文本前缀格式化,保留 max_turns 轮。"""

    def test_empty_history_returns_empty_string(self):
        assert format_history_for_prompt([]) == ""

    def test_single_user_message(self):
        history = [{"role": "user", "content": "你好"}]
        result = format_history_for_prompt(history)
        assert "用户: 你好" in result
        assert "对话历史" in result
        assert "当前问题" in result

    def test_user_and_assistant_messages(self):
        history = [
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "回答"},
        ]
        result = format_history_for_prompt(history)
        assert "用户: 问题" in result
        assert "助手: 回答" in result

    def test_truncates_to_max_turns(self):
        # 真实对话结构:6 轮交替 user/assistant,max_turns=2 → 保留最近 2 轮(4 条)
        history = []
        for i in range(6):
            history.append({"role": "user", "content": f"旧问题{i}"})
            history.append({"role": "assistant", "content": f"旧回答{i}"})
        result = format_history_for_prompt(history, max_turns=2)
        # 保留最近 2 轮(4 条) = 第 5 轮和第 6 轮
        assert "旧问题4" in result
        assert "旧回答4" in result
        assert "旧问题5" in result
        assert "旧回答5" in result
        # 最早的轮次不应出现
        assert "旧问题0" not in result
        assert "旧回答0" not in result

    def test_strips_thinking_tags_from_content(self):
        # assistant 消息内含 <thinking>...</thinking> 应被剥离
        history = [
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "回答<thinking>内部推理</thinking>继续"},
        ]
        result = format_history_for_prompt(history)
        # 内部推理被剥离
        assert "内部推理" not in result
        assert "回答" in result
        assert "继续" in result

    def test_thinking_only_content_renders_empty_assistant_line(self):
        # content 全部是 thinking 标签 → 剥离后为空
        # 实际行为:仍会 append "助手: " 空行(不会跳过)
        history = [
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "<thinking>全部是思考</thinking>"},
        ]
        result = format_history_for_prompt(history)
        # thinking 内容被剥离
        assert "全部是思考" not in result
        # 助手行存在(只是内容为空)
        assert "用户: 问题" in result
        # 验证剥离后的内容是空字符串 - 体现 thinking 标签清理生效
        assert "助手: " in result  # 存在助手行,content 已空

    def test_unknown_role_defaults_to_assistant_label(self):
        # role 不是 "user" 时显示 "助手"
        history = [{"role": "system", "content": "sys"}]
        result = format_history_for_prompt(history)
        assert "助手: sys" in result


# =============================================================================
# build_messages_with_history
# =============================================================================


class TestBuildMessagesWithHistory:
    """build_messages_with_history: 构建 LLM messages 数组。"""

    def test_basic_user_only(self):
        msgs = build_messages_with_history(
            system_prompt="你是助手",
            user_content="问题",
            history=[],
        )
        assert len(msgs) == 2
        assert msgs[0] == {"role": "system", "content": "你是助手"}
        assert msgs[1] == {"role": "user", "content": "问题"}

    def test_empty_system_prompt_skipped(self):
        msgs = build_messages_with_history(
            system_prompt="",
            user_content="问题",
            history=[],
        )
        # 没用 system message
        assert msgs[0] == {"role": "user", "content": "问题"}

    def test_summary_injects_extra_system_message(self):
        msgs = build_messages_with_history(
            system_prompt="你是助手",
            user_content="新问题",
            history=[],
            summary_text="之前的摘要",
        )
        # system + summary system + user
        assert len(msgs) == 3
        assert msgs[0]["role"] == "system"
        assert "你是助手" in msgs[0]["content"]
        assert msgs[1]["role"] == "system"
        assert "之前的摘要" in msgs[1]["content"]
        assert msgs[2] == {"role": "user", "content": "新问题"}

    def test_history_messages_appended_in_order(self):
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        msgs = build_messages_with_history(
            system_prompt="sys",
            user_content="q2",
            history=history,
        )
        # sys + user(q1) + assistant(a1) + user(q2)
        assert len(msgs) == 4
        assert msgs[1] == {"role": "user", "content": "q1"}
        assert msgs[2] == {"role": "assistant", "content": "a1"}
        assert msgs[3] == {"role": "user", "content": "q2"}


# =============================================================================
# _select_recent_messages — 软/硬 token 限制
# =============================================================================


class TestSelectRecentMessages:
    """_select_recent_messages: 根据 token 限制选择历史消息。"""

    def test_empty_history_returns_empty(self):
        assert _select_recent_messages([]) == []

    def test_small_history_within_soft_limit_returns_all(self):
        # 每条 10 字符英文 → 10/4 = 2 tokens,3 条 = 6 tokens << SOFT
        history = [
            {"role": "user", "content": "x" * 10},
            {"role": "assistant", "content": "y" * 10},
            {"role": "user", "content": "z" * 10},
        ]
        result = _select_recent_messages(history)
        assert len(result) == 3
        assert result == history

    def test_large_history_truncated_by_hard_limit(self):
        # 构造单条超大消息,触发硬限制
        # 单条 50000 字符英文 → 12500 tokens > HARD(6000)
        # 应立即 break 返回空
        history = [
            {"role": "user", "content": "a" * 50000},
            {"role": "assistant", "content": "b" * 50000},
        ]
        result = _select_recent_messages(history)
        # 第一条就超 HARD,selected 为空
        assert result == []

    def test_hard_limit_keeps_recent_messages_until_exceeded(self):
        # 构造:6 条 × 1000 tokens = 6000 = HARD_LIMIT
        # 反向累加全部能装下(total=6000 不超硬限)
        history = [
            {"role": "user", "content": "a" * 4000},          # 1000 tokens
            {"role": "assistant", "content": "b" * 4000},     # 1000 tokens
            {"role": "user", "content": "c" * 4000},          # 1000 tokens
            {"role": "assistant", "content": "d" * 4000},     # 1000 tokens
            {"role": "user", "content": "e" * 4000},          # 1000 tokens
            {"role": "assistant", "content": "f" * 4000},     # 1000 tokens
        ]
        # total = 6000 = HARD_LIMIT, 走硬限制分支
        # 反向累加:6000 tokens 全部装下(6000 > 6000 严格 > 才 break)
        result = _select_recent_messages(history)
        # 应全部保留
        assert len(result) == 6

    def test_hard_limit_breaks_when_exceeded(self):
        # 5 条 × 3000 tokens = 15000 > HARD
        # 反向累加:最后一条 3000,前一条累计 6000 仍 ok,第三条累计 9000 > 6000 break
        history = [
            {"role": "user", "content": "a" * 12000},         # 3000 tokens
            {"role": "assistant", "content": "b" * 12000},    # 3000 tokens
            {"role": "user", "content": "c" * 12000},         # 3000 tokens
            {"role": "assistant", "content": "d" * 12000},    # 3000 tokens
            {"role": "user", "content": "e" * 12000},         # 3000 tokens
        ]
        result = _select_recent_messages(history)
        # 反向:e(3000)→ d(累计6000,6000>6000 false 继续)→ c(9000>6000 break)
        # selected = [d, e]
        assert len(result) == 2
        assert result[0]["content"] == "d" * 12000
        assert result[1]["content"] == "e" * 12000


# =============================================================================
# _remove_thinking_tags
# =============================================================================


class TestRemoveThinkingTags:
    """_remove_thinking_tags: 循环清理 <thinking>...</thinking> 块。"""

    def test_no_thinking_tag_returns_unchanged(self):
        assert _remove_thinking_tags("hello world") == "hello world"

    def test_single_thinking_block_removed(self):
        result = _remove_thinking_tags("before<thinking>内部推理</thinking>after")
        assert "内部推理" not in result
        assert result == "beforeafter"

    def test_multiple_thinking_blocks_all_removed(self):
        result = _remove_thinking_tags(
            "a<thinking>1</thinking>b<thinking>2</thinking>c"
        )
        assert result == "abc"

    def test_unclosed_thinking_tag_kept_as_is(self):
        # 没有 </thinking> → 不应破坏内容
        content = "before<thinking>未闭合"
        result = _remove_thinking_tags(content)
        # while 循环中第二次 find <thinking> 时,从前面 start 之后开始找,没找到 break
        # 第一次 start=6,end=-1,break
        assert result == "before<thinking>未闭合"

    def test_thinking_with_close_tag_removed(self):
        # 正常闭合的标签应被清理
        result = _remove_thinking_tags("text<thinking>内部</thinking>more")
        assert "内部" not in result
        assert "more" in result


# =============================================================================
# should_summarize
# =============================================================================


class TestShouldSummarize:
    """should_summarize: 当历史超 SOFT_TOKEN_LIMIT 且无摘要时触发摘要。"""

    def test_existing_summary_skips_summarization(self):
        # 已有 summary_text → 不应触发
        history = [{"role": "user", "content": "a" * 50000}]
        assert should_summarize(history, summary_text="已有摘要") is False

    def test_oversized_history_without_summary_triggers(self):
        # 单条 50000 字符 = 12500 tokens > SOFT(3000),无 summary → True
        history = [{"role": "user", "content": "a" * 50000}]
        assert should_summarize(history) is True

    def test_small_history_does_not_trigger(self):
        # 6 tokens < SOFT → False
        history = [{"role": "user", "content": "a" * 24}]
        assert should_summarize(history) is False

    def test_empty_history_does_not_trigger(self):
        assert should_summarize([]) is False


# =============================================================================
# count_turns
# =============================================================================


class TestCountTurns:
    """count_turns: 数 user 角色的消息数。"""

    def test_empty_history_returns_zero(self):
        assert count_turns([]) == 0

    def test_single_user_message_returns_one(self):
        history = [{"role": "user", "content": "q"}]
        assert count_turns(history) == 1

    def test_user_and_assistant_counts_only_user(self):
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        assert count_turns(history) == 2

    def test_message_without_role_not_counted(self):
        # role 字段缺失或非 "user" 的不计入
        history = [
            {"role": "user", "content": "q1"},
            {"content": "no role"},  # role 缺失
            {"role": "system", "content": "sys"},
        ]
        assert count_turns(history) == 1
