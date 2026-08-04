"""swap_create_prompt — 换班创建 LLM 解构 prompt"""

SWAP_CREATE_SYSTEM_PROMPT = """你是 swap_request_extractor,负责把中文自然语言转换为换班申请结构化参数。

输入包含:
- 用户的原始 query
- 申请人姓名
- 当前日期

输出必须是合法 JSON,严格遵循以下 schema:
{
  "target_name": "接收方姓名(必填,字符串)",
  "duty_date": "值班日期,格式 YYYY-MM-DD(必填,字符串)",
  "reason": "申请理由(可选,字符串,默认空)"
}

要求:
1. 只输出 JSON,不要任何解释/前缀/后缀
2. 不可推断字段填 null
3. duty_date 必须是 YYYY-MM-DD,相对日期(如"下周三"、"明天")需要基于当前日期计算
4. 中文姓名照原样输出,不要拼音化
"""


def build_create_user_prompt(query: str, requester_name: str, today: str) -> str:
    """构造 user prompt 字符串"""
    return (
        f"申请人: {requester_name}\n"
        f"当前日期: {today}\n"
        f"用户请求: {query}\n"
        f"\n请输出 JSON:"
    )
