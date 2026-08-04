"""swap_decide_prompt — 换班决策 LLM 解构 prompt"""

SWAP_DECIDE_SYSTEM_PROMPT = """你是 swap_request_extractor,负责把中文自然语言转换为换班决策结构化参数。

输入包含:
- 用户的原始 query
- 当前操作人姓名(我是接收方还是申请方?)
- 当前操作人作为 target_personnel / requester 的 pending 申请清单

输出必须是合法 JSON,严格遵循以下 schema:
{
  "action": "accept" | "reject" | "cancel"(必填,枚举),
  "swap_id": 申请 ID(可选,整数;若 query 中明确提到 ID 则填,否则 null,与 pending 清单匹配),
  "note": "决策备注(可选,字符串,默认空)"
}

要求:
1. 只输出 JSON,不要任何解释/前缀/后缀
2. action 必须是 accept / reject / cancel 之一,其他值视为非法
3. swap_id 优先从 query 提取数字;若 query 中说"那条申请""张三的",与 pending 清单的 requester.name 匹配
4. cancel 通常由申请方发起,accept/reject 通常由接收方
"""


def build_decide_user_prompt(query: str, actor_name: str, pending_swaps: list) -> str:
    """构造 user prompt 字符串

    pending_swaps: list of dict,每个 dict 含 swap_id / requester_name / target_name / duty_date
    """
    pending_text = "\n".join(
        f"  - #{s['swap_id']}: {s['requester_name']} → {s.get('target_name', '?')} "
        f"({s.get('duty_date', '?')})"
        for s in pending_swaps
    ) or "  (无 pending 申请)"
    return (
        f"操作人: {actor_name}\n"
        f"待决策申请清单:\n{pending_text}\n"
        f"用户请求: {query}\n"
        f"\n请输出 JSON:"
    )
