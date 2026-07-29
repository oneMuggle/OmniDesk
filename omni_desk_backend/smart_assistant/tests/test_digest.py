"""每日晨报(digest)与推送任务(send_daily_digests / send_single_digest)单元测试。

覆盖:
- generate_daily_digest:
    * mock orchestrator 聚合链路 → 返回包含日期/模块统计/重点条目的 Markdown;
    * 传入 scope-aware ToolContext(superuser → GLOBAL);
    * orchestrator 抛异常 → 返回 None 不抛;
    * orchestrator 返回失败回答(error=True) → 返回 None;
    * 未命中聚合链路的降级路径 → 采用 answer 渲染。
- send_daily_digests(派发层):
    * 为每个目标用户(is_active + is_staff)dispatch 一个 send_single_digest 子任务;
    * 非 staff 用户不派发;主任务自身不直接写 Notification;
    * 无目标用户时派发数为 0 且不抛。
- send_single_digest(单用户子任务):
    * 成功 → 写一条 system 类型 Notification;
    * generate 返回 None → 不抛、不写通知、success=False;
    * generate 抛异常 → 失败隔离,不抛、不写通知;
    * 用户不存在 → 记日志不抛、success=False;
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
from django.utils import timezone

from notifications.models import Notification
from smart_assistant.digest import generate_daily_digest
from smart_assistant.scope import SmartAssistantScope
from smart_assistant.tasks import send_daily_digests, send_single_digest

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
# send_daily_digests(派发层)
# =============================================================================


@pytest.mark.django_db
class TestSendDailyDigests:
    """晨报主任务测试:仅断言"为每个目标用户 dispatch 了子任务"。

    主任务不再串行执行生成链路,生成/写通知/失败隔离全部下沉到
    ``send_single_digest`` 子任务(见 TestSendSingleDigest)。
    """

    def test_dispatches_subtask_per_target_user(
        self, admin_user_obj, manager_user_obj, regular_user_obj
    ):
        """每个目标用户(staff + active)派发一个子任务;非 staff 用户不派发。"""
        with patch("smart_assistant.tasks.send_single_digest.delay") as mock_delay:
            summary = send_daily_digests()

        # 目标用户仅 admin_user_obj / manager_user_obj;regular_user_obj 非 staff
        assert summary["dispatched"] == 2
        assert summary["date"] == timezone.localdate().isoformat()
        assert mock_delay.call_count == 2
        dispatched_ids = {call.args[0] for call in mock_delay.call_args_list}
        assert dispatched_ids == {admin_user_obj.id, manager_user_obj.id}
        # 主任务只派发,不直接写通知
        assert Notification.objects.filter(dedupe_key__startswith=DIGEST_DEDUPE_PREFIX).count() == 0

    def test_no_target_users_dispatches_nothing(self, regular_user_obj):
        """无目标用户(仅存在非 staff 用户)→ 派发数为 0,不抛异常。"""
        with patch("smart_assistant.tasks.send_single_digest.delay") as mock_delay:
            summary = send_daily_digests()

        assert summary["dispatched"] == 0
        mock_delay.assert_not_called()


# =============================================================================
# send_single_digest(单用户子任务)
# =============================================================================


@pytest.mark.django_db
class TestSendSingleDigest:
    """单用户晨报子任务测试(mock 掉 generate_daily_digest,真实写 Notification)。"""

    def test_success_creates_notification(self, admin_user_obj):
        """生成成功 → 写一条 system 类型晨报通知,返回 success=True。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value="# 晨报\n测试正文"):
            result = send_single_digest(admin_user_obj.id)

        assert result["user_id"] == admin_user_obj.id
        assert result["success"] is True

        notifications = Notification.objects.filter(dedupe_key__startswith=DIGEST_DEDUPE_PREFIX)
        assert notifications.count() == 1
        notification = notifications.first()
        assert notification.user_id == admin_user_obj.id
        assert notification.type == "system"
        assert "智能助手每日晨报" in notification.title
        assert timezone.localdate().isoformat() in notification.title
        assert notification.content.startswith("# 晨报")
        assert notification.is_read is False

    def test_generate_returning_none_does_not_raise(self, admin_user_obj):
        """generate 返回 None(生成失败)→ 不抛、不写通知、success=False。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value=None):
            result = send_single_digest(admin_user_obj.id)

        assert result["success"] is False
        assert result["reason"] == "generate_failed"
        assert Notification.objects.filter(user=admin_user_obj).count() == 0

    def test_generate_exception_is_isolated(self, admin_user_obj):
        """generate 抛异常(写通知失败等)→ 失败隔离:不向 Celery 抛,不写通知。"""
        with patch(
            "smart_assistant.digest.generate_daily_digest", side_effect=RuntimeError("编排器异常")
        ):
            result = send_single_digest(admin_user_obj.id)

        assert result["success"] is False
        assert result["reason"] == "exception"
        assert Notification.objects.filter(user=admin_user_obj).count() == 0

    def test_missing_user_logs_and_does_not_raise(self):
        """用户不存在(派发后被删除)→ 记日志不抛,success=False。"""
        result = send_single_digest(999999)

        assert result["success"] is False
        assert result["reason"] == "user_not_found"

    def test_same_day_rerun_is_deduped(self, admin_user_obj):
        """当日重复执行(beat 重投/子任务重试)→ dedupe_key 去重,仅一条晨报。"""
        with patch("smart_assistant.digest.generate_daily_digest", return_value="# 晨报"):
            first = send_single_digest(admin_user_obj.id)
            second = send_single_digest(admin_user_obj.id)

        assert first["success"] is True
        assert second["success"] is True  # Service 合并到原通知,仍计成功
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
