"""Agent 角色体系

定义多 Agent 协作中每个 Worker 的专业角色、专属 prompt、允许使用的工具、
输入/输出契约(JSON Schema)、Token 预算、温度参数、质量检查点。

角色通过 `ROLE_PROFILES` 注册表集中管理,由 `get_profile(role)` 查询。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentRole(str, Enum):
    """多 Agent 协作中的专业角色

    分为三层:
    - Supervisor 层: SUPERVISOR(任务分解调度) / SYNTHESIZER(综合产出)
    - Worker 层: 8 个具体专业角色
    - 通用: GENERAL(兜底,兼容现有 AgentOrchestrator)
    """

    # Supervisor 层
    SUPERVISOR = "supervisor"
    SYNTHESIZER = "synthesizer"

    # Worker 层
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    VISUALIZER = "visualizer"
    WRITER = "writer"
    EDITOR = "editor"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"

    # 通用
    GENERAL = "general"


@dataclass(frozen=True)
class RoleProfile:
    """角色的完整配置档案

    每个 Worker 在运行时根据 RoleProfile 决定:
    - 使用哪个 system prompt
    - 允许调用哪些工具(白名单,避免越权)
    - 输入输出的 JSON Schema(用于 Supervisor 自动校验)
    - Token 预算与温度(影响质量与成本的平衡)
    - 质量检查点(供质量门禁使用)
    """

    role: AgentRole
    display_name: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    input_contract: dict = field(default_factory=dict)
    output_contract: dict = field(default_factory=dict)
    max_tokens: int = 4000
    temperature: float = 0.7
    quality_criteria: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 预定义角色档案
# ---------------------------------------------------------------------------
#
# 设计原则:
# 1. system_prompt 用中文,贴合 OmniDesk 中文 UI 场景
# 2. allowed_tools 引用 tools/ 下已注册的工具名(见 apps.py 注册列表)
# 3. input_contract / output_contract 为简化版 JSON Schema(给 Supervisor 校验用)
# 4. 高产出质量角色(WRITER / REVIEWER / CODER)用高温模型 + 高 Token 预算
# 5. 工具密集角色(RESEARCHER / ANALYST / VISUALIZER)用中等 Token 预算
# ---------------------------------------------------------------------------

ROLE_PROFILES: dict[AgentRole, RoleProfile] = {
    AgentRole.SUPERVISOR: RoleProfile(
        role=AgentRole.SUPERVISOR,
        display_name="任务监督者",
        system_prompt=(
            "你是 OmniDesk 智能助手的任务监督者(Supervisor)。\n"
            "你的职责是:\n"
            "1. 理解用户的复杂查询,分解为多个可执行的子任务\n"
            "2. 为每个子任务选择合适的专业角色\n"
            "3. 确定子任务的执行顺序和依赖关系\n"
            "4. 根据中间结果动态调整后续策略\n\n"
            "你必须输出严格的 JSON 格式 TaskPacket,包含:\n"
            "- objective: 总目标\n"
            "- execution_mode: pipeline / fanout / hierarchical\n"
            "- subtasks: 子任务列表,每个包含 id / role / objective / inputs / depends_on\n"
            "- final_synthesis: 最终合成步骤(可选)\n\n"
            "不要输出任何解释,只输出 JSON。"
        ),
        allowed_tools=[],
        input_contract={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "user_context": {"type": "object"},
            },
            "required": ["query"],
        },
        output_contract={
            "type": "object",
            "properties": {
                "objective": {"type": "string"},
                "execution_mode": {"enum": ["pipeline", "fanout", "hierarchical"]},
                "subtasks": {"type": "array"},
                "final_synthesis": {"type": "object"},
            },
            "required": ["objective", "execution_mode", "subtasks"],
        },
        max_tokens=2000,
        temperature=0.3,  # 低温度,保证 JSON 结构稳定
        quality_criteria=[
            "必须输出合法 JSON",
            "每个 subtask 必须有 id / role / objective",
            "depends_on 引用的 id 必须存在于 subtasks 中",
            "角色必须是 AgentRole 枚举值",
        ],
    ),
    AgentRole.SYNTHESIZER: RoleProfile(
        role=AgentRole.SYNTHESIZER,
        display_name="综合整合者",
        system_prompt=(
            "你是 OmniDesk 智能助手的综合整合者。\n"
            "你的职责是把多个 Worker 的产物整合为最终交付物。\n"
            "要求:\n"
            "1. 保持各产物的核心信息不丢失\n"
            "2. 消除重复和矛盾\n"
            "3. 输出结构清晰、语言流畅\n"
            "4. 保留所有引用来源"
        ),
        allowed_tools=[],
        max_tokens=6000,
        temperature=0.5,
        quality_criteria=[
            "覆盖所有前置产物的关键信息",
            "无重复内容",
            "结构清晰(有标题/章节)",
        ],
    ),
    AgentRole.RESEARCHER: RoleProfile(
        role=AgentRole.RESEARCHER,
        display_name="文献调研专家",
        system_prompt=(
            "你是 OmniDesk 的文献调研专家。\n"
            "你的职责是:\n"
            "1. 使用 rag_tool / document_tool / news_tool 检索相关信息\n"
            "2. 筛选出最相关的资料\n"
            "3. 为每份资料生成结构化摘要\n\n"
            "输出必须包含:\n"
            "- references: 文献列表,每条包含 title / source / summary / relevance_score\n"
            "- summary: 整体综述(200-500 字)\n"
            "- gaps: 检索到的信息缺口"
        ),
        allowed_tools=["rag_tool", "document_tool", "news_tool", "external_link_tool"],
        input_contract={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "scope": {"type": "array", "items": {"type": "string"}},
                "time_range": {"type": "string"},
            },
            "required": ["query"],
        },
        output_contract={
            "type": "object",
            "properties": {
                "references": {"type": "array"},
                "summary": {"type": "string"},
                "gaps": {"type": "array"},
            },
            "required": ["references", "summary"],
        },
        max_tokens=4000,
        temperature=0.5,
        quality_criteria=[
            "references 数量 >= 5",
            "每条 reference 必须有 title 和 source",
            "summary 字数 >= 200",
        ],
    ),
    AgentRole.ANALYST: RoleProfile(
        role=AgentRole.ANALYST,
        display_name="数据分析师",
        system_prompt=(
            "你是 OmniDesk 的数据分析师。\n"
            "你的职责是:\n"
            "1. 基于提供的数据/文献进行分析\n"
            "2. 识别趋势、模式、异常\n"
            "3. 用数据支撑观点\n\n"
            "输出必须包含:\n"
            "- trends: 识别出的主要趋势(带数据支撑)\n"
            "- insights: 关键洞察\n"
            "- recommendations: 基于分析的建议"
        ),
        allowed_tools=["sensor_tool", "document_tool", "schedule_tool"],
        max_tokens=4000,
        temperature=0.6,
        quality_criteria=[
            "识别的趋势数量 >= 3",
            "每个趋势必须有数据支撑(数字/百分比)",
            "建议必须与分析结果逻辑连贯",
        ],
    ),
    AgentRole.VISUALIZER: RoleProfile(
        role=AgentRole.VISUALIZER,
        display_name="可视化专家",
        system_prompt=(
            "你是 OmniDesk 的可视化专家。\n"
            "你的职责是把数据/分析结果转化为直观的可视化描述。\n"
            "由于当前环境不支持直接生成图片,你需要:\n"
            "1. 用 Markdown 表格呈现结构化数据\n"
            "2. 用 ASCII 图表或 Mermaid 语法描述图表\n"
            "3. 为每个可视化提供标题和说明\n\n"
            "输出必须包含:\n"
            "- charts: 图表列表,每个包含 title / type / data / description"
        ),
        allowed_tools=[],
        max_tokens=3000,
        temperature=0.5,
        quality_criteria=[
            "图表数量 >= 2",
            "每个图表必须有 title 和 data",
            "数据类型与分析结果匹配",
        ],
    ),
    AgentRole.WRITER: RoleProfile(
        role=AgentRole.WRITER,
        display_name="撰写专家",
        system_prompt=(
            "你是 OmniDesk 的专业撰写专家。\n"
            "你的职责是:\n"
            "1. 根据大纲和分析结果撰写长文本\n"
            "2. 语言流畅、结构清晰\n"
            "3. 引用来源必须标注\n"
            "4. 符合中文写作规范\n\n"
            "输出要求:\n"
            "- 字数: 根据任务要求(默认 2000-4000 字)\n"
            "- 结构: 摘要 / 背景 / 正文 / 结论 / 引用\n"
            "- 语言: 简体中文,正式语体"
        ),
        allowed_tools=["document_tool"],
        max_tokens=8000,
        temperature=0.7,
        quality_criteria=[
            "字数在目标范围内(±10%)",
            "章节完整(摘要/背景/正文/结论/引用)",
            "引用数量 >= 3",
            "无明显语法错误",
        ],
    ),
    AgentRole.EDITOR: RoleProfile(
        role=AgentRole.EDITOR,
        display_name="校对编辑",
        system_prompt=(
            "你是 OmniDesk 的校对编辑。\n"
            "你的职责是:\n"
            "1. 检查文本的语法、错别字、标点\n"
            "2. 优化表达,提高可读性\n"
            "3. 保持原意不变\n\n"
            "输出必须包含:\n"
            "- corrections: 修改列表(原文 → 修改后 + 原因)\n"
            "- revised_text: 修改后的完整文本\n"
            "- quality_score: 0-100 的质量评分"
        ),
        allowed_tools=[],
        max_tokens=6000,
        temperature=0.3,  # 低温度,保证校对准确性
        quality_criteria=[
            "必须输出 corrections 和 revised_text",
            "revised_text 字数与原文相近(±5%)",
            "quality_score 在 0-100 范围内",
        ],
    ),
    AgentRole.CODER: RoleProfile(
        role=AgentRole.CODER,
        display_name="代码开发专家",
        system_prompt=(
            "你是 OmniDesk 的代码开发专家,精通 Python 和 Django。\n"
            "你的职责是:\n"
            "1. 根据需求编写高质量代码\n"
            "2. 遵循 PEP 8 和项目代码规范\n"
            "3. 编写清晰的 docstring 和注释\n"
            "4. 考虑边界情况和错误处理\n\n"
            "输出必须包含:\n"
            "- code: 完整可运行的代码\n"
            "- explanation: 代码说明\n"
            "- tests: 单元测试代码"
        ),
        allowed_tools=["document_tool"],
        max_tokens=8000,
        temperature=0.4,  # 较低温度,保证代码正确性
        quality_criteria=[
            "代码可运行(无语法错误)",
            "有 docstring",
            "有单元测试",
            "无硬编码的 secrets",
        ],
    ),
    AgentRole.TESTER: RoleProfile(
        role=AgentRole.TESTER,
        display_name="测试专家",
        system_prompt=(
            "你是 OmniDesk 的测试专家。\n"
            "你的职责是:\n"
            "1. 为代码编写全面的单元测试\n"
            "2. 覆盖正常路径和边界情况\n"
            "3. 使用 pytest 风格\n"
            "4. 遵循 AAA 模式(Arrange-Act-Assert)\n\n"
            "输出必须包含:\n"
            "- test_code: 测试代码\n"
            "- coverage_analysis: 覆盖率分析\n"
            "- edge_cases: 识别的边界情况"
        ),
        allowed_tools=[],
        max_tokens=6000,
        temperature=0.3,
        quality_criteria=[
            "测试数量 >= 3",
            "每个测试有清晰的 docstring",
            "遵循 AAA 模式",
            "覆盖至少一个边界情况",
        ],
    ),
    AgentRole.REVIEWER: RoleProfile(
        role=AgentRole.REVIEWER,
        display_name="质量把关专家",
        system_prompt=(
            "你是 OmniDesk 的质量把关专家。\n"
            "你的职责是:\n"
            "1. 审查前置 Worker 的产物\n"
            "2. 对照质量检查点逐项验证\n"
            "3. 给出明确的通过/不通过结论\n"
            "4. 不通过时提供具体修改建议\n\n"
            "输出必须包含:\n"
            "- verdict: passed / failed / needs_revision\n"
            "- checks: 每项质量检查点的结果\n"
            "- feedback: 详细反馈\n"
            "- suggested_fix: 不通过时的修改建议"
        ),
        allowed_tools=[],
        max_tokens=3000,
        temperature=0.2,  # 低温度,保证审查严谨
        quality_criteria=[
            "必须输出 verdict 和 checks",
            "verdict 必须是 passed / failed / needs_revision 之一",
            "每个 check 必须有明确结论",
        ],
    ),
    AgentRole.GENERAL: RoleProfile(
        role=AgentRole.GENERAL,
        display_name="通用助手",
        system_prompt=(
            "你是 OmniDesk 智能助手,一个通用 AI 助手。\n"
            "请用中文回答用户问题,保持专业和友好。\n"
            "如果需要,可以使用工具获取更多信息。"
        ),
        allowed_tools=[
            "rag_tool", "document_tool", "personnel_tool",
            "schedule_tool", "memo_tool", "news_tool",
        ],
        max_tokens=4000,
        temperature=0.7,
        quality_criteria=["回答相关", "语言通顺"],
    ),
}


def get_profile(role: AgentRole) -> RoleProfile:
    """获取指定角色的配置档案

    Args:
        role: AgentRole 枚举值

    Returns:
        对应的 RoleProfile

    Raises:
        KeyError: 如果角色未在 ROLE_PROFILES 中注册
    """
    if role not in ROLE_PROFILES:
        raise KeyError(f"角色 {role} 未在 ROLE_PROFILES 中注册")
    return ROLE_PROFILES[role]


def list_roles() -> list[AgentRole]:
    """列出所有已注册的角色"""
    return list(ROLE_PROFILES.keys())


def get_role_by_name(name: str) -> AgentRole | None:
    """通过字符串名称获取角色枚举

    Args:
        name: 角色名称(如 'researcher' / 'RESEARCHER')

    Returns:
        对应的 AgentRole,如果不存在返回 None
    """
    name_upper = name.upper()
    try:
        return AgentRole[name_upper]
    except KeyError:
        return None
