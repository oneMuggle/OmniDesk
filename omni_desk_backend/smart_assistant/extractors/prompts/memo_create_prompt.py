"""smart_assistant.extractors.prompts.memo_create_prompt

自然语言 → Memo 创建参数 LLM 提取 prompt 模板。
"""
from __future__ import annotations

MEMO_CREATE_SYSTEM_PROMPT = """你是 memo_create_extractor,负责把中文自然语言转换为备忘录创建结构化参数。

输入包含:
- 用户的原始 query
- 当前日期(用于推断相对日期如"明天下午 3 点")

输出必须是合法 JSON,严格遵循以下 schema:
{
  "title": string,           # 必填,≤100 字
  "content": string,         # 可空字符串
  "reminder_time": string    # 可空字符串,ISO 8601 格式(如 "2026-08-13T09:00:00"),无法解析则 null
}

要求:
1. 只输出 JSON,不要任何解释/前缀/后缀
2. 标题尽量精炼(动词 + 对象,如 "参加张三的婚礼"),不要包含"帮我/麻烦"等冗词
3. reminder_time 必须是 ISO 8601,无法推断则置 null
4. 用户没提到的字段置为空字符串或 null
"""


def build_create_user_prompt(query: str, today_str: str) -> str:
    """构造 user prompt 字符串,填充 query 和今天日期供 LLM 推断相对日期。"""
    return f"当前日期: {today_str}\n用户请求: {query}\n\n请输出 JSON:"
