"""smart_assistant/tools/spreadsheet_tool.py — Excel 表格统计与自然语言问答"""

from __future__ import annotations

import re

import pandas as pd

from file_processing.ai.query import NaturalLanguageQuery

from .base import BaseTool

# 简单统计关键词 → 直接用 pandas，不必走 LLM
_SIMPLE_STATS = re.compile(r"总人数|几行|多少行|几条|共.?多少|行数|columns|有哪些列|列名")


class SpreadsheetTool(BaseTool):
    """对上传 Excel 的指定 sheet 做统计或自然语言问答。"""

    name = "spreadsheet_qa"
    description = "对用户上传的 Excel 表格做数据统计（总行数/列名）与自然语言问答"
    intent_type = "spreadsheet_qa"
    risk_level = "read"

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema — Excel 表格统计与自然语言问答。"""
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "对用户上传的 Excel 表格做数据统计(总行数/列名)或自然语言问答,"
                    "统计走 pandas,问答复用 file_processing 的 LLM 表格问答。"
                    "示例 query: '这个表格多少行'、'A 列的总和'、'按部门统计人数'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言问题或统计关键词",
                        },
                        "sheet_name": {
                            "type": "string",
                            "description": "指定 sheet 名(可选,默认取第一个 sheet)",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def execute(self, query=None, context=None, **kwargs) -> dict:
        ctx = context if isinstance(context, dict) else {}
        attachment = ctx.get("attachment") or {}
        sheets = attachment.get("sheets") or []
        if not sheets:
            return {"found": False, "message": "当前附件没有可分析的 Excel 表格数据"}
        sheet = sheets[0]
        df = pd.DataFrame(sheet["data"], columns=sheet["headers"])

        if _SIMPLE_STATS.search(query or ""):
            return {
                "found": True,
                "stats": {
                    "sheet": sheet["name"],
                    "columns": sheet["headers"],
                    "total_rows": len(df),
                    "total_columns": len(sheet["headers"]),
                },
                "summary": f"Sheet「{sheet['name']}」共 {len(df)} 行、{len(sheet['headers'])} 列",
            }

        # 复杂自然语言问题 → 复用 file_processing 的 LLM 表格问答
        # P1A-1: query() 改走 LLMRouter,返回 (content, usage) 元组,此处丢弃 usage
        answer, _usage = NaturalLanguageQuery().query(
            query or "",
            {"sheets_data": [{"name": sheet["name"], "headers": sheet["headers"], "data": sheet["data"]}]},
        )
        return {"found": True, "answer": answer, "summary": answer}
