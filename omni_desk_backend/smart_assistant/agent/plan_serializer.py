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

    def __post_init__(self) -> None:
        """构造后立即校验,防止 LLM planner 注入非法 plan。"""
        if not isinstance(self.tool, str) or not self.tool:
            raise PlanValidationError(f"tool 必须是非空字符串,收到: {self.tool!r}")
        if not isinstance(self.params, dict):
            raise PlanValidationError(f"params 必须是 dict,收到: {type(self.params).__name__}")
        if self.on_failure not in VALID_ON_FAILURE:
            raise PlanValidationError(f"on_failure 必须是 {VALID_ON_FAILURE} 之一,收到: {self.on_failure!r}")
        if not isinstance(self.retry_count, int) or self.retry_count < 1:
            raise PlanValidationError(f"retry_count 必须是 >=1 的整数,收到: {self.retry_count!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PlanStep":
        # 委托 __post_init__ 校验,避免重复逻辑
        if not isinstance(d, dict):
            raise PlanValidationError(f"PlanStep.from_dict 期望 dict,收到: {type(d).__name__}")
        return cls(
            tool=d.get("tool", ""),
            params=d.get("params", {}),
            on_failure=d.get("on_failure", "skip"),
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
