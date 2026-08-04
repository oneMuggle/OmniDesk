"""换班工具单元测试(SwapRequestQuery/Create/Decide)"""

import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model

from smart_assistant.tools.swap_request_tool import (
    SwapRequestQueryTool,
    SwapRequestCreateTool,
    SwapRequestDecideTool,
)
from events.models import Schedule, ScheduleSwapRequest
from personnel.models import Personnel

User = get_user_model()


@pytest.fixture
def personnel_a(db):
    return Personnel.objects.create(name="张三")


@pytest.fixture
def personnel_b(db):
    return Personnel.objects.create(name="李四")


@pytest.fixture
def user_a(db, personnel_a):
    return User.objects.create_user(username="user_a", password="test", personnel=personnel_a)


@pytest.fixture
def user_b(db, personnel_b):
    return User.objects.create_user(username="user_b", password="test", personnel=personnel_b)


@pytest.fixture
def schedule_a(db, personnel_a):
    from datetime import date, timedelta
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=7),
        duty_person=personnel_a,
    )


@pytest.fixture
def schedule_b(db, personnel_b):
    from datetime import date, timedelta
    return Schedule.objects.create(
        duty_date=date.today() + timedelta(days=7),
        duty_person=personnel_b,
    )


@pytest.fixture
def swap_request(db, personnel_a, personnel_b, schedule_a):
    from datetime import timedelta
    from django.utils import timezone
    return ScheduleSwapRequest.objects.create(
        requester=personnel_a,
        target_personnel=personnel_b,
        original_schedule=schedule_a,
        reason="测试换班",
        expires_at=timezone.now() + timedelta(hours=48),
    )


# ---------------------------------------------------------------------------
# SwapRequestQueryTool 测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSwapRequestQueryTool:
    """查询工具测试"""

    def test_query_no_user(self):
        """未登录用户返回 found=False"""
        tool = SwapRequestQueryTool()
        result = tool.execute(query="查询换班", context=None)

        assert result["found"] is False
        assert "未登录" in result["message"]

    def test_query_no_personnel(self, db):
        """用户未关联 personnel 返回 found=False"""
        user_no_personnel = User.objects.create_user(username="no_personnel", password="test")
        tool = SwapRequestQueryTool()
        context = MagicMock()
        context.user = user_no_personnel

        result = tool.execute(query="查询换班", context=context)

        assert result["found"] is False
        assert "未关联人员档案" in result["message"]

    def test_query_empty(self, personnel_a, user_a):
        """无换班申请返回 found=False"""
        tool = SwapRequestQueryTool()
        context = MagicMock()
        context.user = user_a

        result = tool.execute(query="查询换班", context=context)

        assert result["found"] is False
        assert "暂无换班申请" in result["message"]

    def test_query_with_swaps(self, swap_request, personnel_a, user_a):
        """有换班申请返回 found=True"""
        tool = SwapRequestQueryTool()
        context = MagicMock()
        context.user = user_a

        result = tool.execute(query="查询换班", context=context)

        assert result["found"] is True
        assert result["count"] == 1
        assert len(result["swaps"]) == 1
        assert result["swaps"][0]["swap_id"] == swap_request.id
        assert result["swaps"][0]["role"] == "发起方"
        assert result["swaps"][0]["target"] == "李四"


# ---------------------------------------------------------------------------
# SwapRequestCreateTool 测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSwapRequestCreateTool:
    """创建工具测试"""

    def test_create_dry_run(self, user_a, personnel_b, schedule_a):
        """dry_run 模式返回 draft(成功路径:user + target + schedule)"""
        from datetime import date, timedelta
        from smart_assistant.extractors.swap_extractor import CreateParams
        tool = SwapRequestCreateTool()
        context = {"dry_run": True, "user": user_a}
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(
                target_name="李四",
                duty_date=(date.today() + timedelta(days=7)).isoformat(),
                reason="出差",
            ),
        ):
            result = tool.execute(query="我想和李四换班", context=context)
        assert result["found"] is True
        assert "draft" in result
        assert "summary" in result["draft"]  # 新实现返 summary

    def test_create_confirmed(self, user_a):
        """confirmed 模式返回结果"""
        tool = SwapRequestCreateTool()
        context = {"confirmed": True}

        result = tool.execute(query="我想和李四换下周三的班", context=context)

        assert result["found"] is True
        assert "result" in result

    def test_create_fallback(self, user_a):
        """兜底模式返回 found=False"""
        tool = SwapRequestCreateTool()
        context = {}

        result = tool.execute(query="我想和李四换下周三的班", context=context)

        assert result["found"] is False
        assert "异常" in result["message"]


