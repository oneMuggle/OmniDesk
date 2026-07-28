"""多轮对话上下文管理器。

负责：
1. 加载/保存会话历史
2. 构建 LLM messages 数组（system prompt + 历史 + 当前问题）
3. Token 估算与上下文窗口管理
4. 滚动摘要触发（含失败退避，防止 LLM 故障期重试风暴）
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Token 阈值
SOFT_TOKEN_LIMIT = 3000  # 超过此值时压缩旧消息
HARD_TOKEN_LIMIT = 6000  # 超过此值时只保留摘要 + 最近 3 轮
RECENT_TURNS_SOFT = 6  # 软限制下保留的最近轮数
RECENT_TURNS_HARD = 3  # 硬限制下保留的最近轮数

# LLM 失败响应前缀（intent_classifier / tool_chain_executor 失败时返回的文案）
FAILED_ANSWER_PREFIX = "回答生成失败"
FAILED_ANSWER_STREAM_PREFIX = "[错误] 回答生成失败"

# 滚动摘要提示词
ROLLING_SUMMARY_PROMPT = (
    "请将以下对话历史压缩为一段简洁的中文摘要。"
    "保留关键事实（涉及的人物、时间、事项与结论），不超过 300 字，"
    "直接输出摘要正文，不要添加任何标题或前缀。"
)


def is_failed_answer(answer) -> bool:
    """统一判断 LLM 回答是否为失败响应。

    非流式路径失败文案形如 ``回答生成失败: <异常>``；
    流式路径失败 chunk 形如 ``[错误] 回答生成失败: <异常>``。
    orchestrator / views 共用此判断，避免错误文本污染多轮上下文。
    """
    if not isinstance(answer, str) or not answer:
        return False
    return answer.startswith(FAILED_ANSWER_PREFIX) or answer.startswith(FAILED_ANSWER_STREAM_PREFIX)


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。

    中文 ~1.5 字符/token，英文/数字 ~4 字符/token。
    这是快速估算，不依赖 tiktoken 等重型库。
    """
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


def format_history_for_prompt(history: list, max_turns: int = 5) -> str:
    """格式化对话历史为文本前缀（用于 prompt 拼接方式）。

    保留 format_history 的兼容性，供 generate_general_answer 等使用。
    """
    if not history:
        return ""

    # 截取最近 N 轮（每轮 = user + assistant）
    recent = history[-(max_turns * 2) :]

    parts = []
    for msg in recent:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        # 跳过 <thinking> 标签内的推理内容
        clean_content = content
        think_start = clean_content.find("<thinking>")
        think_end = clean_content.find("</thinking>")
        if think_start != -1 and think_end != -1 and think_end > think_start:
            clean_content = clean_content[:think_start] + clean_content[think_end + 10 :]
        if clean_content.strip():
            parts.append(f"{role}: {clean_content.strip()}")

    if not parts:
        return ""

    return "\n\n对话历史：\n" + "\n".join(parts) + "\n\n当前问题："


def build_messages_with_history(
    system_prompt: str,
    user_content: str,
    history: list,
    summary_text: str = None,
) -> list:
    """构建 LLM messages 数组，包含智能截断的历史。

    Args:
        system_prompt: 系统提示
        user_content: 当前用户消息
        history: 完整对话历史列表 [{"role": "user"/"assistant", "content": "..."}]
        summary_text: 可选的早期轮次摘要

    Returns:
        messages: 适合 OpenAI-compatible API 的 messages 数组
    """
    messages = []

    # System message
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # 如果有摘要，先注入摘要
    if summary_text:
        messages.append({"role": "system", "content": f"以下是之前对话的摘要，请在回答时参考：\n{summary_text}"})

    # 选择要保留的历史消息
    recent_messages = _select_recent_messages(history)

    # 追加历史消息
    for msg in recent_messages:
        messages.append(
            {
                "role": msg["role"],
                "content": msg["content"],
            }
        )

    # 追加当前用户消息
    messages.append({"role": "user", "content": user_content})

    return messages


def _select_recent_messages(history: list) -> list:
    """根据 token 限制选择要保留的历史消息。"""
    if not history:
        return []

    total_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in history)

    if total_tokens <= SOFT_TOKEN_LIMIT:
        # 全部保留
        return history

    # 从最新消息往回取，直到接近 token 限制
    selected = []
    running_tokens = 0

    for msg in reversed(history):
        content = msg.get("content", "")
        # 清理 <thinking> 内容以节省 token
        clean_content = _remove_thinking_tags(content)
        token_count = estimate_tokens(clean_content)

        if running_tokens + token_count > HARD_TOKEN_LIMIT:
            break

        selected.insert(
            0,
            {
                "role": msg["role"],
                "content": clean_content,
            },
        )
        running_tokens += token_count

    return selected


def _remove_thinking_tags(content: str) -> str:
    """移除 <thinking> 标签内容以节省 token。"""
    result = content
    while True:
        start = result.find("<thinking>")
        if start == -1:
            break
        end = result.find("</thinking>", start)
        if end == -1:
            break
        result = result[:start] + result[end + 11 :]
    return result


def should_summarize(history: list, summary_text: str = None, session_id=None) -> bool:
    """判断是否需要生成摘要。

    当历史 token 数超过 SOFT_TOKEN_LIMIT 且还没有摘要时，触发摘要生成。
    传入 ``session_id`` 时额外检查失败退避标记：近期摘要 LLM 调用失败过
    的会话在退避期内直接跳过，避免 LLM 故障期每次请求都重复锤击端点。
    """
    if summary_text:
        return False

    if is_summary_in_backoff(session_id):
        return False

    total_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in history)
    return total_tokens > SOFT_TOKEN_LIMIT


