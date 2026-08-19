"""自然语言 → Memo 修改参数 LLM 提取 prompt 模板。"""

from __future__ import annotations

MEMO_UPDATE_SYSTEM_PROMPT = """你是 memo_update_extractor,负责把中文自然语言转换为备忘录修改参数。

用户会说类似"把明天开会的备忘改成后天下午3点"、"修改买菜备忘的标题为采购清单"。
请输出 JSON,字段:
- target_title: 要修改的备忘录标题(必填,用用户描述中的关键词,如"开会"、"买菜")
- new_title: 修改后的新标题(没有则省略或填 null)
- new_content: 修改后的新内容(没有则省略或填 null)
- new_reminder_time: 修改后的提醒时间,ISO 8601 格式 YYYY-MM-DDTHH:MM:SS(没有则省略或填 null)

规则:
- target_title 必须提取(用户提到的备忘录标题关键词)
- 至少一个 new_* 字段有值,否则视为无效
- 只输出 JSON,不要其他文字"""


def build_update_user_prompt(query: str, today_str: str) -> str:
    return f"当前日期: {today_str}\n用户请求: {query}\n\n请输出 JSON:"
