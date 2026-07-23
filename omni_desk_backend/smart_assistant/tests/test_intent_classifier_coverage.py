"""Tests for smart_assistant.agent.intent_classifier — 覆盖率补齐.

目标:agent/intent_classifier.py 46% → 80%+。
覆盖 4 个函数:build_intent_prompt, classify_intent,
generate_answer, generate_answer_stream, generate_general_answer。
"""

import pytest

from smart_assistant.agent.intent_classifier import (
    build_intent_prompt,
    classify_intent,
    generate_answer,
    generate_answer_stream,
    generate_general_answer,
)


# =============================================================================
# build_intent_prompt
# =============================================================================


class TestBuildIntentPrompt:
    """build_intent_prompt: 把 schema 列表拼到 INTENT_PROMPT 模板."""

    def test_single_schema(self):
        """单个 schema → 渲染到模板."""
        schemas = [{"name": "schedule_query", "description": "排班查询"}]
        result = build_intent_prompt(schemas)
        assert "schedule_query" in result
        assert "排班查询" in result
        # 模板占位符被替换
        assert "{tool_schemas}" not in result

    def test_multiple_schemas(self):
        """多个 schema → 多行 schema 文本."""
        schemas = [
            {"name": "schedule_query", "description": "排班查询"},
            {"name": "personnel_query", "description": "人员查询"},
        ]
        result = build_intent_prompt(schemas)
        assert "schedule_query" in result
        assert "personnel_query" in result
        assert "排班查询" in result
        assert "人员查询" in result

    def test_empty_schemas(self):
        """空 schema 列表 → 模板保留意图类型说明(无具体 schema 行)."""
        result = build_intent_prompt([])
        # 空 schema 时,join 是空字符串,模板其他部分保留
        assert "schedule_query" in result  # 模板中硬编码的意图名
        assert "{tool_schemas}" not in result


# =============================================================================
# classify_intent
# =============================================================================


class TestClassifyIntent:
    """classify_intent: 用 LLM 分类意图."""

    def test_basic_classification(self, mock_llm_router):
        """无 history 时,基本意图分类."""
        mock_llm_router.generate.return_value = ("schedule_query", {"total_tokens": 10})
        result = classify_intent("明天谁值班?", [{"name": "schedule_query", "description": "排班"}])
        assert result == "schedule_query"
        assert mock_llm_router.generate.called

    def test_classification_normalizes_response(self, mock_llm_router):
        """响应被标准化:去空格、转小写、空格→下划线、连字符→下划线."""
        mock_llm_router.generate.return_value = ("  Schedule Query  ", {})
        result = classify_intent("test", [])
        assert result == "schedule_query"

    def test_classification_with_hyphen_to_underscore(self, mock_llm_router):
        """连字符被替换为下划线."""
        mock_llm_router.generate.return_value = ("knowledge-qa", {})
        result = classify_intent("test", [])
        assert result == "knowledge_qa"

    def test_classification_with_history(self, mock_llm_router):
        """有 history 时,前缀拼接历史."""
        mock_llm_router.generate.return_value = ("general_chat", {})
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好"},
        ]
        result = classify_intent("今天怎么样?", [], history=history)
        assert result == "general_chat"
        # 检查 prompt 中包含历史
        call_args = mock_llm_router.generate.call_args
        prompt = call_args.kwargs.get("prompt", "")
        assert "对话历史" in prompt

    def test_classification_fallback_on_exception(self, mock_llm_router):
        """LLM 抛异常时,fallback 到 general_chat."""
        mock_llm_router.generate.side_effect = Exception("LLM error")
        result = classify_intent("test", [])
        assert result == "general_chat"

    def test_classification_empty_history_treated_as_no_history(self, mock_llm_router):
        """空 history 列表走 else 分支."""
        mock_llm_router.generate.return_value = ("general_chat", {})
        # history=[] 时, `if history and len(history) > 0` 为 False
        result = classify_intent("test", [], history=[])
        assert result == "general_chat"


# =============================================================================
# generate_answer
# =============================================================================


class TestGenerateAnswer:
    """generate_answer: 把工具结果转化为自然语言回答."""

    def test_basic_answer(self, mock_llm_router):
        """基本回答生成."""
        mock_llm_router.generate.return_value = ("明天张三值班。", {"total_tokens": 20})
        answer, usage = generate_answer(
            user_query="明天谁值班?",
            intent="schedule_query",
            tool_name="schedule_query",
            tool_result={"found": True, "schedules": []},
        )
        assert answer == "明天张三值班。"
        assert usage == {"total_tokens": 20}
        # 检查调用 messages 形式
        call_args = mock_llm_router.generate.call_args
        assert "messages" in call_args.kwargs
        # system prompt 应包含 user_query, intent, tool_name
        system_msg = call_args.kwargs["messages"][0]
        assert system_msg["role"] == "system"
        assert "明天谁值班?" in system_msg["content"]

    def test_answer_with_none_tool_result(self, mock_llm_router):
        """tool_result 为 None 时,使用'无结果'占位."""
        mock_llm_router.generate.return_value = ("没有相关信息。", {})
        answer, usage = generate_answer(
            user_query="test",
            intent="general_chat",
            tool_name="schedule_query",
            tool_result=None,
        )
        assert answer == "没有相关信息。"
        # 检查 system prompt 包含"无结果"
        call_args = mock_llm_router.generate.call_args
        system_content = call_args.kwargs["messages"][0]["content"]
        assert "无结果" in system_content

    def test_answer_with_history(self, mock_llm_router):
        """history 非空时,加入 messages."""
        mock_llm_router.generate.return_value = ("answer", {})
        history = [
            {"role": "user", "content": "old_q"},
            {"role": "assistant", "content": "old_a"},
        ]
        answer, usage = generate_answer(
            user_query="new_q",
            intent="general_chat",
            tool_name="",
            tool_result={},
            history=history,
        )
        # messages 应包含 system + history + user
        call_args = mock_llm_router.generate.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) >= 3
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles
        assert "assistant" in roles

    def test_answer_exception_returns_error_message(self, mock_llm_router):
        """LLM 抛异常时,返回错误消息 + usage=None."""
        mock_llm_router.generate.side_effect = Exception("API down")
        answer, usage = generate_answer(
            user_query="test",
            intent="general_chat",
            tool_name="x",
            tool_result={"found": True},
        )
        assert "回答生成失败" in answer
        assert "API down" in answer
        assert usage is None


