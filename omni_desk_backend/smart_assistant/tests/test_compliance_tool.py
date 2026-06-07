"""ComplianceTool 测试 - 合规问题/待整改项查询工具.

对应交接文档任务 2.1:
- 数据源:compliance.ComplianceIssue
- 过滤:未完成(status IN 待处理/处理中)
- 关键词匹配:description / issue_type / project.name
- 紧急程度过滤:severity="紧急"
- 即将到期过滤:due_date <= today+7
- 上限 10 条,按 severity 倒序
- N+1 防护:select_related("project", "document_book", "document_template")
"""

from datetime import date, timedelta

import pytest

from compliance.models import ComplianceIssue
from documents.models import Book
from projects.models import Project
from smart_assistant.tools.compliance_tool import ComplianceTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def tool():
    return ComplianceTool()


@pytest.fixture
def issue_setup(db, admin_user_obj):
    """创建项目+书籍+几个合规问题(描述含业务关键词"整改",以通过关键词过滤)"""
    project = Project.objects.create(name="P1")
    book = Book.objects.create(title="B1", project=project)
    pending = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="需要整改", status="待处理"
    )
    resolved = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="需要整改", status="已解决"
    )
    return {"project": project, "book": book, "pending": pending, "resolved": resolved}


@pytest.mark.django_db
def test_query_pending_only(tool, issue_setup):
    ctx = ToolContext(user="u")
    result = tool.execute("待整改", ctx)
    assert result["found"] is True
    statuses = [i["status"] for i in result["issues"]]
    assert "已解决" not in statuses


@pytest.mark.django_db
def test_filter_by_severity(tool, issue_setup):
    # description 包含关键词"紧急",以通过关键词过滤
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="紧急整改", severity="紧急", status="待处理"
    )
    ctx = ToolContext(user="u")
    result = tool.execute("紧急", ctx)
    severities = [i["severity"] for i in result["issues"]]
    assert all(s == "紧急" for s in severities)


@pytest.mark.django_db
def test_keyword_in_description(tool, issue_setup):
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="缺少签字", status="待处理"
    )
    ctx = ToolContext(user="u")
    result = tool.execute("签字", ctx)
    assert any("签字" in i["description"] for i in result["issues"])


@pytest.mark.django_db
def test_due_soon_includes_due_date(tool, issue_setup):
    soon = date.today() + timedelta(days=3)
    # description 包含关键词"即将到期",以通过关键词过滤
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="即将到期整改", status="待处理", due_date=soon
    )
    ctx = ToolContext(user="u")
    result = tool.execute("即将到期", ctx)
    assert any(i.get("due_date") == soon.isoformat() for i in result["issues"])


@pytest.mark.django_db
def test_empty_result(tool):
    ctx = ToolContext(user="u")
    result = tool.execute("xyz123不存在", ctx)
    assert result["found"] is False


@pytest.mark.django_db
def test_severity_ordering_business_priority(tool, db):
    """回归测试:severity 按业务优先级排序(紧急 > 高 > 中 > 低),
    不是按 CharField 字典序(高 > 紧 > 低 > 中 是错的)。
    不依赖 issue_setup,自己创建项目以避免 fixture 的默认 severity="中" 污染结果。"""
    project = Project.objects.create(name="P1")
    expected_order = ["紧急", "高", "中", "低"]
    for sev in expected_order:
        ComplianceIssue.objects.create(
            project=project, issue_type="其他",
            description=f"{sev}级整改", severity=sev, status="待处理"
        )
    ctx = ToolContext(user="u")
    result = tool.execute("整改", ctx)
    severities = [i["severity"] for i in result["issues"]]
    assert severities == expected_order


@pytest.mark.django_db
def test_no_n_plus_1(tool, issue_setup):
    """回归测试:用足够多的 issue + 精确查询数,确保 select_related 真的生效。"""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    # 加 5 个待处理 issue 触发 N+1(没 select_related 时每行 +1 query)
    for i in range(5):
        ComplianceIssue.objects.create(
            project=issue_setup["project"], issue_type="其他",
            description=f"issue-{i}", status="待处理"
        )
    with CaptureQueriesContext(connection) as ctx_q:
        tool.execute("待整改", ToolContext(user="u"))
    # 有 select_related 时:1 SELECT(主)+0 N+1= 1 query
    # 无 select_related 时:1 SELECT(主)+ 5 SELECT(author/book/template)= 6+ queries
    assert len(ctx_q.captured_queries) <= 2, (
        f"Too many queries ({len(ctx_q.captured_queries)}); "
        "select_related likely missing on one of the 3 FKs"
    )


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type(tool):
    assert tool.intent_type == "compliance_query"
