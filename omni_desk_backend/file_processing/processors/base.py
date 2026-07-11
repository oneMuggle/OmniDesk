from abc import ABC, abstractmethod
from typing import Any


class FileProcessor(ABC):
    """文件处理器抽象基类"""

    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """提取纯文本（用于 AI 分析）"""
        pass

    @abstractmethod
    def extract_markdown(self, file_path: str) -> str:
        """提取 Markdown 格式"""
        pass

    @abstractmethod
    def extract_structured(self, file_path: str) -> dict[str, Any]:
        """提取结构化数据（JSON）"""
        pass

    @abstractmethod
    def get_metadata(self, file_path: str) -> dict[str, Any]:
        """获取文件元数据（页数、Sheet 数等）"""
        pass
