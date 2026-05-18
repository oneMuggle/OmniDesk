SYSTEM_PROMPT = """你是一个智能助手，负责将工具检索到的信息整理成自然语言回答用户的问题。

请根据以下信息生成回答：

用户问题: {user_query}
识别意图: {intent}
工具名称: {tool_name}
工具结果: {tool_result}

要求：
1. 用简洁自然的中文回答
2. 如果是排班信息，清楚列出值班人员和领导
3. 如果是人员信息，列出部门、职位和状态
4. 如果是知识库查询，注明信息来源文档
5. 如果工具未找到相关信息，直接告知用户未找到相关记录，不要给出额外建议或泛泛回答
6. 不要编造任何信息"""


def format_history(history: list, max_turns: int = 5) -> str:
    """格式化对话历史为上下文"""
    if not history:
        return ''

    # 截取最近 N 轮（每轮=user+assistant）
    recent = history[-(max_turns * 2):]

    parts = []
    for msg in recent:
        role = '用户' if msg.get('role') == 'user' else '助手'
        content = msg.get('content', '')
        # 跳过 <thinking> 标签内的推理内容
        clean_content = content
        think_start = clean_content.find('<thinking>')
        think_end = clean_content.find('</thinking>')
        if think_start != -1 and think_end != -1:
            clean_content = clean_content[:think_start] + clean_content[think_end + 11:]
        parts.append(f'{role}: {clean_content.strip()}')

    if not parts:
        return ''

    return '\n\n对话历史：\n' + '\n'.join(parts) + '\n\n当前问题：'

INTENT_PROMPT = """你是一个意图分类器。根据用户的问题，判断意图类型。

可选的意图类型：
{tool_schemas}

如果用户的问题与排班、值班相关，返回 schedule_query
如果用户的问题与人员信息查询相关，返回 personnel_query
如果用户的问题与业务知识、文档查询相关，返回 knowledge_qa
如果用户的问题与公文、文档模板、试验搜索相关，返回 document_search
如果用户的问题与事件、日程、节假日查询相关，返回 event_query
如果用户的问题与备忘录、便签查询相关，返回 memo_query
如果用户的问题与项目进度、状态、负责人查询相关，返回 project_status
如果用户的问题与新闻、通知搜索相关，返回 news_search
其他情况返回 general_chat

只返回意图类型名称，不要其他解释。"""
