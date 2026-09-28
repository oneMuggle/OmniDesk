"""S4-1：创建首批三个数字员工角色。

个人秘书默认开启（接替原每日晨报，保持推送不中断）；排班管理员、合规专员是新的
主动行为，默认关闭，由管理员在「AI 管理 → 数字员工」页开启。
"""

from django.db import migrations

PROFILES = [
    {
        "key": "secretary",
        "name": "个人秘书",
        "description": "工作日早上汇总每个人今天的备忘、值班、会议和待处理的换班申请，推送晨报。",
        "system_prompt": "你是个人秘书。根据给定的晨报数据，用一句话提醒用户今天最需要注意的事情，不超过 60 字，不要编造数据。",
        "toolsets": ["memo", "schedule", "meeting_room", "swap_request"],
        "data_scope": "仅本人数据",
        "trigger": "beat",
        "schedule_label": "工作日 08:30",
        "enabled": True,
        "daily_llm_quota": 0,
        "daily_action_quota": 500,
    },
    {
        "key": "scheduler",
        "name": "排班管理员",
        "description": "巡检未来 7 天的排班冲突；值班人员当天是试验责任人时，推荐接替人并请当事人确认发起换班。",
        "system_prompt": "",
        "toolsets": ["schedule", "trial", "swap_request"],
        "data_scope": "未来 7 天排班",
        "trigger": "beat",
        "schedule_label": "工作日 16:00",
        "enabled": False,
        "daily_llm_quota": 0,
        "daily_action_quota": 50,
    },
    {
        "key": "compliance",
        "name": "合规专员",
        "description": "跟踪 3 天内到期和已逾期的合规问题，汇总提醒项目负责人，并为逾期或紧急问题起草整改建议。",
        "system_prompt": (
            "你是质量合规专员。根据合规问题的类型、描述和位置，给出不超过 5 条可执行的整改建议，"
            "每条一行，以“- ”开头，总字数不超过 300 字。不要编造法规条款编号。"
        ),
        "toolsets": ["compliance", "memo"],
        "data_scope": "负责人名下的合规问题",
        "trigger": "beat",
        "schedule_label": "工作日 09:10",
        "enabled": False,
        "daily_llm_quota": 50,
        "daily_action_quota": 100,
    },
]


def seed(apps, schema_editor):
    AgentProfile = apps.get_model("smart_assistant", "AgentProfile")
    for data in PROFILES:
        AgentProfile.objects.get_or_create(key=data["key"], defaults=data)


def unseed(apps, schema_editor):
    AgentProfile = apps.get_model("smart_assistant", "AgentProfile")
    AgentProfile.objects.filter(key__in=[p["key"] for p in PROFILES]).delete()


class Migration(migrations.Migration):
    dependencies = [("smart_assistant", "0020_agent_staff")]

    operations = [migrations.RunPython(seed, unseed)]
