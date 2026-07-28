"""每日晨报(digest)与推送任务(send_daily_digests)单元测试。

覆盖:
- generate_daily_digest:
    * mock orchestrator 聚合链路 → 返回包含日期/模块统计/重点条目的 Markdown;
    * 传入 scope-aware ToolContext(superuser → GLOBAL);
    * orchestrator 抛异常 → 返回 None 不抛;
    * orchestrator 返回失败回答(error=True) → 返回 None;
    * 未命中聚合链路的降级路径 → 采用 answer 渲染。
- send_daily_digests:
    * mock generate → 每个目标用户(is_active + is_staff)一条 Notification;
    * 非 staff 用户不接收;
    * 部分用户失败不影响其余用户;
    * 当日重复执行按 dedupe_key 去重,不产生第二条。
- beat 配置:
    * settings.CELERY_BEAT_SCHEDULE 含 "smart-assistant-daily-digest",
      且 schedule 为 crontab(工作日 8:30)。
"""

from datetime import date
from unittest.mock import patch

import pytest
from celery.schedules import crontab
from django.conf import settings

from notifications.models import Notification
from smart_assistant.digest import generate_daily_digest
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tasks import send_daily_digests

# 固定测试日期:2026-07-29 周三,避免断言随真实日期漂移
FIXED_TODAY = date(2026, 7, 29)

DIGEST_DEDUPE_PREFIX = "smart_assistant_daily_digest:"


def _aggregated_result() -> dict:
    """构造 orchestrator 聚合链路(intent="aggregated_day")的返回结构。

    字段与 AgentOrchestrator._process_chain / ResultSynthesizer 输出保持一致。
    """
    return {
        "answer": "今天共有 3 项安排。",
        "intent": "aggregated_day",
        "tool_used": "schedule_query",
        "tool_result": {
            "summary": "共 3 项：排班 1 条、会议室 1 条、备忘录 1 条",
            "items": [
                {
                    "type": "schedule_query",
                    "module": "排班",
                    "data": {"title": "夜班 18:00-24:00"},
                    "sort_key": "2026-07-29",
                },
                {
                    "type": "meeting_room_query",
                    "module": "会议室",
                    "data": {"name": "周例会 @ 第一会议室"},
                    "sort_key": "2026-07-29",
                },
                {
                    "type": "memo_query",
                    "module": "备忘录",
                    "data": {"content": "提交月度报表"},
                    "sort_key": "9999",  # 无时间字段兜底值,渲染时应被省略
                },
            ],
            "total_count": 3,
            "moduleCounts": {"排班": 1, "会议室": 1, "备忘录": 1},
            "chain_results": [],
        },
        "sources": None,
        "error": False,
    }


# =============================================================================
# generate_daily_digest
# =============================================================================


