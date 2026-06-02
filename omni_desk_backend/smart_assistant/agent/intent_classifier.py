from llm_service.router import get_router
from .prompt_builder import INTENT_PROMPT, SYSTEM_PROMPT
from .conversation_context import build_messages_with_history, format_history_for_prompt


def build_intent_prompt(schemas: list) -> str:
    """构建意图分类提示词"""
    schema_text = '\n'.join([f"- {s['name']}: {s['description']}" for s in schemas])
    return INTENT_PROMPT.replace('{tool_schemas}', schema_text)


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
        # 标准化：去空格、转小写、替换空格为下划线
        return response.strip().lower().replace(' ', '_').replace('-', '_')
    except Exception:
        return 'general_chat'


def generate_answer(user_query: str, intent: str, tool_name: str, tool_result: dict, history: list = None) -> str:
    """将工具结果转化为自然语言回答，支持多轮上下文"""
    result_text = str(tool_result) if tool_result else '无结果'

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
        answer, _ = client.generate(messages=messages)
        return answer.strip()
    except Exception as e:
        return f'回答生成失败: {str(e)}'


def generate_answer_stream(user_query: str, intent: str, tool_name: str, tool_result: dict, history: list = None):
    """流式版本：逐步 yield LLM 输出 chunk，支持多轮上下文"""
    result_text = str(tool_result) if tool_result else '无结果'

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
        yield f'[错误] 回答生成失败: {str(e)}'


def generate_general_answer(query: str, history: list = None) -> str:
    """通用对话回答，支持多轮上下文"""
    client = get_router()
    try:
        if history and len(history) > 0:
            # 使用 messages 数组方式
            messages = build_messages_with_history(
                system_prompt='请根据对话历史和当前问题，用自然的中文回答用户。不要编造信息。',
                user_content=query,
                history=history,
            )
            answer, _ = client.generate(messages=messages)
        else:
            answer, _ = client.generate(prompt=query)
        return answer.strip()
    except Exception as e:
        return f'回答生成失败: {str(e)}'