# ---------------------------------------------------------------------------
# SwapRequestCreateTool._dry_run 业务测试(Task 8)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSwapRequestCreateDryRun:
    """SwapRequestCreateTool._dry_run 各场景"""

    def test_dry_run_no_user(self):
        """ctx 无 user → found=False"""
        tool = SwapRequestCreateTool()
        result = tool._dry_run("我想和李四换班", ctx={})
        assert result["found"] is False
        assert "未关联" in result["message"]

    def test_dry_run_extractor_returns_none(self, user_a):
        """LLM 解析失败 → found=False"""
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=None,
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("模糊 query", ctx={"user": user_a})
        assert result["found"] is False
        assert "无法识别" in result["message"]

    def test_dry_run_target_not_found(self, user_a):
        """目标人不存在 → found=False 说明'未找到'"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="不存在的名字", duty_date="2026-08-12"),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "未找到" in result["message"]

    def test_dry_run_schedule_not_found(self, user_a, personnel_b):
        """该日 requester 无排班 → found=False"""
        from datetime import date, timedelta
        from smart_assistant.extractors.swap_extractor import CreateParams
        past = date.today() - timedelta(days=30)
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="李四", duty_date=past.isoformat()),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "找不到您" in result["message"]

    def test_dry_run_self_swap(self, user_a, personnel_a):
        """target == requester → found=False"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(target_name="张三", duty_date="2026-08-12"),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is False
        assert "不能把班换给自己" in result["message"]

    def test_dry_run_success(self, user_a, personnel_b, schedule_a):
        """所有校验通过 → 返 draft"""
        from smart_assistant.extractors.swap_extractor import CreateParams
        with patch(
            "smart_assistant.tools.swap_request_tool.extract_create_params",
            return_value=CreateParams(
                target_name="李四", duty_date=schedule_a.duty_date.isoformat(), reason="出差"
            ),
        ):
            tool = SwapRequestCreateTool()
            result = tool._dry_run("query", ctx={"user": user_a})
        assert result["found"] is True
        assert "draft" in result
        draft = result["draft"]
        assert "fields" in draft
        assert draft["fields"]["target_personnel_id"] == personnel_b.id
        assert draft["fields"]["original_schedule_id"] == schedule_a.id
        assert draft["fields"]["reason"] == "出差"


# ---------------------------------------------------------------------------
# SwapRequestDecideTool 测试
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSwapRequestDecideTool:
    """决策工具测试"""

    def test_decide_dry_run(self, user_b):
        """dry_run 模式返回 draft"""
        tool = SwapRequestDecideTool()
        context = {"dry_run": True}

        result = tool.execute(query="同意张三的换班申请", context=context)

        assert result["found"] is True
        assert "draft" in result
        assert "summary" in result["draft"]

    def test_decide_confirmed(self, user_b):
        """confirmed 模式返回结果"""
        tool = SwapRequestDecideTool()
        context = {"confirmed": True}

        result = tool.execute(query="同意张三的换班申请", context=context)

        assert result["found"] is True
        assert "result" in result

    def test_decide_fallback(self, user_b):
        """兜底模式返回 found=False"""
        tool = SwapRequestDecideTool()
        context = {}

        result = tool.execute(query="同意张三的换班申请", context=context)

        assert result["found"] is False
        assert "异常" in result["message"]