def count_turns(history: list) -> int:
    """计算对话轮数。"""
    if not history:
        return 0
    return sum(1 for msg in history if msg.get("role") == "user")


# ---------------------------------------------------------------------------
# 滚动摘要（长会话上下文压缩）
# ---------------------------------------------------------------------------

# 摘要失败退避（修复「重试风暴」）：LLM 故障期若每次 chat 请求都重试注定
# 失败的摘要调用，会让请求延迟翻倍并反复锤击端点。失败后写入按会话隔离的
# 退避标记，退避期内 should_summarize / apply_rolling_summary 直接跳过。
SUMMARY_BACKOFF_TTL = 1800  # 退避时长：30 分钟
SUMMARY_BACKOFF_PREFIX = "smart_assistant:summary_backoff:"


def _summary_backoff_key(session_id) -> str:
    """退避标记的缓存键（按会话隔离，避免跨会话互相抑制）。"""
    return f"{SUMMARY_BACKOFF_PREFIX}{session_id}"


def is_summary_in_backoff(session_id) -> bool:
    """该会话是否处于摘要失败退避期。

    ``session_id`` 为 None（如测试中的鸭子类型 session 无主键）时永不退避，
    保持既有调用方的行为不变。
    """
    if session_id is None:
        return False
    return cache.get(_summary_backoff_key(session_id)) is not None


def mark_summary_backoff(session_id, ttl: int = SUMMARY_BACKOFF_TTL) -> None:
    """摘要尝试失败后写入退避标记（TTL 到期自动失效）。"""
    if session_id is None:
        return
    cache.set(_summary_backoff_key(session_id), "1", ttl)


def clear_summary_backoff(session_id) -> None:
    """摘要成功后清除退避标记（TTL 到期也会自动失效，此处显式清理）。"""
    if session_id is None:
        return
    cache.delete(_summary_backoff_key(session_id))


def truncate_to_recent_turns(messages: list, recent_turns: int = RECENT_TURNS_SOFT) -> list:
    """截断历史，仅保留最近 N 轮（每轮 = user + assistant 各一条）。"""
    if not messages:
        return []
    return list(messages[-(recent_turns * 2) :])


def build_effective_history(messages: list, summary_text: str = None) -> list:
    """构造送入 LLM 的有效历史。

    - 无摘要：返回全量历史（兼容原行为）
    - 有摘要：以「摘要（system 消息）+ 最近 N 轮」代替全量，
      避免长会话 token 线性膨胀
    """
    messages = messages or []
    if not summary_text:
        return list(messages)
    recent = truncate_to_recent_turns(messages)
    summary_msg = {
        "role": "system",
        "content": f"以下是之前对话的摘要，请在回答时参考：\n{summary_text}",
    }
    return [summary_msg] + recent


def _format_transcript(messages: list) -> str:
    """把消息列表渲染为「用户/助手」对话文稿（剔除 thinking 标签）。"""
    parts = []
    for msg in messages or []:
        role = msg.get("role")
        if role == "user":
            label = "用户"
        elif role == "assistant":
            label = "助手"
        else:
            # system 等角色不参与摘要素材
            continue
        content = _remove_thinking_tags(msg.get("content", "") or "").strip()
        if content:
            parts.append(f"{label}: {content}")
    return "\n".join(parts)


def generate_rolling_summary(messages: list):
    """经 LLM 路由器为早期对话生成摘要。

    失败时（异常或返回失败响应）返回 None，由调用方静默降级（保留全量历史），
    绝不影响主对话链路。
    """
    transcript = _format_transcript(messages)
    if not transcript:
        return None
    try:
        # 延迟导入，避免模块级循环依赖，并保证测试 patch llm_service.router.get_router 生效
        from llm_service.router import get_router

        answer, _usage = get_router().generate(
            prompt=f"{ROLLING_SUMMARY_PROMPT}\n\n对话历史：\n{transcript}",
        )
    except Exception as exc:
        logger.warning("滚动摘要生成失败，保留全量历史: %s", exc)
        return None
    if is_failed_answer(answer):
        logger.warning("滚动摘要返回失败响应，保留全量历史")
        return None
    summary = (answer or "").strip()
    return summary or None


def apply_rolling_summary(session, recent_turns: int = RECENT_TURNS_SOFT) -> bool:
    """会话保存路径的滚动摘要入口（就地修改 session，不负责 save）。

    超过 ``SOFT_TOKEN_LIMIT`` 且尚无摘要时：
    1. 对「早期消息」（最近 N 轮之外的部分）生成摘要写入 ``summary_text``
    2. 截断 ``messages`` 仅保留最近 N 轮，并同步 ``turn_count`` / ``summary_token_count``

    摘要生成失败时静默降级：session 保持原样（全量历史），并写入失败退避
    标记（默认 30 分钟）。退避期内 ``should_summarize`` 直接返回 False，
    避免 LLM 故障期每次 chat 请求都多打一次注定失败的摘要调用（重试风暴）。
    摘要成功后清除退避标记。

    返回 True 表示发生了摘要与截断。
    """
    # 鸭子类型 session 可能无主键（测试场景）→ session_id=None → 不参与退避
    session_id = getattr(session, "pk", None)
    messages = list(session.messages or [])
    if not should_summarize(messages, session.summary_text, session_id=session_id):
        return False
    recent = truncate_to_recent_turns(messages, recent_turns)
    early = messages[: len(messages) - len(recent)]
    if not early:
        return False
    summary = generate_rolling_summary(early)
    if not summary:
        # LLM 失败（异常/失败响应）→ 写退避标记，抑制后续重试风暴
        mark_summary_backoff(session_id)
        return False
    session.summary_text = summary
    session.summary_token_count = estimate_tokens(summary)
    session.messages = recent
    session.turn_count = count_turns(recent)
    clear_summary_backoff(session_id)
    return True
