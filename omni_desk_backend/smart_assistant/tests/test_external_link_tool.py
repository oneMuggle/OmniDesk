"""ExternalLinkTool 测试 — 任务 3.1.

数据源:external_integration.ExternalLink
"""
import pytest

from external_integration.models import ExternalLink
from smart_assistant.tools.external_link_tool import ExternalLinkTool
from smart_assistant.tools.tool_context import ToolContext


@pytest.fixture
def tool():
    return ExternalLinkTool()


@pytest.fixture
def links(db):
    return [
        ExternalLink.objects.create(
            name="公司VPN", url="https://vpn.example.com",
            category="网络", description="VPN 登录地址", is_active=True
        ),
        ExternalLink.objects.create(
            name="Jira", url="https://jira.example.com",
            category="研发", is_active=True
        ),
        ExternalLink.objects.create(
            name="已废弃链接", url="https://old.example.com",
            category="其他", is_active=False
        ),
    ]


@pytest.mark.django_db
def test_fuzzy_match_name(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("VPN", ctx)
    assert result["found"] is True
    assert any("VPN" in l["name"] for l in result["links"])


@pytest.mark.django_db
def test_excludes_inactive(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("链接", ctx)
    names = [l["name"] for l in result["links"]]
    assert "已废弃链接" not in names


@pytest.mark.django_db
def test_match_in_description(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("登录地址", ctx)
    assert any("VPN" in l["name"] for l in result["links"])


@pytest.mark.django_db
def test_list_by_category(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("研发", ctx)
    assert all(l["category"] == "研发" for l in result["links"])


@pytest.mark.django_db
def test_sso_enabled_flag(tool, links):
    ExternalLink.objects.filter(name="公司VPN").update(sso_enabled=True)
    ctx = ToolContext(user="u")
    result = tool.execute("VPN", ctx)
    vpn = next(l for l in result["links"] if "VPN" in l["name"])
    assert vpn["sso_enabled"] is True


@pytest.mark.django_db
def test_empty_result(tool):
    ctx = ToolContext(user="u")
    result = tool.execute("xyz123", ctx)
    assert result["found"] is False


@pytest.mark.django_db
def test_no_keywords_returns_recent(tool, links):
    ctx = ToolContext(user="u")
    result = tool.execute("所有链接", ctx)
    # 应返回所有 active 链接
    assert result["count"] == 2


def test_required_auth_and_intent(tool):
    assert tool.required_auth is True
    assert tool.intent_type == "external_link_query"
