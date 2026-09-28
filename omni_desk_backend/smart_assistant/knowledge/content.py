"""各来源生成入库内容。返回 ``None`` 表示该对象不应在知识库中（未发布、未同步、已删除）。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from django.utils import timezone
from django.utils.html import strip_tags

MAX_BODY_CHARS = 200_000


class ContentNotReady(Exception):
    """内容暂时拿不到（如 Paperless 还没 OCR 完），保持 pending 等下次对账。"""


@dataclass(frozen=True)
class SourceContent:
    title: str
    body: str
    file_name: str

    def render(self) -> str:
        body = self.body
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + "\n\n（内容过长，已截断）"
        return f"# {self.title}\n\n{body}\n"


_BLOCK_END = re.compile(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|blockquote|pre)>")


def html_to_text(value: str) -> str:
    text = _BLOCK_END.sub("\n", value or "")
    text = html.unescape(strip_tags(text))
    lines = [line.strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def build_announcement(source_id: int) -> SourceContent | None:
    from events.models import Announcement

    announcement = Announcement.objects.filter(pk=source_id, status=Announcement.STATUS_PUBLISHED).first()
    if announcement is None:
        return None
    published = announcement.published_at or announcement.created_at
    meta = f"来源：公告　发布时间：{timezone.localtime(published).strftime('%Y-%m-%d %H:%M')}"
    return SourceContent(
        title=announcement.title,
        body=f"{meta}\n\n{html_to_text(announcement.content)}",
        file_name=f"announcement-{announcement.pk}.md",
    )


def build_paperless(source_id: int) -> SourceContent | None:
    from paperless_proxy.models import DocumentBinding
    from paperless_proxy.services.client import PaperlessClient

    binding = DocumentBinding.objects.filter(pk=source_id, paperless_id__isnull=False).first()
    if binding is None:
        return None
    document = PaperlessClient().get_document(binding.paperless_id)
    text = str((document or {}).get("content") or "").strip()
    if not text:
        raise ContentNotReady("paperless 尚未生成文本")
    meta = f"来源：文档库（{binding.get_source_type_display()}）"
    return SourceContent(title=binding.title, body=f"{meta}\n\n{text}", file_name=f"paperless-{binding.pk}.md")


BUILDERS = {
    "announcement": build_announcement,
    "paperless_document": build_paperless,
}
