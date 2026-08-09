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

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — 读取 Office 附件切片。

        chunk_index 用于长文档分片读取,从 context 拿 attachment 后
        按索引返回对应切片(OfficeExtractor.chunk_text 分片)。
        """
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "读取本次对话已上传 Office 附件(Word/Excel/PPT)的指定切片,"
                    "长文档按需分次读取。"
                    "示例 query: '继续读下一页'、'看附件第 2 段'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询,用于日志/审计",
                        },
                        "chunk_index": {
                            "type": "integer",
                            "description": "切片序号(从 0 开始),默认 0",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, params=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment")
        if not attachment or not attachment.get("text"):
            return {"found": False, "message": "当前对话未找到可读取的附件内容"}
        chunks = OfficeExtractor.chunk_text(attachment["text"])
        if not chunks:
            return {"found": False, "message": "附件无可读取的文本内容"}
        # I-2:优先用 LLM 结构化参数 chunk_index(此前永远读第 0 片)
        index = params.get("chunk_index") if isinstance(params, dict) else None
        if index is None:
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
