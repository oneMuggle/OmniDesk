"""Plan 序列化测试 — multi-tool chain 可序列化到 DB、可从 DB 恢复。

Task 1 of feat/sa-multi-tool-chain: 让 plan 可持久化、可断点恢复。
"""
import pytest

from smart_assistant.agent.plan_serializer import (
    Plan,
    PlanStep,
    PlanValidationError,
)


class TestPlanStep:
    def test_step_to_dict_includes_all_fields(self):
        step = PlanStep(
            tool="schedule",
            params={"query": "张三这周值班"},
            on_failure="skip",
            retry_count=2,
        )
        d = step.to_dict()
        assert d == {
            "tool": "schedule",
            "params": {"query": "张三这周值班"},
            "on_failure": "skip",
            "retry_count": 2,
        }

    def test_step_from_dict_roundtrip(self):
        d = {
            "tool": "schedule",
            "params": {"query": "张三这周值班"},
            "on_failure": "skip",
            "retry_count": 2,
        }
        step = PlanStep.from_dict(d)
        assert step.tool == "schedule"
        assert step.params == {"query": "张三这周值班"}
        assert step.on_failure == "skip"
        assert step.retry_count == 2


class TestPlan:
    def test_plan_to_dict_serializes_steps(self):
        plan = Plan(steps=[
            PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip"),
            PlanStep(tool="memo", params={"title": "{{step1.output.summary}}"}, on_failure="retry"),
        ])
        d = plan.to_dict()
        assert "steps" in d
        assert len(d["steps"]) == 2
        assert d["steps"][1]["params"]["title"] == "{{step1.output.summary}}"

    def test_plan_from_dict_roundtrip(self):
        d = {
            "steps": [
                {"tool": "schedule", "params": {"query": "张三"}, "on_failure": "skip"},
                {"tool": "memo", "params": {"title": "x"}, "on_failure": "skip"},
            ]
        }
        plan = Plan.from_dict(d)
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "schedule"

    def test_plan_invalid_on_failure_raises(self):
        with pytest.raises(PlanValidationError) as exc:
            PlanStep.from_dict({"tool": "x", "params": {}, "on_failure": "invalid_value"})
        assert "on_failure" in str(exc.value)


@pytest.mark.django_db
class TestToolChainPlanModel:
    def test_save_and_load_plan(self, admin_user_obj):
        from smart_assistant.models import ToolChainPlan

        plan = Plan(steps=[PlanStep(tool="schedule", params={"query": "张三"}, on_failure="skip")])
        record = ToolChainPlan.objects.create(
            user=admin_user_obj,
            plan_data=plan.to_dict(),
            status="pending",
        )

        loaded = ToolChainPlan.objects.get(id=record.id)
        restored = Plan.from_dict(loaded.plan_data)
        assert len(restored.steps) == 1
        assert restored.steps[0].tool == "schedule"