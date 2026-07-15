"""多轮对话上下文管理器。

负责：
1. 加载/保存会话历史
2. 构建 LLM messages 数组（system prompt + 历史 + 当前问题）
3. Token 估算与上下文窗口管理
4. 滚动摘要触发
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Token 阈值
SOFT_TOKEN_LIMIT = 3000  # 超过此值时压缩旧消息
HARD_TOKEN_LIMIT = 6000  # 超过此值时只保留摘要 + 最近 3 轮
RECENT_TURNS_SOFT = 6  # 软限制下保留的最近轮数
RECENT_TURNS_HARD = 3  # 硬限制下保留的最近轮数


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
    summary_text: str | None = None,
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
    selected: list[dict[str, Any]] = []
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


def should_summarize(history: list, summary_text: str | None = None) -> bool:
    """判断是否需要生成摘要。

    当历史 token 数超过 SOFT_TOKEN_LIMIT 且还没有摘要时，触发摘要生成。
    """
    if summary_text:
        return False

    total_tokens = sum(estimate_tokens(msg.get("content", "")) for msg in history)
    return total_tokens > SOFT_TOKEN_LIMIT


def count_turns(history: list) -> int:
    """计算对话轮数。"""
    if not history:
        return 0
    return sum(1 for msg in history if msg.get("role") == "user")
