"""一次完整评估：造种子数据 → 逐目标 × 路径跑用例 → 出报告。

调用方负责数据库：``manage.py ai_eval`` 先建临时测试库；pytest 里直接用测试库。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .cases import CaseError, load_cases, filter_cases, validate_cases
from .harness import PATHS, EvalRunner, Target, isolated_runtime
from .report import build_report
from .seed import CANARY_SPECS, build_world


@dataclass
class SuiteResult:
    report: dict
    results: list
    world: object


def parse_target(spec: str, *, env=None) -> Target:
    """解析 ``name=qwen,url=https://llm.example.com,model=qwen2.5-72b,key_env=QWEN_KEY[,cost=0.002]``。

    ``url`` 与端点配置里的地址同口径（不带 ``/v1``；带了会自动去掉）。

    密钥建议用 ``key_env`` 指向环境变量，避免出现在命令行历史里；也支持 ``key=``。
    """
    import os

    env = os.environ if env is None else env
    fields: dict = {}
    for part in (spec or "").split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError(f"目标参数格式应为 key=value：{part!r}")
        key, value = part.split("=", 1)
        fields[key.strip()] = value.strip()
    missing = [k for k in ("url", "model") if not fields.get(k)]
    if missing:
        raise ValueError(f"目标缺少 {', '.join(missing)}：{spec!r}")
    api_key = fields.get("key", "")
    if fields.get("key_env"):
        api_key = env.get(fields["key_env"], "")
        if not api_key:
            raise ValueError(f"环境变量 {fields['key_env']} 未设置")
    try:
        cost = Decimal(fields.get("cost") or "0")
    except InvalidOperation as exc:
        raise ValueError(f"cost 不是数字：{fields.get('cost')!r}") from exc
    name = fields.get("name") or fields["model"]
    # 与 LlmEndpoint.api_endpoint 同口径：不带 /v1（路由器自己拼 /v1/chat/completions），多写了就去掉
    base_url = fields["url"].rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[: -len("/v1")]
    return Target(name=name, base_url=base_url, model=fields["model"], api_key=api_key, cost_per_1k=cost)


def target_from_config() -> Target | None:
    """读取当前库里智能助手正在用的端点 + 模型（须在切换到临时库之前调用）。"""
    from smart_assistant.models import LlmAppConfig

    config = (
        LlmAppConfig.objects.filter(app_name="smart_assistant", is_active=True, endpoint__isnull=False)
        .select_related("endpoint")
        .first()
    )
    if config is None or not config.endpoint.api_endpoint:
        return None
    endpoint = config.endpoint
    return Target(
        name=f"当前配置:{endpoint.name}",
        base_url=endpoint.api_endpoint,
        model=config.model_name or "",
        api_key=endpoint.api_key or "",
        cost_per_1k=endpoint.cost_per_1k_tokens or Decimal("0"),
    )


def select_cases(patterns=None, directory=None):
    """加载、过滤并校验用例；引用了未注册工具或未知标记时抛 ``CaseError``。"""
    from smart_assistant.capabilities import capabilities
    from smart_assistant.tools.registry import ToolRegistry

    cases = filter_cases(load_cases(directory), patterns or [])
    # 能力目录里声明的工具都算已知（含默认关闭的删除类工具：注入用例正是要验证它点不动）
    known = set(ToolRegistry._tools) | {spec.intent for spec in capabilities.specs(include_disabled=True)}
    problems = validate_cases(cases, tool_names=known, canary_keys=CANARY_SPECS.keys())
    if problems:
        raise CaseError("用例校验失败：\n" + "\n".join(problems))
    return cases


def run_suite(
    cases, *, mode: str = "scripted", targets=None, paths=PATHS, repeat: int = 1, on_result=None
) -> SuiteResult:
    """在当前数据库上造种子数据并跑完全部目标。剧本模式忽略 ``targets``。"""
    started = timezone.now()
    scripted = mode == "scripted"
    run_targets = [Target.scripted()] if scripted else list(targets or [])
    if not run_targets:
        raise ValueError("真模型模式至少需要一个目标（--target 或 --from-config）")
    results: list = []
    with isolated_runtime():
        world = build_world()
        for target in run_targets:
            runner = EvalRunner(world, target=target, scripted=scripted)
            results.extend(runner.run(cases, paths=paths, repeat=repeat, on_result=on_result))
    report = build_report(results, mode=mode, targets=run_targets, cases=cases, started_at=started)
    return SuiteResult(report=report, results=results, world=world)
