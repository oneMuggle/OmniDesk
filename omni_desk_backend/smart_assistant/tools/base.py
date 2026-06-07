from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tool_context import ToolContext


class ValidationResult:
    """工具结果验证"""

    def __init__(self, is_valid: bool = True, reason: str = ""):
        self.is_valid = is_valid
        self.reason = reason


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    intent_type: str = ""  # 用于意图匹配
    required_auth: bool = True  # 工具是否需要登录用户上下文(NEW 工具为 True)

    @abstractmethod
    def execute(self, query: str, context: "ToolContext") -> dict:
        """执行工具,返回结构化结果。

        参数:
            query: 用户的查询文本。
            context: 工具执行上下文(ToolContext),包含 user / request_id / history。
                必填 —— 调用方应在分发前从 DRF request 构造(参见
                ``ToolContext.from_request``)。
        """
        pass

    def get_schema(self) -> dict:
        """返回工具的描述 schema，用于意图识别"""
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
        }

    def get_examples(self) -> list:
        """返回 few-shot 示例，帮助 LLM 理解工具用法。"""
        return []

    def validate_params(self, params: dict) -> ValidationResult:
        """校验工具参数。子类可覆盖。"""
        return ValidationResult(is_valid=True)

    def validate_result(self, result: dict) -> ValidationResult:
        """校验工具返回结果的有效性。子类可覆盖。

        当工具返回 found=False 或数据不完整时返回无效。
        """
        if not isinstance(result, dict):
            return ValidationResult(is_valid=False, reason="结果不是字典")
        if not result.get("found"):
            return ValidationResult(
                is_valid=False,
                reason=result.get("message", "未找到相关信息"),
            )
        return ValidationResult(is_valid=True)

    def extract_keywords(self, query: str) -> list:
        """从用户查询中提取关键词。默认去除停用词。"""
        stopwords = {"搜索", "查找", "查询", "请问", "帮我", "看看", "有没有", "的", "了", "吗", "呢"}
        keywords = []
        for word in query:
            if word not in stopwords:
                keywords.append(word)
        return keywords
