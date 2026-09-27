"""能力注册中心：发现各 app 的 ``ai_tools.py``、启动自检、按用户判定权限。"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from collections.abc import Iterable

from django.core.exceptions import ImproperlyConfigured

from .spec import (
    LOGIN_ONLY,
    TOOLSET_MARKER,
    ConfirmPolicy,
    DataScope,
    PageContext,
    QuickPrompt,
    Toolset,
    ToolSpec,
    import_ref,
    import_tool_class,
)

if TYPE_CHECKING:
    from django.apps import AppConfig

    from smart_assistant.tools.base import BaseTool

#: 各 app 中声明工具集的子模块名
AI_TOOLS_MODULE = "ai_tools"

_PERMISSION_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")
_TOOLSET_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

#: 快捷问题文案上限（抽屉按钮宽度有限）
QUICK_PROMPT_LABEL_MAX = 12
QUICK_PROMPT_QUERY_MAX = 100
#: 单次返回的快捷问题上限
QUICK_PROMPT_LIMIT = 6


@dataclass(frozen=True)
class ResolvedToolSpec:
    """ToolSpec + 所属工具集 + 工具实例（发现流程产物）。"""

    spec: ToolSpec
    toolset: Toolset
    tool: BaseTool
    enabled: bool = True

    @property
    def intent(self) -> str:
        return self.tool.intent_type

    @property
    def risk_level(self) -> str:
        return self.tool.risk_level

    @property
    def read_only(self) -> bool:
        from smart_assistant.tools.base import RISK_LEVEL_READ

        return self.tool.risk_level == RISK_LEVEL_READ

    @property
    def destructive(self) -> bool:
        from smart_assistant.tools.base import RISK_LEVEL_DESTRUCTIVE

        return self.tool.risk_level == RISK_LEVEL_DESTRUCTIVE

    @property
    def idempotent(self) -> bool:
        if self.spec.idempotent is not None:
            return self.spec.idempotent
        return self.read_only

    def annotations(self) -> dict:
        """MCP ToolAnnotations（2025-06-18）。仅为提示，安全由权限与 scope 保证。"""
        return {
            "title": self.spec.title,
            "readOnlyHint": self.read_only,
            "destructiveHint": self.destructive,
            "idempotentHint": self.idempotent,
            "openWorldHint": self.spec.open_world,
        }


# ---------------------------------------------------------------------------
# 启动自检
# ---------------------------------------------------------------------------


def _strict_schema_errors(node: Any, path: str) -> list[str]:
    """递归检查每个 object 节点 ``additionalProperties is False``。"""
    errors: list[str] = []
    if not isinstance(node, dict):
        return errors
    if node.get("type") == "object":
        if node.get("additionalProperties") is not False:
            errors.append(f"{path} 缺少 additionalProperties=false")
        for key, prop in (node.get("properties") or {}).items():
            errors.extend(_strict_schema_errors(prop, f"{path}.{key}"))
    if node.get("type") == "array" and "items" in node:
        errors.extend(_strict_schema_errors(node["items"], f"{path}[]"))
    return errors


def validate_spec(spec: ToolSpec, tool: BaseTool) -> list[str]:
    """返回该声明的全部问题（空列表表示通过）。规则见实施计划"启动自检"。"""
    from smart_assistant.tools.base import (
        RISK_LEVEL_READ,
        VALID_RISK_LEVELS,
        BaseTool as _BaseTool,
    )
    from smart_assistant.tools.registry import ToolRegistry

    errors: list[str] = []
    intent = getattr(tool, "intent_type", "") or "<未设置 intent_type>"

    if not spec.title:
        errors.append("title 不能为空")

    perm = spec.required_permission
    if perm != LOGIN_ONLY and not (isinstance(perm, str) and _PERMISSION_RE.match(perm)):
        errors.append(f"required_permission 必须是 LOGIN_ONLY 或 'app_label.codename'，实际为 {perm!r}")

    if spec.data_scope not in DataScope.ALL:
        errors.append(f"data_scope 取值无效: {spec.data_scope!r}")
    if spec.confirm not in ConfirmPolicy.ALL:
        errors.append(f"confirm 取值无效: {spec.confirm!r}")

    risk = getattr(tool, "risk_level", None)
    if risk not in VALID_RISK_LEVELS:
        errors.append(f"risk_level 取值无效: {risk!r}")
    elif risk == RISK_LEVEL_READ:
        if spec.confirm != ConfirmPolicy.NONE or tool.require_confirmation:
            errors.append("只读工具不应声明确认")
        if spec.rollback:
            errors.append("只读工具不应声明 rollback")
    else:
        if spec.confirm == ConfirmPolicy.NONE:
            errors.append(f"{risk} 工具必须声明 confirm（当前为 none）")
        if not tool.require_confirmation:
            errors.append(f"{risk} 工具的 require_confirmation 必须为 True，与 confirm 声明一致")

    if spec.data_scope == DataScope.SCOPE:
        cls = type(tool)
        if cls.build_base_queryset is _BaseTool.build_base_queryset or cls._scope_self is _BaseTool._scope_self:
            errors.append("data_scope=scope 的工具必须实现 build_base_queryset() 与 _scope_self()")

    try:
        schema = tool.get_openai_tool_schema()
    except Exception as exc:
        errors.append(f"get_openai_tool_schema() 抛出异常: {exc!r}")
    else:
        if not ToolRegistry._is_valid_openai_schema(schema):
            errors.append("OpenAI schema 结构不合法")
        else:
            function = schema["function"]
            if function.get("name") != intent:
                errors.append(f"schema name {function.get('name')!r} 与 intent 不一致")
            if function.get("strict") is not True:
                errors.append("schema 必须声明 strict=True")
            errors.extend(_strict_schema_errors(function["parameters"], "parameters"))

    return [f"[{intent}] {msg}" for msg in errors]


def _regex_errors(pattern: Any, where: str) -> tuple[list[str], re.Pattern | None]:
    if not isinstance(pattern, str) or not pattern:
        return [f"{where} 必须是非空正则字符串"], None
    try:
        return [], re.compile(pattern)
    except re.error as exc:
        return [f"{where} 正则无法编译: {pattern!r}（{exc}）"], None


def validate_toolset_extras(toolset: Toolset) -> list[str]:
    """校验 ``routes`` / ``quick_prompts`` / ``page_contexts``（S2）。"""
    errors: list[str] = []
    for pattern in toolset.routes:
        errors.extend(_regex_errors(pattern, "routes")[0])

    for prompt in toolset.quick_prompts:
        if not isinstance(prompt, QuickPrompt):
            errors.append(f"quick_prompts 中存在非 QuickPrompt 条目: {prompt!r}")
            continue
        if not prompt.label or len(prompt.label) > QUICK_PROMPT_LABEL_MAX:
            errors.append(f"快捷问题 label 必须为 1–{QUICK_PROMPT_LABEL_MAX} 字: {prompt.label!r}")
        if not prompt.query or len(prompt.query) > QUICK_PROMPT_QUERY_MAX:
            errors.append(f"快捷问题 query 必须为 1–{QUICK_PROMPT_QUERY_MAX} 字: {prompt.query!r}")
        for pattern in prompt.routes:
            errors.extend(_regex_errors(pattern, f"快捷问题 {prompt.label!r} 的 routes")[0])
        if not prompt.routes and not toolset.routes:
            errors.append(f"快捷问题 {prompt.label!r} 没有 routes，且 toolset 也未声明 routes")

    for ctx in toolset.page_contexts:
        if not isinstance(ctx, PageContext):
            errors.append(f"page_contexts 中存在非 PageContext 条目: {ctx!r}")
            continue
        if not _TOOLSET_NAME_RE.match(ctx.record_type or ""):
            errors.append(f"record_type 必须是小写蛇形: {ctx.record_type!r}")
        if not ctx.title:
            errors.append(f"[{ctx.record_type}] 页面上下文 title 不能为空")
        route_errors, compiled = _regex_errors(ctx.route, f"[{ctx.record_type}] route")
        errors.extend(route_errors)
        if compiled is not None and "record_id" not in compiled.groupindex:
            errors.append(f"[{ctx.record_type}] route 必须包含命名组 (?P<record_id>...)")
        try:
            loader = import_ref(ctx.loader)
        except Exception as exc:
            errors.append(f"[{ctx.record_type}] loader 无法导入: {ctx.loader!r}（{exc!r}）")
        else:
            if not callable(loader):
                errors.append(f"[{ctx.record_type}] loader 不可调用: {ctx.loader!r}")
    return errors


# ---------------------------------------------------------------------------
# 注册中心
# ---------------------------------------------------------------------------


class CapabilityRegistry:
    """保存全部工具集与工具声明；进程内单例见模块级 ``capabilities``。"""

    def __init__(self) -> None:
        self._toolsets: dict[str, Toolset] = {}
        self._specs: dict[str, ResolvedToolSpec] = {}
        self._page_contexts: dict[str, tuple[Toolset, PageContext]] = {}

    # --- 查询 ---------------------------------------------------------------

    def toolsets(self) -> list[Toolset]:
        return list(self._toolsets.values())

    def specs(self, include_disabled: bool = True) -> list[ResolvedToolSpec]:
        return [s for s in self._specs.values() if include_disabled or s.enabled]

    def get(self, intent: str) -> ResolvedToolSpec | None:
        return self._specs.get(intent)

    def is_permitted(self, intent: str, user: Any) -> bool:
        """按 ``required_permission`` 判定用户能否调用该工具。

        - 未登记声明的工具（测试桩等）放行，登录校验仍由 ``required_auth`` 负责；
        - ``LOGIN_ONLY`` 放行；
        - Django 权限码走 ``user.has_perm()``（superuser 天然通过）。
        """
        resolved = self._specs.get(intent)
        if resolved is None:
            return True
        if not resolved.enabled:
            return False
        perm = resolved.spec.required_permission
        if perm == LOGIN_ONLY:
            return True
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        has_perm = getattr(user, "has_perm", None)
        return bool(has_perm and has_perm(perm))

    def toolset_permitted(self, name: str, user: Any) -> bool:
        """该用户能否调用工具集中至少一个启用的工具。"""
        return any(
            item.enabled and item.toolset.name == name and self.is_permitted(item.intent, user)
            for item in self._specs.values()
        )

    def page_contexts(self) -> list[tuple[Toolset, PageContext]]:
        return list(self._page_contexts.values())

    def match_page_context(self, route: str) -> tuple[Toolset, PageContext, int] | None:
        """按路由找到页面上下文声明与记录 ID；未匹配返回 None。"""
        for owner, ctx in self._page_contexts.values():
            match = re.search(ctx.route, route)
            if not match:
                continue
            try:
                record_id = int(match.group("record_id"))
            except (TypeError, ValueError):
                continue
            return owner, ctx, record_id
        return None

    def quick_prompts_for(self, route: str, user: Any, limit: int = QUICK_PROMPT_LIMIT) -> list[dict]:
        """返回匹配该路由、且用户有权使用的快捷问题（按注册顺序，去重）。"""
        results: list[dict] = []
        seen: set[str] = set()
        for owner in self._toolsets.values():
            if not owner.quick_prompts or not self.toolset_permitted(owner.name, user):
                continue
            for prompt in owner.quick_prompts:
                patterns = prompt.routes or owner.routes
                if not any(re.search(p, route) for p in patterns):
                    continue
                if prompt.query in seen:
                    continue
                seen.add(prompt.query)
                results.append({"label": prompt.label, "query": prompt.query, "toolset": owner.name})
                if len(results) >= limit:
                    return results
        return results

    def missing_permissions(self) -> list[str]:
        """返回数据库中不存在的权限码（需在迁移完成后调用）。"""
        from django.contrib.auth.models import Permission

        missing: list[str] = []
        for resolved in self._specs.values():
            perm = resolved.spec.required_permission
            if perm == LOGIN_ONLY:
                continue
            app_label, codename = perm.split(".", 1)
            if not Permission.objects.filter(content_type__app_label=app_label, codename=codename).exists():
                missing.append(f"[{resolved.intent}] {perm}")
        return missing

    # --- 注册 ---------------------------------------------------------------

    def register_toolset(self, toolset: Toolset) -> list[ResolvedToolSpec]:
        """校验并登记一个工具集；任何问题都抛 ``ImproperlyConfigured``。"""
        from django.conf import settings

        errors: list[str] = []
        if not _TOOLSET_NAME_RE.match(toolset.name or ""):
            errors.append(f"toolset 名称必须是小写蛇形: {toolset.name!r}")
        if toolset.name in self._toolsets:
            errors.append(f"toolset 名称重复: {toolset.name!r}")
        if not toolset.specs:
            errors.append(f"toolset {toolset.name!r} 没有声明任何工具")
        errors.extend(validate_toolset_extras(toolset))
        seen_types: set[str] = set()
        for ctx in toolset.page_contexts:
            if not isinstance(ctx, PageContext):
                continue
            if ctx.record_type in self._page_contexts or ctx.record_type in seen_types:
                errors.append(f"record_type 重复: {ctx.record_type!r}")
            seen_types.add(ctx.record_type)

        resolved: list[ResolvedToolSpec] = []
        seen: set[str] = set()
        for spec in toolset.specs:
            if not isinstance(spec, ToolSpec):
                errors.append(f"toolset {toolset.name!r} 中存在非 ToolSpec 条目: {spec!r}")
                continue
            try:
                tool = import_tool_class(spec.tool)()
            except Exception as exc:
                errors.append(f"toolset {toolset.name!r} 无法实例化工具 {spec.tool!r}: {exc!r}")
                continue
            spec_errors = validate_spec(spec, tool)
            intent = tool.intent_type
            if intent in self._specs or intent in seen:
                spec_errors.append(f"[{intent}] intent 重复")
            errors.extend(spec_errors)
            seen.add(intent)
            enabled = True
            if spec.feature_flag:
                enabled = bool(getattr(settings, spec.feature_flag, False))
            resolved.append(ResolvedToolSpec(spec=spec, toolset=toolset, tool=tool, enabled=enabled))

        if errors:
            raise ImproperlyConfigured(f"AI 能力声明自检失败（{toolset.module}）：\n  - " + "\n  - ".join(errors))

        self._toolsets[toolset.name] = toolset
        for item in resolved:
            self._specs[item.intent] = item
        for ctx in toolset.page_contexts:
            self._page_contexts[ctx.record_type] = (toolset, ctx)
        return resolved

    def load_module(self, module: Any, app_label: str) -> list[Toolset]:
        """登记一个 ``ai_tools`` 模块中所有带 ``@toolset`` 标记的函数（按定义顺序）。"""
        loaded: list[Toolset] = []
        for obj in list(vars(module).values()):
            meta = getattr(obj, TOOLSET_MARKER, None)
            if not meta or not callable(obj):
                continue
            specs = obj()
            toolset = Toolset(
                name=meta["name"],
                title=meta["title"],
                description=meta.get("description", ""),
                app_label=app_label,
                module=module.__name__,
                specs=tuple(specs or ()),
                routes=tuple(meta.get("routes", ())),
                quick_prompts=tuple(meta.get("quick_prompts", ())),
                page_contexts=tuple(meta.get("page_contexts", ())),
            )
            self.register_toolset(toolset)
            loaded.append(toolset)
        return loaded

    def discover(self, app_configs: Iterable[AppConfig] | None = None, tool_registry: Any = None) -> None:
        """扫描各 app 的 ``ai_tools`` 模块并把启用的工具注册进 ``ToolRegistry``。

        可重复调用：每次都从空状态重建（``ready()`` 在测试中可能多次触发）。
        """
        from django.apps import apps
        from django.utils.module_loading import module_has_submodule

        if tool_registry is None:
            from smart_assistant.tools.registry import ToolRegistry as tool_registry

        self._toolsets.clear()
        self._specs.clear()
        self._page_contexts.clear()

        configs = list(app_configs) if app_configs is not None else list(apps.get_app_configs())
        for config in configs:
            if not module_has_submodule(config.module, AI_TOOLS_MODULE):
                continue
            module = importlib.import_module(f"{config.name}.{AI_TOOLS_MODULE}")
            self.load_module(module, config.label)

        for resolved in self._specs.values():
            if resolved.enabled:
                tool_registry.register(resolved.tool)


#: 进程内单例
capabilities = CapabilityRegistry()
