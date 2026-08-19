"""自然语言 → Memo 删除参数 LLM 提取 prompt 模板。"""

from __future__ import annotations

MEMO_DELETE_SYSTEM_PROMPT = """你是 memo_delete_extractor,负责把中文自然语言转换为备忘录删除参数。

用户会说类似"删掉明天开会的备忘"、"把采购备忘删了"。
请输出 JSON,字段:
- target_title: 要删除的备忘录标题(必填,用用户描述中的关键词,如"开会"、"采购")

规则:
- target_title 必须提取
- 只输出 JSON,不要其他文字"""


def build_delete_user_prompt(query: str, today_str: str) -> str:
    return f"当前日期: {today_str}\n用户请求: {query}\n\n请输出 JSON:"
