"""工具链计划生成器。

当用户查询涉及多个意图时（如"查询张三的值班安排和待审批流程"），
LLM 生成工具执行计划，指定工具顺序和依赖关系。
"""

import json
import logging

from llm_service.router import get_router
from .prompt_builder import TOOL_CHAIN_PROMPT

logger = logging.getLogger(__name__)


def generate_tool_chain_plan(query: str, schemas: list, history: list = None) -> list | None:
    """判断是否需要多工具，并生成执行计划。

    Args:
        query: 用户查询
        schemas: 所有工具的 schema 列表
        history: 可选的对话历史

    Returns:
        执行计划列表（需要多工具时），或 None（单工具场景）
    """
    # 先尝试单意图分类
    from .intent_classifier import classify_intent

    primary_intent = classify_intent(query, schemas, history)

    # 检查查询中是否包含多个意图的关键词
    relevant_tools = []
    for schema in schemas:
        if _matches_intent(query, schema):
            relevant_tools.append(schema["name"])

    # 如果只有一个工具匹配，不需要链式执行
    if len(relevant_tools) <= 1:
        return None

    # 多工具场景，生成执行计划
    try:
        plan = _ask_llm_for_plan(query, schemas, history)
        return plan
    except Exception as e:
        logger.warning("工具链计划生成失败: %s", e)
        return None


def _matches_intent(query: str, schema: dict) -> bool:
    """基于关键词判断查询是否匹配某个工具意图。"""
    intent_name = schema.get("name", "").lower()

    # 意图关键词映射
    intent_keywords = {
        "schedule_query": ["排班", "值班", "谁值班", "值班表"],
        "event_query": ["事件", "日程", "节假日", "假期", "放假"],
        "personnel_query": ["人员", "谁", "部门", "职位", "电话", "联系人"],
        "knowledge_qa": ["知识", "文档", "文档库", "怎么", "如何", "是什么"],
        "document_search": ["文档", "公文", "模板", "搜索文档"],
        "memo_query": ["备忘录", "便签", "提醒"],
        "project_status": ["项目", "进度", "里程碑", "负责人"],
        "news_search": ["新闻", "通知", "公告"],
        # 换班三分支(P0-1,llm-swap-shift Phase 2)。注:换班是单工具场景,
        # 此处关键词仅参与多工具粗筛,最终路由以 classify_intent 的 LLM 分类为准;
        # 误命中多工具时 TOOL_CHAIN_PROMPT 会让 LLM 返回空数组回退单工具路径。
        "swap_request_create": ["换班", "替班", "调班", "换一下", "替一下"],
        "swap_request_decide": ["同意换班", "拒绝换班", "撤销换班", "取消换班", "接受换班", "不同意换班"],
        "swap_request_query": ["我发起的换班", "换班进度", "换班状态", "收到的换班", "收到的换班申请", "谁要跟我换班"],
    }

    keywords = intent_keywords.get(intent_name, [])
    return any(kw in query for kw in keywords)


def _ask_llm_for_plan(query: str, schemas: list, history: list = None) -> list | None:
    """让 LLM 生成工具执行计划。"""
    schema_text = json.dumps(schemas, ensure_ascii=False, indent=2)

    prompt = TOOL_CHAIN_PROMPT.format(
        tool_schemas=schema_text,
        user_query=query,
    )

    client = get_router()
    response, _ = client.generate(prompt=prompt)

    # 解析 JSON 响应
    try:
        # 尝试从响应中提取 JSON
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            plan = json.loads(response[json_start:json_end])
            # 验证计划格式
            if isinstance(plan, list) and all("tool" in step for step in plan):
                return plan
        return None
    except (json.JSONDecodeError, ValueError):
        logger.warning("工具链计划 JSON 解析失败: %s", response[:200])
        return None
