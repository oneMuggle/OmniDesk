"""由能力注册中心生成能力目录（Markdown）。

输出文件：``docs/technical/46-ai-capability-catalog.md``。内容完全由代码决定、
不含时间戳，便于用测试校验"文档与代码一致"。
"""

from __future__ import annotations

from pathlib import Path

from .registry import CapabilityRegistry, ResolvedToolSpec
from .spec import LOGIN_ONLY, ConfirmPolicy, DataScope

#: 仓库内能力目录的相对路径（相对仓库根目录）
CATALOG_RELATIVE_PATH = Path("docs") / "technical" / "46-ai-capability-catalog.md"

_RISK_LABELS = {"read": "只读", "write": "写入", "destructive": "删除"}

_SCOPE_DESCRIPTIONS = {
    DataScope.SCOPE: "按 SELF / DEPARTMENT / GLOBAL 三级 scope 过滤（`smart_assistant/scope.py`）",
    DataScope.OWNER: "只返回当前用户本人的数据，任何 scope 都不扩大",
    DataScope.MODULE: "与该模块 HTTP 接口共用同一段可见性逻辑",
    DataScope.DELEGATED: "不直接查询模型，调用其他工具的 `scoped_queryset()`",
    DataScope.ATTACHMENT: "只读取本次请求携带的附件",
    DataScope.KNOWLEDGE: "检索知识库或公共资料，不涉及用户私有数据",
    DataScope.RECIPIENT: "向他人写入（如发通知）时，按发起人的 scope 限定可选收件人",
}


def default_catalog_path() -> Path:
    """仓库根目录下的能力目录路径（``omni_desk_backend`` 的上一级）。"""
    from django.conf import settings

    return Path(settings.BASE_DIR).parent / CATALOG_RELATIVE_PATH


def _cell(text: str) -> str:
    return (text or "—").replace("|", "\\|").replace("\n", " ")


def _permission_label(resolved: ResolvedToolSpec) -> str:
    perm = resolved.spec.required_permission
    return "登录即可" if perm == LOGIN_ONLY else f"`{perm}`"


def _flags(resolved: ResolvedToolSpec) -> str:
    parts: list[str] = []
    if resolved.idempotent:
        parts.append("幂等")
    if resolved.spec.open_world:
        parts.append("访问外部系统")
    if resolved.spec.rollback:
        parts.append(f"可回滚（{resolved.spec.rollback}）")
    if resolved.spec.feature_flag:
        state = "开" if resolved.enabled else "关"
        parts.append(f"开关 `{resolved.spec.feature_flag}`（当前{state}）")
    return "、".join(parts) or "—"


def render_catalog(registry: CapabilityRegistry) -> str:
    specs = registry.specs()
    lines: list[str] = [
        "# 46 AI 能力目录",
        "",
        "> **本文件由代码自动生成，请勿手工编辑。**",
        "> 生成命令：`cd omni_desk_backend && python manage.py ai_capabilities --write`",
        "> 数据来源：各 app 的 `ai_tools.py`（`smart_assistant/capabilities`）。测试会校验本文件与代码一致。",
        "",
        "## 概览",
        "",
    ]
    by_risk = {level: sum(1 for s in specs if s.risk_level == level) for level in _RISK_LABELS}
    lines.append(
        f"共 {len(registry.toolsets())} 个工具集、{len(specs)} 个工具："
        + "，".join(f"{label} {by_risk[level]} 个" for level, label in _RISK_LABELS.items())
        + "。"
    )
    lines += [
        "",
        "| 工具集 | 所属 app | 工具（intent） |",
        "| --- | --- | --- |",
    ]
    for toolset in registry.toolsets():
        intents = [s.intent for s in specs if s.toolset.name == toolset.name]
        lines.append(
            f"| {_cell(toolset.title)}（`{toolset.name}`） | `{toolset.app_label}` | "
            + "、".join(f"`{i}`" for i in intents)
            + " |"
        )

    lines += ["", "## 工具明细", ""]
    for toolset in registry.toolsets():
        lines += [
            f"### {toolset.title}（`{toolset.name}`）",
            "",
            f"声明位置：`{toolset.module.replace('.', '/')}.py`",
            "",
        ]
        if toolset.description:
            lines += [toolset.description, ""]
        lines += [
            "| intent | 名称 | 类型 | 权限 | 数据范围 | 确认 | 其他 | 说明 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in specs:
            if s.toolset.name != toolset.name:
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{s.intent}`",
                        _cell(s.spec.title),
                        _RISK_LABELS.get(s.risk_level, s.risk_level),
                        _permission_label(s),
                        DataScope.LABELS.get(s.spec.data_scope, s.spec.data_scope),
                        ConfirmPolicy.LABELS.get(s.spec.confirm, s.spec.confirm),
                        _flags(s),
                        _cell(s.tool.description),
                    ]
                )
                + " |"
            )
        lines.append("")

    lines += [
        "## 字段说明",
        "",
        "- **类型**：由工具类的 `risk_level` 推导；对外导出为 MCP ToolAnnotations"
        "（`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint`）。",
        '- **权限**：`登录即可` 表示已登录用户都能调用，实际能看到的数据由"数据范围"限制；'
        "填写权限码时，还需 `user.has_perm()` 通过（superuser 天然通过）。",
        "- **数据范围**：",
    ]
    for key, desc in _SCOPE_DESCRIPTIONS.items():
        lines.append(f"  - {DataScope.LABELS[key]}（`{key}`）：{desc}")
    lines += [
        "- **确认**：写入和删除类工具必须经发起人本人确认后才执行（confirm-replay）。",
        "",
    ]
    return "\n".join(lines)
