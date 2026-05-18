from .intent_classifier import classify_intent, generate_answer, generate_answer_stream, generate_general_answer
from ..tools.registry import ToolRegistry
from ..cache import (
    get_cached_intent, cache_intent,
    get_cached_tool_result, cache_tool_result,
    get_cached_answer, cache_answer,
)


class AgentOrchestrator:
    """Agent 编排器：意图分类 → 工具选择 → 回答生成"""

    def process(self, user_query: str, conversation_history: list = None) -> dict:
        """处理用户问题"""
        # Step 1: 意图分类（先查缓存）
        schemas = ToolRegistry.get_all_schemas()
        has_history = conversation_history is not None and len(conversation_history) > 0

        if not has_history:
            cached_intent = get_cached_intent(user_query, schemas)
            if cached_intent:
                intent = cached_intent
            else:
                intent = classify_intent(user_query, schemas, conversation_history)
                cache_intent(user_query, schemas, intent)
        else:
            # 有对话历史时跳过缓存（上下文相关）
            intent = classify_intent(user_query, schemas, conversation_history)

        # Step 2: 工具路由（先查缓存）
        tool = ToolRegistry.get_tool(intent)
        if tool:
            cached_result = get_cached_tool_result(tool.name, user_query)
            if cached_result is not None:
                tool_result = cached_result
            else:
                try:
                    tool_result = tool.execute(user_query, context={'history': conversation_history or []})
                except Exception as e:
                    tool_result = {'found': False, 'message': f'工具执行失败: {str(e)}'}
                cache_tool_result(tool.name, user_query, tool_result)

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

            # Step 3: LLM 生成自然语言回答（先查缓存）
            if not has_history:
                cached_answer = get_cached_answer(user_query, intent)
                if cached_answer:
                    answer = cached_answer
                else:
                    answer = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)
                    cache_answer(user_query, intent, answer)
            else:
                answer = generate_answer(user_query, intent, tool.name, tool_result, conversation_history)

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

        has_history = conversation_history is not None and len(conversation_history) > 0

        # Step 1: 意图分类
        schemas = ToolRegistry.get_all_schemas()
        intent = classify_intent(user_query, schemas, conversation_history)
        if not has_history:
            cache_intent(user_query, schemas, intent)

        # Step 2: 工具路由
        tool = ToolRegistry.get_tool(intent)
        tool_result = None
        tool_name = None
        sources = None
        tool_fallback = False

        if tool:
            cached_result = get_cached_tool_result(tool.name, user_query)
            if cached_result is not None:
                tool_result = cached_result
            else:
                try:
                    tool_result = tool.execute(user_query, context={'history': conversation_history or []})
                except Exception as e:
                    tool_result = {'found': False, 'message': f'工具执行失败: {str(e)}'}
                cache_tool_result(tool.name, user_query, tool_result)

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
            stream = generate_answer_stream(user_query, intent, tool_name, tool_result, conversation_history)
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
