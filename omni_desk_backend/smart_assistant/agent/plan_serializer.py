"""Plan 序列化 — multi-tool chain 的 JSON 持久化与恢复。

Task 1 of feat/sa-multi-tool-chain: 让 plan 可序列化、可断点恢复。

数据结构::

    Plan
    └── steps: list[PlanStep]
        ├── tool: str            # 工具名
        ├── params: dict         # 参数(支持 {{step1.output.xxx}} 嵌套引用)
        ├── on_failure: str      # skip | retry | fallback(默认 skip)
        └── retry_count: int     # retry 策略时使用(默认 2)

使用示例::

    plan = Plan(steps=[PlanStep(tool="schedule", params={"query": "张三"})])
    record = ToolChainPlan.objects.create(user=user, plan_data=plan.to_dict())
    restored = Plan.from_dict(record.plan_data)
"""

from dataclasses import asdict, dataclass, field

VALID_ON_FAILURE = {"skip", "retry", "fallback"}


class PlanValidationError(ValueError):
    """Plan 校验失败。"""


@dataclass
class PlanStep:
    """单个工具调用步骤。"""

    tool: str
    params: dict
    on_failure: str = "skip"
    retry_count: int = 2

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        on_failure = d.get("on_failure", "skip")
        if on_failure not in VALID_ON_FAILURE:
            raise PlanValidationError(
                f"on_failure 必须是 {VALID_ON_FAILURE} 之一,收到: {on_failure!r}"
            )
        return cls(
            tool=d["tool"],
            params=d.get("params", {}),
            on_failure=on_failure,
            retry_count=d.get("retry_count", 2),
        )


@dataclass
class Plan:
    """多工具链执行计划。"""

    steps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"steps": [step.to_dict() for step in self.steps]}

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(steps=[PlanStep.from_dict(s) for s in d.get("steps", [])])
