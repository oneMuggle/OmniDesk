from abc import ABC, abstractmethod


class BaseTool(ABC):
    """工具基类"""
    name: str = ''
    description: str = ''
    intent_type: str = ''  # 用于意图匹配

    @abstractmethod
    def execute(self, query: str, context: dict = None) -> dict:
        """执行工具，返回结构化结果"""
        pass

    def get_schema(self) -> dict:
        """返回工具的描述 schema，用于意图识别"""
        return {
            'name': self.name,
            'description': self.description,
            'intent_type': self.intent_type,
        }
