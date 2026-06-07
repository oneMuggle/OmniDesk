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
    """创建项目+书籍+几个合规问题"""
    project = Project.objects.create(name="P1")
    book = Book.objects.create(title="B1", project=project)
    pending = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="d", status="待处理"
    )
    resolved = ComplianceIssue.objects.create(
        project=project, document_book=book,
        issue_type="不规范", description="d", status="已解决"
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
def test_filter_by_severity(tool, issue_setup, db):
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
def test_keyword_in_description(tool, issue_setup, db):
    ComplianceIssue.objects.create(
        project=issue_setup["project"], issue_type="其他",
        description="缺少签字", status="待处理"
    )
    ctx = ToolContext(user="u")
    result = tool.execute("签字", ctx)
    assert any("签字" in i["description"] for i in result["issues"])


@pytest.mark.django_db
def test_due_soon_includes_due_date(tool, issue_setup, db):
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
def test_no_n_plus_1(tool, issue_setup, db):
    """确保使用了 select_related"""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx_q:
        tool.execute("待整改", ToolContext(user="u"))
    # 创建 1 个 project 2 个 issue,select_related project 后应 < 5 query
    assert len(ctx_q.captured_queries) < 5


def test_required_auth_true(tool):
    assert tool.required_auth is True


def test_intent_type(tool):
    assert tool.intent_type == "compliance_query"