class TestGenerateDailyDigest:
    """晨报生成逻辑测试(全部 mock 掉 AgentOrchestrator,不触 LLM)。"""

    def test_returns_markdown_with_date_modules_and_items(self, admin_user_obj):
        """聚合链路正常 → Markdown 含日期标题、summary、模块统计与重点条目。"""
        with patch("smart_assistant.digest.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.process.return_value = _aggregated_result()
            markdown = generate_daily_digest(admin_user_obj, today=FIXED_TODAY)

        assert markdown is not None
        # 日期标题(含中文星期)
        assert "# 智能助手每日晨报（2026-07-29 周三）" in markdown
        # summary 与模块统计
        assert "共 3 项" in markdown
        assert "排班：1 条" in markdown
        assert "会议室：1 条" in markdown
        assert "备忘录：1 条" in markdown
        # 重点条目:模块标签 + 摘要;时间兜底值 9999 不出现
        assert "【排班】2026-07-29 夜班 18:00-24:00" in markdown
        assert "【会议室】2026-07-29 周例会 @ 第一会议室" in markdown
        assert "【备忘录】提交月度报表" in markdown
        assert "9999" not in markdown

    def test_passes_scope_aware_tool_context(self, admin_user_obj):
        """process() 收到携带用户与 scope 的 ToolContext(superuser → GLOBAL)。"""
        with patch("smart_assistant.digest.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.process.return_value = _aggregated_result()
            generate_daily_digest(admin_user_obj, today=FIXED_TODAY)

        call_kwargs = mock_orch.return_value.process.call_args.kwargs
        tool_context = call_kwargs["tool_context"]
        assert tool_context.user is admin_user_obj
        assert tool_context.scope == SmartAssistantScope.GLOBAL
        # 晨报为独立巡检,不携带会话历史
        assert call_kwargs["conversation_history"] is None

    def test_orchestrator_exception_returns_none(self, admin_user_obj):
        """orchestrator 抛异常 → 返回 None,不向上传播。"""
        with patch("smart_assistant.digest.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.process.side_effect = RuntimeError("LLM 服务不可用")
            assert generate_daily_digest(admin_user_obj, today=FIXED_TODAY) is None

    def test_error_answer_returns_none(self, admin_user_obj):
        """orchestrator 返回失败回答(error=True) → 视为生成失败返回 None。"""
        failed = _aggregated_result()
        failed["error"] = True
        with patch("smart_assistant.digest.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.process.return_value = failed
            assert generate_daily_digest(admin_user_obj, today=FIXED_TODAY) is None

    def test_non_aggregated_result_falls_back_to_answer(self, admin_user_obj):
        """未命中多工具链(单工具/通用对话) → 降级采用 answer 作为正文,仍含日期标题。"""
        single_tool = {
            "answer": "今日仅有一条排班:白班。",
            "intent": "schedule_query",
            "tool_used": "schedule_query",
            "tool_result": {"found": True},
            "sources": None,
            "error": False,
        }
        with patch("smart_assistant.digest.AgentOrchestrator") as mock_orch:
            mock_orch.return_value.process.return_value = single_tool
            markdown = generate_daily_digest(admin_user_obj, today=FIXED_TODAY)

        assert markdown is not None
        assert "2026-07-29 周三" in markdown
        assert "今日仅有一条排班:白班。" in markdown


# =============================================================================
# send_daily_digests
# =============================================================================


class TestSendDailyDigests:
    """晨报推送 Celery 任务测试(mock 掉 generate_daily_digest,真实写 Notification)。"""

    def test_creates_notification_per_target_user(self, admin_user_obj, manager_user_obj, regular_user_obj):
        """每个目标用户(staff + active)一条晨报;非 staff 用户不接收。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value="# 晨报\n测试正文") as mock_gen:
            summary = send_daily_digests()

        # 目标用户仅 admin_user_obj / manager_user_obj;regular_user_obj 非 staff
        assert summary["total"] == 2
        assert summary["success"] == 2
        assert summary["failed"] == 0
        assert mock_gen.call_count == 2

        notifications = Notification.objects.filter(dedupe_key__startswith=DIGEST_DEDUPE_PREFIX)
        assert notifications.count() == 2
        assert set(notifications.values_list("user__username", flat=True)) == {
            "admin_test",
            "manager_test",
        }
        # Notification 写入字段校验
        notification = notifications.first()
        assert notification.type == "system"
        assert "智能助手每日晨报" in notification.title
        assert summary["date"] in notification.title
        assert notification.content.startswith("# 晨报")
        assert notification.is_read is False

    def test_partial_failure_continues_remaining_users(self, admin_user_obj, manager_user_obj):
        """单个用户生成抛异常 → 该用户跳过,其余用户照常收到晨报。"""

        def fake_generate(user, today=None):
            if user.username == "admin_test":
                raise RuntimeError("编排器异常")
            return "# 晨报正文"

        with patch("smart_assistant.digest.generate_daily_digest", side_effect=fake_generate):
            summary = send_daily_digests()

        assert summary["success"] == 1
        assert summary["failed"] == 1
        # 失败用户无通知,成功用户有且仅有一条
        assert Notification.objects.filter(user=admin_user_obj, type="system").count() == 0
        assert Notification.objects.filter(user=manager_user_obj, type="system").count() == 1

    def test_generate_returning_none_counts_as_failed(self, admin_user_obj):
        """generate 返回 None(生成失败)→ 计失败且不写 Notification,任务不抛。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value=None):
            summary = send_daily_digests()

        assert summary["success"] == 0
        assert summary["failed"] == 1
        assert Notification.objects.filter(user=admin_user_obj).count() == 0

    def test_same_day_rerun_is_deduped(self, admin_user_obj):
        """当日重复执行(beat 重投)→ dedupe_key 去重,同一用户仅一条晨报。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value="# 晨报"):
            first = send_daily_digests()
            second = send_daily_digests()

        assert first["success"] == 1
        assert second["success"] == 1  # Service 合并到原通知,仍计成功
        assert Notification.objects.filter(user=admin_user_obj, type="system").count() == 1


# =============================================================================
# beat 配置
# =============================================================================


class TestBeatSchedule:
    """settings.CELERY_BEAT_SCHEDULE 注册断言。"""

    def test_daily_digest_entry_registered(self):
        """晨报条目存在且指向正确的任务路径。"""
        entry = settings.CELERY_BEAT_SCHEDULE.get("smart-assistant-daily-digest")
        assert entry is not None
        assert entry["task"] == "smart_assistant.tasks.send_daily_digests"
        assert isinstance(entry["schedule"], crontab)

    def test_crontab_is_weekday_8_30(self):
        """schedule 为工作日(周一~周五)8:30。"""
        schedule = settings.CELERY_BEAT_SCHEDULE["smart-assistant-daily-digest"]["schedule"]
        assert schedule.minute == {30}
        assert schedule.hour == {8}
        assert schedule.day_of_week == {1, 2, 3, 4, 5}
