"""smart_assistant/tools/office_read_tool.py — 读取已上传 Office 附件切片"""

from __future__ import annotations

from ..extractors.office_extractor import OfficeExtractor
from .base import BaseTool


class OfficeReadTool(BaseTool):
    """读取本次对话已上传 Office 附件的指定切片（长文档按需读取）。"""

    name = "office_read"
    description = "读取用户上传 Office 附件的指定内容切片（当附件较长、需要更多内容时调用）"
    intent_type = "office_read"
    risk_level = "read"

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment")
        if not attachment or not attachment.get("text"):
            return {"found": False, "message": "当前对话未找到可读取的附件内容"}
        chunks = OfficeExtractor.chunk_text(attachment["text"])
        if not chunks:
            return {"found": False, "message": "附件无可读取的文本内容"}
        index = attachment.get("chunk_index", 0)
        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            return {"found": False, "message": f"切片序号越界（共 {len(chunks)} 片）"}
        return {
            "found": True,
            "filename": attachment.get("filename", "附件"),
            "total_chunks": len(chunks),
            "chunks": [chunks[index]],
            "summary": f"已读取附件第 {index + 1}/{len(chunks)} 片",
        }
