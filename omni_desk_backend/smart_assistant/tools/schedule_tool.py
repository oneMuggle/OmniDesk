from datetime import timedelta
from django.utils import timezone
from events.models import Schedule
from .base import BaseTool


class ScheduleTool(BaseTool):
    name = "schedule_query"
    description = "查询排班、值班安排"
    intent_type = "schedule_query"
    risk_level = "read"  # 显式声明:只读查询工具,无副作用

    def execute(self, query=None, context=None, params=None, scope=None, qs=None) -> dict:
        """查询排班。

        支持两种调用方式(向后兼容):
        - 旧:execute(query, context) — 由 ToolChainExecutor 旧路径调用
        - 新:execute(params, scope, qs) — 由跨模块汇总新路径调用
        """
        # 新路径(跨模块汇总)
        if qs is not None and scope is not None:
            target_date = timezone.now().date()
            if params:
                if params.get("date") == "明天":
                    target_date = (timezone.now() + timedelta(days=1)).date()
                elif params.get("date") == "后天":
                    target_date = (timezone.now() + timedelta(days=2)).date()
            schedules = qs.filter(duty_date=target_date)
            results = [
                {
                    "duty_date": str(s.duty_date),
                    "duty_person": s.duty_person.name if s.duty_person else "未安排",
                    "duty_leader": s.duty_leader.name if s.duty_leader else "未安排",
                }
                for s in schedules
            ]
            return {
                "date": str(target_date),
                "found": bool(results),
                "count": len(results),
                "schedules": results,
                "module_label": "排班",
            }

        # 旧路径(向后兼容)
        target_date = timezone.now().date()
        if query:
            if "明天" in query:
                target_date = (timezone.now() + timedelta(days=1)).date()
            elif "后天" in query:
                target_date = (timezone.now() + timedelta(days=2)).date()
            elif "昨天" in query:
                target_date = (timezone.now() - timedelta(days=1)).date()
        schedules = Schedule.objects.filter(duty_date=target_date).select_related("duty_person", "duty_leader")
        if not schedules.exists():
            return {"date": str(target_date), "found": False, "message": f"{target_date} 暂无排班记录"}
        results = [
            {
                "duty_date": str(s.duty_date),
                "duty_person": s.duty_person.name if s.duty_person else "未安排",
                "duty_leader": s.duty_leader.name if s.duty_leader else "未安排",
            }
            for s in schedules
        ]
        return {"date": str(target_date), "found": True, "schedules": results}

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "intent_type": self.intent_type,
            # 与 BaseTool.get_schema 保持一致:暴露风险等级供执行器/前端门控
            "risk_level": self.risk_level,
        }

    @classmethod
    def get_openai_tool_schema(cls) -> dict:
        """OpenAI strict mode tool schema (Task 4 原生 function calling)。

        name 与现有 intent_type 对齐;description 含 2 句中文说明 + 2 个示例 query
        (降低 LLM 选错工具概率);parameters 每层 additionalProperties=false。
        """
        return {
            "type": "function",
            "function": {
                "name": cls.intent_type,
                "description": (
                    "查询排班/值班信息。支持日期范围、人员姓名、班次类型过滤。"
                    "示例 query: '明天的排班'、'本周张三的值班'。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "自然语言查询,可含日期/人员/班次关键词",
                        },
                        "date_from": {
                            "type": "string",
                            "format": "date",
                            "description": "起始日期(ISO 8601),可选",
                        },
                        "date_to": {
                            "type": "string",
                            "format": "date",
                            "description": "结束日期(ISO 8601),可选",
                        },
                        "personnel_name": {
                            "type": "string",
                            "description": "人员姓名,精确匹配",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        }

    def build_base_queryset(self):
        """返回未过滤的排班 QuerySet。"""
        return Schedule.objects.select_related("duty_person", "duty_leader").all()

    def _scope_self(self, qs, ctx):
        """本人范围:仅返回 ctx.user 名下的排班。

        注:brief 原代码使用 ``duty_person__user``,但 ``Personnel`` 无 ``user`` 字段,
        实际反向关系为 ``user_account``(由 ``CustomUser.personnel = OneToOneField(...)``
        的 ``related_name`` 定义)。此处用 ``user_account`` 与实际模型一致。
        """
        return qs.filter(duty_person__user_account=ctx.user)
