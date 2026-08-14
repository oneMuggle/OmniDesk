"""orchestrator 缓存签名与参数拆包辅助(从 orchestrator.py 提取,行为不变)。"""

import json


def _scope_cache_sig(tool_context):
    """从 ToolContext 派生 cache 隔离签名,防止跨用户缓存投毒。

    返回形如 ``u<user_pk>_s<scope_value>`` 的短串,拼到 cache key 里。
    tool_context 为 None 时退化为 ``anonymous``,与原行为兼容(空 sig)。
    """
    if tool_context is None or tool_context.user is None:
        return "anonymous"
    user = tool_context.user
    user_pk = getattr(user, "pk", None) or getattr(user, "id", None) or "anon"
    scope = getattr(tool_context, "scope", None)
    scope_value = scope.value if hasattr(scope, "value") else str(scope or "self")
    return f"u{user_pk}_s{scope_value}"


def _dict_to_query(validated) -> str:
    """把原生 tool_calls 的 validated 参数 dict 拆包为 ``execute()`` 期望的 query 字符串。

    F1 修复(2026-08-07):orchestrator 此前把 LLM 返回的 ``validated``(dict,
    来自 ``json.loads(tc.function.arguments)``)直接传给
    ``execute_with_guard(query, context)``,而 ``BaseTool.execute`` 签名期望
    ``query: str`` —— 导致:

    - **崩溃(6 工具)**:memo / document / project / sensor / news / personnel
      内部对 query 调 ``replace()`` / ``strip()``,dict 无该方法抛
      ``AttributeError``;
    - **静默错乱(5+ 工具)**:schedule / event / meeting_room 等 ``"X" in query``
      变成查 dict 的 key,恒为 ``False``(查错日期);compliance / external_link
      迭代 dict 得到 key 而非查询词。

    拆包策略:
    - **优先取 ``query`` 字段** —— 所有 19 个工具的 OpenAI schema 均以
      ``query`` 为必填自然语言输入,execute 实现只消费 query;LLM 额外给出的
      结构化字段(schedule 的 date_from/date_to、personnel 的 department 等)
      不拼接进 query(保留 F1 防污染决策,避免污染关键词匹配如 memo 的
      title__icontains),而是由 ``_execute_native_tool`` 经 ``params``
      完整透传给工具,工具 opt-in 读取,缺失时回退 query 解析;
    - **无 ``query`` 时兜底** —— 把其余非 query 字段序列化为
      ``key: value`` 片段(``，`` 连接),保留 LLM 提供的结构化参数语义;
    - 非 dict 输入(理论不出现)直接 ``str()`` 化,保持调用方不挂起。

    JSON fallback 路径(``_legacy_process``)仍传原始 ``user_query`` 字符串,
    本函数仅作用于原生 tool_calls 路径,不影响 A/B 对等。
    """
    if isinstance(validated, str):
        return validated
    if not isinstance(validated, dict):
        return "" if validated is None else str(validated)
    query = validated.get("query")
    if query is not None and str(query).strip():
        return str(query)
    parts = []
    for key, value in validated.items():
        if key == "query" or value is None:
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        parts.append(f"{key}: {value}")
    return "，".join(parts) if parts else ""
