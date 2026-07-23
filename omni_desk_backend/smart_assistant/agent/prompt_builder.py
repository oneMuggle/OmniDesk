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


TOOL_EMPTY_PROMPT = """你是一个智能助手。你尝试查询了相关信息，但没有找到记录。

用户问题: {user_query}
查询工具: {tool_name}
工具返回: {tool_message}

要求：
1. 直接告知用户未找到相关记录，语气友好自然
2. 可以简要说明可能的原因（如该日期暂无排班数据）
3. 建议用户联系管理员确认数据是否已录入
4. 不要编造信息，不要给出与查询无关的建议
5. 不要说"我没有权限"或"我无法访问"——你已经查询过了，只是没有找到结果"""


def format_history(history: list, max_turns: int = 5) -> str:
    """格式化对话历史为上下文"""
    if not history:
        return ""

    # 截取最近 N 轮（每轮=user+assistant）
    recent = history[-(max_turns * 2) :]

    parts = []
    for msg in recent:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        # 跳过 <thinking> 标签内的推理内容
        clean_content = content
        think_start = clean_content.find("<thinking>")
        think_end = clean_content.find("</thinking>")
        if think_start != -1 and think_end != -1:
            clean_content = clean_content[:think_start] + clean_content[think_end + 11 :]
        parts.append(f"{role}: {clean_content.strip()}")

    if not parts:
        return ""

    return "\n\n对话历史：\n" + "\n".join(parts) + "\n\n当前问题："


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
如果用户的问题与公司公告、通知、本周安排查询相关，返回 announcement_query
如果用户的问题与合规检查、整改项、待办合规问题查询相关，返回 compliance_query
如果用户的问题与公司内网工具、外链、VPN、Jira 等系统访问地址查询相关，返回 external_link_query

如果用户的问题涉及以下复杂任务场景，返回 complex_task：
- 需要多步骤协作的任务(如：调研 + 分析 + 撰写报告)
- 需要多个专业角色参与的任务(如：文献调研、数据分析、代码开发)
- 需要长文本产出物的任务(如：研究报告、技术文档、代码实现)
- 明确包含"调研"、"报告"、"分析"、"开发"、"整理"、"综述"等关键词

其他情况返回 general_chat

只返回意图类型名称，不要其他解释。"""

SUMMARY_INTENT_HINT = """

## 汇总场景提示

当用户问"我今天/这周/接下来有哪些事"等汇总类问题时:
1. 主动规划多个工具并行调用(Schedule + MeetingRoom + Announcement + Memo 等)
2. 每个工具会自动按用户身份过滤(scope=self/department/global)
3. 综合结果时按时间排序,清晰呈现各类别数量

示例 query:
- "这周我有哪些事" → schedule + meeting_room + announcement
- "今天有什么安排" → schedule + meeting_room
- "本部门最新公告" → announcement(单一工具,但会按 scope 过滤)
"""


TOOL_CHAIN_PROMPT = (
    """你是一个工具链规划器。根据用户的查询，判断需要调用哪些工具。

可用的工具：
{tool_schemas}

用户查询：{user_query}

请分析用户查询中涉及的意图，返回需要调用的工具列表（JSON 格式）。
如果查询只涉及一个意图，返回空数组 []。
如果涉及多个意图，返回工具执行计划。

格式：
[
  {{"tool": "工具名", "params": {{"query": "子查询"}}, "depends_on": null}},
  {{"tool": "工具名2", "params": {{"query": "子查询2"}}, "depends_on": "工具名"}}
]

只返回 JSON 数组，不要其他文字。"""
    + SUMMARY_INTENT_HINT
)

TOOL_CHAIN_SYNTHESIS_PROMPT = """你是一个智能助手，负责将多个工具的执行结果综合成自然的中文回答。

用户问题：{user_query}

各工具执行结果：
{tool_results}

要求：
1. 用简洁自然的中文回答
2. 综合所有成功的工具结果
3. 对于失败的工具，简要说明原因
4. 不要编造任何信息
5. 如果有失败的工具，在回答末尾注明（如"但暂时无法查询XX信息"）"""
