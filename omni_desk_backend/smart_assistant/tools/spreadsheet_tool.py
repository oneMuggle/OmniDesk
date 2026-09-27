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

    def execute(self, query=None, context=None, params=None, **kwargs) -> dict:
        # 兼容旧路径的 dict 上下文和原生 tool calling 的 ToolContext（attachment 字段）
        if isinstance(context, dict):
            attachment = context.get("attachment") or {}
        else:
            attachment = getattr(context, "attachment", None) or {}
        sheets = attachment.get("sheets") or []
        if not sheets:
            return {"found": False, "message": "当前附件没有可分析的 Excel 表格数据"}

        params = params if isinstance(params, dict) else {}
        query = params.get("query") or query
        sheet_name = str(params.get("sheet_name") or "").strip()
        if sheet_name:
            sheet = next((s for s in sheets if s.get("name") == sheet_name), None)
            if sheet is None:
                available = [s.get("name") for s in sheets]
                return {
                    "found": False,
                    "message": f"未找到名为「{sheet_name}」的 sheet，可选：{'、'.join(map(str, available))}",
                    "available_sheets": available,
                }
        else:
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
        # P1A-1: query() 改走 LLMRouter,返回 (content, usage) 元组
        answer, usage = NaturalLanguageQuery().query(
            query or "",
            {"sheets_data": [{"name": sheet["name"], "headers": sheet["headers"], "data": sheet["data"]}]},
        )
        return {
            "found": True,
            "answer": answer,
            "summary": answer,
            "meta": {"usage": usage},  # P1A-1 Task 4: 暴露 usage 元数据
        }
