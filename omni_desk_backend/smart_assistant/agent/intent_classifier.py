from llm_service.openai_client import OpenAIClient
from .prompt_builder import INTENT_PROMPT, SYSTEM_PROMPT


def build_intent_prompt(schemas: list) -> str:
    """构建意图分类提示词"""
    schema_text = '\n'.join([f"- {s['name']}: {s['description']}" for s in schemas])
    return INTENT_PROMPT.replace('{tool_schemas}', schema_text)


def classify_intent(query: str, schemas: list) -> str:
    """使用 LLM 进行意图分类"""
    prompt = build_intent_prompt(schemas)
    client = OpenAIClient()
    try:
        response = client.generate(
            prompt=f"用户问题: {query}\n\n{prompt}",
        )
        # 标准化：去空格、转小写、替换空格为下划线
        return response.strip().lower().replace(' ', '_').replace('-', '_')
    except Exception:
        return 'general_chat'


def generate_answer(user_query: str, intent: str, tool_name: str, tool_result: dict) -> str:
    """将工具结果转化为自然语言回答"""
    result_text = str(tool_result) if tool_result else '无结果'

    prompt = SYSTEM_PROMPT.format(
        user_query=user_query,
        intent=intent,
        tool_name=tool_name,
        tool_result=result_text,
    )

    client = OpenAIClient()
    try:
        return client.generate(prompt=prompt).strip()
    except Exception as e:
        return f'回答生成失败: {str(e)}'


def generate_answer_stream(user_query: str, intent: str, tool_name: str, tool_result: dict):
    """流式版本：逐步 yield LLM 输出 chunk"""
    result_text = str(tool_result) if tool_result else '无结果'

    prompt = SYSTEM_PROMPT.format(
        user_query=user_query,
        intent=intent,
        tool_name=tool_name,
        tool_result=result_text,
    )

    client = OpenAIClient()
    try:
        for chunk in client.generate(prompt=prompt, stream=True):
            yield chunk
    except Exception as e:
        yield f'[错误] 回答生成失败: {str(e)}'


def generate_general_answer(query: str, history: list = None) -> str:
    """通用对话回答"""
    client = OpenAIClient()
    try:
        return client.generate(prompt=query).strip()
    except Exception as e:
        return f'回答生成失败: {str(e)}'
