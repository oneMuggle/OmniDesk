from .intent_classifier import classify_intent, generate_answer, generate_general_answer
from ..tools.registry import ToolRegistry


class AgentOrchestrator:
    """Agent 编排器：意图分类 → 工具选择 → 回答生成"""

    def process(self, user_query: str, conversation_history: list = None) -> dict:
        """处理用户问题"""
        # Step 1: 意图分类
        schemas = ToolRegistry.get_all_schemas()
        intent = classify_intent(user_query, schemas)

        # Step 2: 工具路由
        tool = ToolRegistry.get_tool(intent)
        if tool:
            tool_result = tool.execute(user_query, context={'history': conversation_history or []})
            # Step 3: LLM 生成自然语言回答
            answer = generate_answer(user_query, intent, tool.name, tool_result)
            return {
                'answer': answer,
                'intent': intent,
                'tool_used': tool.name,
                'tool_result': tool_result,
                'sources': tool_result.get('sources') if isinstance(tool_result, dict) else None,
            }
        else:
            # 通用对话
            answer = generate_general_answer(user_query, conversation_history)
            return {
                'answer': answer,
                'intent': 'general_chat',
                'tool_used': None,
                'tool_result': None,
                'sources': None,
            }
