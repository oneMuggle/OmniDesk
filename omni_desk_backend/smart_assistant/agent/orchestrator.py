from .intent_classifier import classify_intent, generate_answer, generate_answer_stream, generate_general_answer
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
            try:
                tool_result = tool.execute(user_query, context={'history': conversation_history or []})
            except Exception as e:
                # 工具异常，fallback 到通用回答
                tool_result = {'found': False, 'message': f'工具执行失败: {str(e)}'}

            # 工具失败时优雅降级
            if isinstance(tool_result, dict) and not tool_result.get('found'):
                answer = generate_general_answer(user_query, conversation_history)
                return {
                    'answer': answer,
                    'intent': intent,
                    'tool_used': tool.name,
                    'tool_result': tool_result,
                    'sources': None,
                    'tool_fallback': True,
                }

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

    def process_stream(self, user_query: str, conversation_history: list = None):
        """流式处理：先发送元数据，再逐 chunk 发送 LLM 输出"""
        import json

        # Step 1: 意图分类
        schemas = ToolRegistry.get_all_schemas()
        intent = classify_intent(user_query, schemas)

        # Step 2: 工具路由
        tool = ToolRegistry.get_tool(intent)
        tool_result = None
        tool_name = None
        sources = None
        tool_fallback = False

        if tool:
            try:
                tool_result = tool.execute(user_query, context={'history': conversation_history or []})
            except Exception as e:
                tool_result = {'found': False, 'message': f'工具执行失败: {str(e)}'}

            # 工具失败时 fallback 到通用回答
            if isinstance(tool_result, dict) and not tool_result.get('found'):
                tool_name = tool.name
                tool_fallback = True
            else:
                tool_name = tool.name
                sources = tool_result.get('sources') if isinstance(tool_result, dict) else None

        # 先发送元数据
        meta = json.dumps({
            'type': 'meta',
            'intent': intent,
            'tool_used': tool_name,
            'tool_result': tool_result,
            'sources': sources,
            'tool_fallback': tool_fallback,
        }, ensure_ascii=False)
        yield f"data: {meta}\n\n"

        # Step 3: 流式生成回答
        if tool_fallback:
            # fallback 到通用回答
            answer = generate_general_answer(user_query, conversation_history)
            def _gen():
                yield answer
            stream = _gen()
        elif tool:
            stream = generate_answer_stream(user_query, intent, tool_name, tool_result)
        else:
            answer = generate_general_answer(user_query, conversation_history)
            def _gen2():
                yield answer
            stream = _gen2()

        for chunk in stream:
            data = json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"

        # 发送结束信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
