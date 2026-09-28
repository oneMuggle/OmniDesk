"""评估用例的数据结构、加载与校验。

用例放在 ``evals/cases/*.yaml``，每个文件顶层为 ``cases: [...]``。格式见
docs/plans/2026-09-28_ai-eval-s0.md §2。
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CASES_DIR = Path(__file__).resolve().parent / "cases"

CATEGORIES = ("basic", "cross_module", "privilege", "injection", "ambiguous", "fault", "write")
CATEGORY_LABELS = {
    "basic": "基础查询",
    "cross_module": "跨模块",
    "privilege": "越权",
    "injection": "提示注入",
    "ambiguous": "意图模糊",
    "fault": "依赖故障",
    "write": "写操作",
}
PERSONAS = ("staff_a", "staff_a2", "staff_b", "head_a", "admin")
FAULT_KINDS = ("timeout", "error")
CANARY_PREFIX = "EVAL-"


class CaseError(ValueError):
    """用例文件格式不正确。"""


@dataclass(frozen=True)
class ToolCallStep:
    name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Expect:
    tools_any: tuple = ()
    tools_none: tuple = ()
    visible: tuple = ()
    # None：不检查是否出确认卡（如注入类用例）
    confirmation: bool | None = False
    # tools_any 显式写成 [] 时为 True：不应调用任何工具
    no_tool: bool = False


@dataclass(frozen=True)
class Script:
    intent: str = "general_chat"
    rounds: tuple = ()  # tuple[tuple[ToolCallStep, ...], ...]
    plan: tuple = ()  # 旧 JSON 路径的工具链计划：tuple[dict, ...]
    extract: dict = field(default_factory=dict)  # 写工具参数提取器的返回
    answer: str = ""


@dataclass(frozen=True)
class Fault:
    tool: str
    kind: str


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    persona: str
    question: str
    expect: Expect
    script: Script
    # 旧 JSON 路径的已知能力差异（如不做多意图规划）时，对该路径覆盖部分 expect 字段
    expect_json: Expect | None = None
    fault: Fault | None = None
    note: str = ""
    # 只在某条路径上跑（默认两条都跑）
    paths: tuple = ("native", "json")

    def expect_for(self, path: str) -> Expect:
        if path == "json" and self.expect_json is not None:
            return self.expect_json
        return self.expect

    @property
    def injected_tools(self) -> tuple:
        """注入类用例里剧本「服从注入」时调用的工具（= tools_none）。"""
        return self.expect.tools_none


def _as_tuple(value, *, name: str, case_id: str) -> tuple:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(value)
    raise CaseError(f"{case_id}: {name} 必须是列表")


def _parse_rounds(raw, case_id: str) -> tuple:
    rounds = []
    for idx, rnd in enumerate(raw or []):
        if isinstance(rnd, dict):
            rnd = [rnd]
        if not isinstance(rnd, list) or not rnd:
            raise CaseError(f"{case_id}: script.rounds[{idx}] 必须是非空列表")
        steps = []
        for step in rnd:
            if not isinstance(step, dict) or not step.get("name"):
                raise CaseError(f"{case_id}: script.rounds[{idx}] 的每一步必须有 name")
            args = step.get("args") or {}
            if not isinstance(args, dict):
                raise CaseError(f"{case_id}: script.rounds[{idx}].args 必须是对象")
            steps.append(ToolCallStep(name=str(step["name"]), args=dict(args)))
        rounds.append(tuple(steps))
    return tuple(rounds)


def _parse_expect(exp: dict, case_id: str, name: str) -> Expect:
    tools_any = _as_tuple(exp.get("tools_any"), name=f"{name}.tools_any", case_id=case_id)
    confirmation = exp.get("confirmation", False)
    return Expect(
        tools_any=tools_any,
        tools_none=_as_tuple(exp.get("tools_none"), name=f"{name}.tools_none", case_id=case_id),
        visible=_as_tuple(exp.get("visible"), name=f"{name}.visible", case_id=case_id),
        confirmation=None if confirmation is None else bool(confirmation),
        no_tool="tools_any" in exp and not tools_any,
    )


def parse_case(raw: dict) -> EvalCase:
    """把一条 YAML 用例转成 ``EvalCase``；只做结构校验，引用校验见 ``validate_cases``。"""
    if not isinstance(raw, dict):
        raise CaseError("用例必须是对象")
    case_id = str(raw.get("id") or "").strip()
    if not case_id:
        raise CaseError("用例缺少 id")
    category = raw.get("category")
    if category not in CATEGORIES:
        raise CaseError(f"{case_id}: category 必须是 {', '.join(CATEGORIES)} 之一")
    persona = raw.get("persona")
    if persona not in PERSONAS:
        raise CaseError(f"{case_id}: persona 必须是 {', '.join(PERSONAS)} 之一")
    question = str(raw.get("question") or "").strip()
    if not question:
        raise CaseError(f"{case_id}: 缺少 question")

    exp = raw.get("expect") or {}
    if not isinstance(exp, dict):
        raise CaseError(f"{case_id}: expect 必须是对象")
    expect = _parse_expect(exp, case_id, "expect")
    expect_json = None
    if raw.get("expect_json") is not None:
        override = raw["expect_json"]
        if not isinstance(override, dict):
            raise CaseError(f"{case_id}: expect_json 必须是对象")
        if not str(raw.get("note") or "").strip():
            raise CaseError(f"{case_id}: 使用 expect_json 时必须在 note 里说明 JSON 路径为什么不同")
        expect_json = _parse_expect({**exp, **override}, case_id, "expect_json")

    scr = raw.get("script") or {}
    if not isinstance(scr, dict):
        raise CaseError(f"{case_id}: script 必须是对象")
    plan = scr.get("plan") or []
    if not isinstance(plan, list) or not all(isinstance(s, dict) and s.get("tool") for s in plan):
        raise CaseError(f"{case_id}: script.plan 必须是 [{{tool, params}}] 列表")
    extract = scr.get("extract") or {}
    if not isinstance(extract, dict):
        raise CaseError(f"{case_id}: script.extract 必须是对象")
    script = Script(
        intent=str(scr.get("intent") or "general_chat"),
        rounds=_parse_rounds(scr.get("rounds"), case_id),
        plan=tuple(dict(s) for s in plan),
        extract=dict(extract),
        answer=str(scr.get("answer") or ""),
    )

    fault = None
    if raw.get("fault"):
        f = raw["fault"]
        if not isinstance(f, dict) or not f.get("tool") or f.get("kind") not in FAULT_KINDS:
            raise CaseError(f"{case_id}: fault 必须是 {{tool, kind: timeout|error}}")
        fault = Fault(tool=str(f["tool"]), kind=str(f["kind"]))

    paths = _as_tuple(raw.get("paths") or ("native", "json"), name="paths", case_id=case_id)
    if not paths or any(p not in ("native", "json") for p in paths):
        raise CaseError(f"{case_id}: paths 只能包含 native、json")

    return EvalCase(
        id=case_id,
        category=category,
        persona=persona,
        question=question,
        expect=expect,
        script=script,
        expect_json=expect_json,
        fault=fault,
        note=str(raw.get("note") or ""),
        paths=paths,
    )


def load_cases(directory: Path | str | None = None) -> list[EvalCase]:
    """读取目录下全部 ``*.yaml``，按文件名、文件内顺序返回；id 必须全局唯一。"""
    base = Path(directory) if directory else CASES_DIR
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for path in sorted(base.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        items = data.get("cases") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise CaseError(f"{path.name}: 顶层必须是 cases: [...]")
        for raw in items:
            try:
                case = parse_case(raw)
            except CaseError as exc:
                raise CaseError(f"{path.name}: {exc}") from None
            if case.id in seen:
                raise CaseError(f"{path.name}: 用例 id 重复：{case.id}")
            seen.add(case.id)
            cases.append(case)
    return cases


def validate_cases(cases, *, tool_names, canary_keys) -> list[str]:
    """引用校验：工具名必须已注册、标记 key 必须存在。返回问题列表（空 = 通过）。"""
    problems = []
    tool_names = set(tool_names)
    canary_keys = set(canary_keys)
    for case in cases:
        expects = [e for e in (case.expect, case.expect_json) if e is not None]
        referenced = {name for e in expects for name in (*e.tools_any, *e.tools_none)}
        referenced |= {step.name for rnd in case.script.rounds for step in rnd}
        referenced |= {str(step["tool"]) for step in case.script.plan}
        if case.fault:
            referenced.add(case.fault.tool)
        if case.script.intent not in ("general_chat", "complex_task"):
            referenced.add(case.script.intent)
        for name in sorted(referenced - tool_names):
            problems.append(f"{case.id}: 未注册的工具 {name}")
        # 问题里出现标记前缀会让「回显问题」被误判为泄露，也会让模型直接拿到编码
        if CANARY_PREFIX in case.question:
            problems.append(f"{case.id}: question 里不能出现标记前缀 {CANARY_PREFIX}")
        if case.category == "write" and not case.script.extract:
            problems.append(f"{case.id}: 写操作用例需要 script.extract（旧 JSON 路径的参数提取器返回）")
        for key in sorted({k for e in expects for k in e.visible}):
            if key not in canary_keys:
                problems.append(f"{case.id}: 未知的标记 {key}")
    return problems


def filter_cases(cases, patterns) -> list[EvalCase]:
    """按 id 或类别过滤（支持通配符，逗号分隔）；patterns 为空返回全部。"""
    pats = [p.strip() for p in (patterns or []) if p and p.strip()]
    if not pats:
        return list(cases)
    return [c for c in cases if any(fnmatch.fnmatch(c.id, p) or c.category == p for p in pats)]
