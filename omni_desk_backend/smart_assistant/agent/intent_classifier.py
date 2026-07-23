import re

from llm_service.router import get_router
from .prompt_builder import INTENT_PROMPT, SYSTEM_PROMPT, TOOL_EMPTY_PROMPT
from .conversation_context import build_messages_with_history, format_history_for_prompt

# 匹配 <think>...</think> 或 <think>...</think> 块（含中间内容）
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.IGNORECASE)


def _strip_think_tags(response: str) -> str:
    """去除 LLM 响应中的 <think>...</think> 块，保留正文。"""
    cleaned = _THINK_RE.sub("", response)
    return cleaned.strip()


def build_intent_prompt(schemas: list) -> str:
    """构建意图分类提示词"""
    schema_text = "\n".join([f"- {s['name']}: {s['description']}" for s in schemas])
    return INTENT_PROMPT.replace("{tool_schemas}", schema_text)


def classify_intent(query: str, schemas: list, history: list = None) -> str:
    """使用 LLM 进行意图分类，支持多轮上下文"""
    prompt = build_intent_prompt(schemas)
    client = get_router()
    try:
        # 使用 messages 数组方式，传入历史
        if history and len(history) > 0:
            history_prefix = format_history_for_prompt(history)
            full_content = history_prefix + f"用户问题: {query}\n\n{prompt}"
        else:
            full_content = f"用户问题: {query}\n\n{prompt}"
        response, _ = client.generate(prompt=full_content)

        # 去除 <think>...</think> 块（DeepSeek 等模型会输出推理过程）
        response = _strip_think_tags(response)

        # 标准化：去空格、转小写、替换空格为下划线
        return response.strip().lower().replace(" ", "_").replace("-", "_")
    except Exception:
        return "general_chat"


def generate_answer(user_query: str, intent: str, tool_name: str, tool_result: dict, history: list = None) -> tuple:
    """将工具结果转化为自然语言回答，支持多轮上下文。返回 (answer, usage) 元组。"""
    result_text = str(tool_result) if tool_result else "无结果"

    # 使用 messages 数组方式，包含完整历史
    client = get_router()
    try:
        messages = build_messages_with_history(
            system_prompt=SYSTEM_PROMPT.format(
                user_query=user_query,
                intent=intent,
                tool_name=tool_name,
                tool_result=result_text,
            ),
            user_content=user_query,
            history=history or [],
        )
        answer, usage = client.generate(messages=messages)
        return answer.strip(), usage
    except Exception as e:
        return f"回答生成失败: {str(e)}", None


def generate_answer_stream(user_query: str, intent: str, tool_name: str, tool_result: dict, history: list = None):
    """流式版本：逐步 yield LLM 输出 chunk，支持多轮上下文"""
    result_text = str(tool_result) if tool_result else "无结果"

    # 使用 messages 数组方式，包含完整历史
    client = get_router()
    try:
        messages = build_messages_with_history(
            system_prompt=SYSTEM_PROMPT.format(
                user_query=user_query,
                intent=intent,
                tool_name=tool_name,
                tool_result=result_text,
            ),
            user_content=user_query,
            history=history or [],
        )
        for chunk in client.generate(messages=messages, stream=True):
            yield chunk
    except Exception as e:
        yield f"[错误] 回答生成失败: {str(e)}"


def generate_general_answer(query: str, history: list = None) -> tuple:
    """通用对话回答，支持多轮上下文。返回 (answer, usage) 元组。"""
    client = get_router()
    try:
        if history and len(history) > 0:
            # 使用 messages 数组方式
            messages = build_messages_with_history(
                system_prompt="请根据对话历史和当前问题，用自然的中文回答用户。不要编造信息。",
                user_content=query,
                history=history,
            )
            answer, usage = client.generate(messages=messages)
        else:
            answer, usage = client.generate(prompt=query)
        return answer.strip(), usage
    except Exception as e:
        return f"回答生成失败: {str(e)}", None


def generate_tool_empty_answer(user_query: str, tool_name: str, tool_result: dict, history: list = None) -> tuple:
    """工具执行成功但未找到结果时，生成友好的告知回答。返回 (answer, usage) 元组。

    与 generate_general_answer 的区别：
    - 带完整系统提示词，明确告知 LLM "工具已执行但未找到结果"
    - 避免 LLM 误以为"没有权限"而给出不恰当回复
    """
    tool_message = tool_result.get("message", "未找到相关记录") if isinstance(tool_result, dict) else "未找到相关记录"
    client = get_router()
    system_prompt = TOOL_EMPTY_PROMPT.format(
        user_query=user_query,
        tool_name=tool_name,
        tool_message=tool_message,
    )
    try:
        if history and len(history) > 0:
            messages = build_messages_with_history(
                system_prompt=system_prompt,
                user_content=user_query,
                history=history,
            )
            answer, usage = client.generate(messages=messages)
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ]
            answer, usage = client.generate(messages=messages)
        return answer.strip(), usage
    except Exception as e:
        return f"回答生成失败: {str(e)}", None