# =============================================================================
# generate_answer_stream
# =============================================================================


class TestGenerateAnswerStream:
    """generate_answer_stream: 流式生成回答."""

    def test_stream_yields_chunks(self, mock_llm_router):
        """流式生成时逐 chunk yield."""

        def fake_stream(**kwargs):
            for chunk in ["你", "好", "世界"]:
                yield chunk

        mock_llm_router.generate.side_effect = fake_stream
        chunks = list(generate_answer_stream(
            user_query="hi",
            intent="general_chat",
            tool_name="x",
            tool_result={"found": True},
        ))
        assert chunks == ["你", "好", "世界"]

    def test_stream_with_history(self, mock_llm_router):
        """流式带 history."""

        def fake_stream(**kwargs):
            yield "chunk"

        mock_llm_router.generate.side_effect = fake_stream
        history = [{"role": "user", "content": "old"}]
        chunks = list(generate_answer_stream(
            user_query="new",
            intent="general_chat",
            tool_name="x",
            tool_result={},
            history=history,
        ))
        assert chunks == ["chunk"]

    def test_stream_exception_yields_error_marker(self, mock_llm_router):
        """流式抛异常时,yield 错误标记."""

        def fake_stream_error(**kwargs):
            raise Exception("stream fail")
            yield  # 保持生成器语法(永远不执行)

        mock_llm_router.generate.side_effect = fake_stream_error
        chunks = list(generate_answer_stream(
            user_query="test",
            intent="general_chat",
            tool_name="x",
            tool_result={"found": True},
        ))
        assert len(chunks) == 1
        assert "[错误]" in chunks[0]
        assert "stream fail" in chunks[0]

    def test_stream_with_none_tool_result(self, mock_llm_router):
        """tool_result=None 时,使用'无结果'占位."""

        def fake_stream(**kwargs):
            yield "ok"

        mock_llm_router.generate.side_effect = fake_stream
        chunks = list(generate_answer_stream(
            user_query="test",
            intent="general_chat",
            tool_name="x",
            tool_result=None,
        ))
        # 检查 messages 中 system prompt 包含"无结果"
        call_args = mock_llm_router.generate.call_args
        assert "无结果" in call_args.kwargs["messages"][0]["content"]


# =============================================================================
# generate_general_answer
# =============================================================================


class TestGenerateGeneralAnswer:
    """generate_general_answer: 通用对话回答(无工具)."""

    def test_general_answer_with_history(self, mock_llm_router):
        """有 history 时,使用 messages 形式."""
        mock_llm_router.generate.return_value = ("一般回答", {"total_tokens": 15})
        history = [{"role": "user", "content": "旧问题"}]
        answer, usage = generate_general_answer("新问题", history=history)
        assert answer == "一般回答"
        assert usage == {"total_tokens": 15}
        # messages 形式调用
        call_args = mock_llm_router.generate.call_args
        assert "messages" in call_args.kwargs

    def test_general_answer_without_history(self, mock_llm_router):
        """无 history 时,使用 prompt 形式."""
        mock_llm_router.generate.return_value = ("回答", {})
        answer, usage = generate_general_answer("问题")
        assert answer == "回答"
        # prompt 形式调用
        call_args = mock_llm_router.generate.call_args
        assert "prompt" in call_args.kwargs
        assert call_args.kwargs["prompt"] == "问题"

    def test_general_answer_empty_history_uses_prompt_form(self, mock_llm_router):
        """空 history 列表走 prompt 形式."""
        mock_llm_router.generate.return_value = ("answer", {})
        generate_general_answer("q", history=[])
        call_args = mock_llm_router.generate.call_args
        # `if history and len(history) > 0` → 空 history 为 False → 走 prompt 形式
        assert "prompt" in call_args.kwargs

    def test_general_answer_exception_returns_error(self, mock_llm_router):
        """异常时返回错误消息 + usage=None."""
        mock_llm_router.generate.side_effect = Exception("fail")
        answer, usage = generate_general_answer("q")
        assert "回答生成失败" in answer
        assert "fail" in answer
        assert usage is None
