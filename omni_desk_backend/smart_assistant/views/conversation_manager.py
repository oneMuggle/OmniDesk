"""会话领域逻辑(纯函数模块)——从 views/chat.py 拆分。

职责:附件抽取/注入、会话加载、成功持久化、结果判定与 usage 解析。
仅依赖 models / extractors / tools_io / conversation_context,不依赖任何
ViewSet / DRF 视图基础设施(Response 仅用于构造附件错误响应)。
"""

from observability import get_logger
from rest_framework import status
from rest_framework.response import Response

from ..agent.conversation_context import (
    apply_rolling_summary,
    build_effective_history,
    count_turns,
    is_failed_answer,
)
from ..extractors.office_extractor import ExtractedDocument, OfficeExtractError, OfficeExtractor
from ..models import SmartAssistantSession
from ..tools_io import cache_attachment, file_sha256

logger = get_logger(__name__, "smart_assistant")


def resolve_error(result: dict) -> bool:
    """判定编排结果是否为失败响应：优先取显式 error 标记，前缀判断兜底。"""
    return bool(result.get("error")) or is_failed_answer(result.get("answer"))


def usage_fields(usage):
    """从 usage 字典提取 token 与成本字段（缺失时为 None，不报错）。"""
    usage = usage or {}
    return (
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
        usage.get("estimated_cost"),
        usage.get("model_name") or "",
    )


def extract_attachment(request):
    """校验并抽取附件。返回 (doc_dict, None) 或 (None, error_response)。

    ``doc_dict`` 字段:text / markdown / sheets / format / filename;
    无附件时 ``(None, None)``;抽取失败时 ``(None, Response 400)``。
    """
    file = request.FILES.get("attachment")
    if not file:
        return None, None
    # I-1:早期拒绝超大文件，避免全量读入内存后再由 OfficeExtractor 拒绝
    if file.size and file.size > 10 * 1024 * 1024:
        return None, Response(
            {"detail": "文件超过 10MB 上限，请压缩或拆分后重试"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        extracted = OfficeExtractor.extract(file)
    except OfficeExtractError as exc:
        return None, Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if not extracted.text and not extracted.markdown:
        return None, Response(
            {"detail": "未从文件中提取到文本内容，可能为纯图片扫描件"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    doc_dict = {
        "text": extracted.text,
        "markdown": extracted.markdown,
        "sheets": extracted.sheets,
        "format": extracted.format,
        "filename": file.name,
    }
    return doc_dict, None


def inject_attachment(conversation_history, doc_dict, conversation_id):
    """把附件内容作为 system 消息注入历史头部，并写入短时附件缓存。

    缓存键:(conversation_id, file_hash),TTL 10 分钟,供后续 office_read
    工具按 file_hash 二次取用。无 conversation_id 时不缓存(单次请求即丢)。
    """
    prompt_text = OfficeExtractor.format_for_prompt(
        ExtractedDocument(text=doc_dict["text"], markdown=doc_dict["markdown"]),
        doc_dict["filename"],
    )
    attachment_msg = {"role": "system", "content": prompt_text}
    conversation_history = [attachment_msg] + (conversation_history or [])
    if conversation_id:
        seed = (doc_dict["filename"] + doc_dict["text"][:200]).encode("utf-8", errors="replace")
        file_hash = file_sha256(seed)
        cache_attachment(conversation_id, file_hash, doc_dict)
    return conversation_history


def load_session(user, conversation_id):
    """加载会话并构建有效历史。

    提取 create / stream 共有的会话加载逻辑:按 (id, user) 取会话,
    有摘要时用「摘要 + 最近消息」代替全量历史(控制 token 膨胀)。

    会话不存在 / 不属于该用户 / 无 conversation_id 时返回 (None, None),
    不抛异常 —— 是否响应 404 由调用方决定。
    """
    if not conversation_id:
        return None, None
    try:
        session = SmartAssistantSession.objects.get(id=conversation_id, user=user)
        conversation_history = build_effective_history(session.messages, session.summary_text)
    except SmartAssistantSession.DoesNotExist:
        return None, None
    return session, conversation_history


def persist_success(session, conversation_id, query, answer, user):
    """create 路径的成功持久化:追加消息 / 更新 turn_count / 滚动摘要,或新建会话。

    返回 (session, cid)。失败响应不落库的判断在调用方完成(本函数仅处理成功路径)。
    注意:仅提取 create 版语义(建新会话带 title);stream 版持久化带 last_error=''
    防御,语义有差异,由 chat_stream 单独实现。
    """
    if conversation_id and session:
        existing_messages = session.messages or []
        session.messages = existing_messages + [
            {"role": "user", "content": query},
            {"role": "assistant", "content": answer},
        ]
        session.turn_count = count_turns(session.messages)
        if not session.title:
            session.title = query[:50]
        # 滚动摘要：超阈值时压缩早期历史（失败静默降级，不影响主对话）
        apply_rolling_summary(session)
        session.save()
        cid = session.id
    else:
        session = SmartAssistantSession.objects.create(
            user=user,
            title=query[:50],
            messages=[
                {"role": "user", "content": query},
                {"role": "assistant", "content": answer},
            ],
            turn_count=1,
        )
        cid = session.id
    return session, cid
