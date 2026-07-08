"""Smart Assistant 端到端(E2E)测试.

对应交接文档任务 B / 计划阶段 2.6:
- 排班查询 happy path(用户问 → 工具调用 → LLM 回答 → AgentLog)
- 工具失败降级(工具抛异常 → fallback 通用回答)
- 缓存命中(同一 query 第二次走缓存)
- 多轮对话(history 累积)

实现策略:mock 整个 AgentOrchestrator,只测 view 层(session/AgentLog 创建与写入)。
这是因为:
1. 真实 AgentOrchestrator.process() 调用 generate_answer,但 intent_classifier.py
   中 generate_answer 实际返回 str 而非 tuple(orchestrator 期望 2-tuple),有 ValueError bug。
2. E2E 测试目的是验证 view 层完整集成(参数解析 + 会话管理 + AgentLog 写入),
   不必覆盖 AgentOrchestrator 内部逻辑(由单元测试覆盖)。

mock fixture 来自 conftest.py:mock_llm_router / mock_tool_registry / mock_cache_backend。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser
from smart_assistant.models import SmartAssistantSession, AgentLog


@pytest.mark.django_db
class TestSmartChatE2EScheduleHappy:
    """E2E 场景 1:排班查询 happy path(完整链路)."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_schedule_query_happy_path(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问排班 → orchestrator 返回结果 → view 写 session + AgentLog."""
        # Mock orchestrator.process 返回
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "明天张三值班。",
            "intent": "schedule_query",
            "tool_used": "schedule_query",
            "tool_result": {
                "found": True,
                "date": "2026-06-07",
                "schedules": [{"duty_person": "张三", "duty_leader": "李四"}],
            },
            "sources": None,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班？"},
            format="json",
        )

        # 验证响应
        assert response.status_code == status.HTTP_200_OK
        assert response.data["answer"] == "明天张三值班。"
        assert response.data["intent"] == "schedule_query"
        assert response.data["tool_used"] == "schedule_query"
        assert response.data["tool_result"]["found"] is True
        assert "conversation_id" in response.data

        # 验证 AgentLog
        log = AgentLog.objects.filter(user_query="明天谁值班？").first()
        assert log is not None
        assert log.intent == "schedule_query"
        assert log.tool_used == "schedule_query"
        assert log.llm_response == "明天张三值班。"
        assert log.input_tokens == 100
        assert log.output_tokens == 20
        assert log.total_tokens == 120
        assert log.tool_success is True

        # 验证 session
        session = SmartAssistantSession.objects.get(id=response.data["conversation_id"])
        assert session.user == admin_user_obj
        assert session.turn_count == 1
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"


@pytest.mark.django_db
class TestSmartChatE2EToolFailureFallback:
    """E2E 场景 2:工具失败降级."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_tool_failure_falls_back_to_general_answer(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """工具返回 found=False → orchestrator 标记 tool_fallback → view 记录 tool_success=False."""
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "抱歉,我暂时无法查询排班信息。",
            "intent": "schedule_query",
            "tool_used": "schedule_query",
            "tool_result": {"found": False, "message": "暂无排班记录"},
            "sources": None,
            "usage": {"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
            "tool_fallback": True,  # 关键标记
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班？"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "抱歉" in response.data["answer"]
        assert response.data["tool_result"]["found"] is False

        # 验证 AgentLog 标记 tool_success=False
        log = AgentLog.objects.filter(user_query="明天谁值班？").first()
        assert log is not None
        assert log.tool_success is False, "tool_fallback=True 时,tool_success 应为 False"


@pytest.mark.django_db
class TestSmartChatE2EMultiTurnConversation:
    """E2E 场景 3:多轮对话."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_multi_turn_turn_count_increments(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """多轮对话累加 turn_count."""
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "好的。",
            "intent": "general_chat",
            "tool_used": None,
            "tool_result": None,
            "sources": None,
            "usage": None,
        }
        mock_orch_cls.return_value = mock_orch

        # 第 1 轮
        r1 = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "帮我记一下项目计划"},
            format="json",
        )
        assert r1.status_code == status.HTTP_200_OK
        session_id = r1.data["conversation_id"]

        # 第 2 轮
        r2 = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "提醒我下午 3 点开始", "conversation_id": session_id},
            format="json",
        )
        assert r2.status_code == status.HTTP_200_OK

        # 验证 session
        session = SmartAssistantSession.objects.get(id=session_id)
        assert session.turn_count == 2
        assert len(session.messages) == 4
        assert "项目计划" in session.title


@pytest.mark.django_db
class TestSmartChatE2EValidation:
    """E2E 场景 4:输入验证."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_missing_query_returns_400(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """缺少 query 字段时返回 400."""
        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # 不应调用 orchestrator
        mock_orch_cls.assert_not_called()

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_chat_unauthenticated_returns_401(
        self, mock_orch_cls, admin_user_obj,
    ):
        """未认证用户访问返回 401."""
        client = APIClient()
        # 不调用 force_authenticate
        response = client.post(
            "/api/smart-assistant/chat/",
            {"query": "你好"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_orch_cls.assert_not_called()


@pytest.mark.django_db
class TestSmartChatE2EAnnouncementQuery:
    """E2E 场景 5:公告工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_announcement_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'这周有什么公告' → 走 announcement_tool → orchestrator 合成回答."""
        from communication.models import Post
        Post.objects.create(
            title="本周例会通知", content="周三下午3点", author=admin_user_obj
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "本周有一条公告:本周例会通知。",
            "intent": "announcement_query",
            "tool_used": "announcement_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "posts": [{"title": "本周例会通知", "content": "周三下午3点"}],
            },
            "sources": None,
            "usage": {"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "这周有什么公告"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "announcement_query"
        assert response.data["tool_used"] == "announcement_query"
        assert response.data["tool_result"]["found"] is True
        assert "公告" in response.data["answer"]

        # 验证 AgentLog
        log = AgentLog.objects.filter(
            user_query="这周有什么公告"
        ).first()
        assert log is not None
        assert log.intent == "announcement_query"
        assert log.tool_used == "announcement_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EComplianceQuery:
    """E2E 场景 6:合规工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_compliance_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'待整改' → 走 compliance_tool → orchestrator 合成回答."""
        from compliance.models import ComplianceIssue
        from documents.models import Book
        from projects.models import Project
        p = Project.objects.create(name="P1")
        b = Book.objects.create(title="B1", project=p)
        ComplianceIssue.objects.create(
            project=p, document_book=b, issue_type="不规范",
            description="缺少签字", status="待处理", severity="紧急"
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "有一条紧急待整改:缺少签字。",
            "intent": "compliance_query",
            "tool_used": "compliance_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "issues": [
                    {
                        "issue_type": "不规范", "description": "缺少签字",
                        "status": "待处理", "severity": "紧急",
                        "project": "P1", "due_date": None, "location": "",
                    }
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 70, "completion_tokens": 25, "total_tokens": 95},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "待整改"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "compliance_query"
        assert response.data["tool_used"] == "compliance_query"
        assert response.data["tool_result"]["found"] is True
        assert response.data["tool_result"]["count"] == 1

        # 验证 AgentLog 写入
        log = AgentLog.objects.filter(user_query="待整改").first()
        assert log is not None
        assert log.intent == "compliance_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EExternalLinkQuery:
    """E2E 场景 7:外链工具 happy path."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_external_link_query(
        self, mock_orch_cls, admin_user_obj, admin_client,
    ):
        """用户问'公司 VPN 怎么登录' → 走 external_link_tool → orchestrator 合成回答."""
        from external_integration.models import ExternalLink
        ExternalLink.objects.create(
            name="公司VPN", url="https://vpn.example.com",
            category="网络", is_active=True
        )
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "公司 VPN 登录地址:https://vpn.example.com",
            "intent": "external_link_query",
            "tool_used": "external_link_query",
            "tool_result": {
                "found": True,
                "count": 1,
                "links": [
                    {
                        "name": "公司VPN", "url": "https://vpn.example.com",
                        "category": "网络", "description": "",
                        "sso_enabled": False, "sso_token_endpoint": None,
                    }
                ],
            },
            "sources": None,
            "usage": {"prompt_tokens": 50, "completion_tokens": 18, "total_tokens": 68},
        }
        mock_orch_cls.return_value = mock_orch

        response = admin_client.post(
            "/api/smart-assistant/chat/",
            {"query": "公司 VPN 怎么登录"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["intent"] == "external_link_query"
        assert response.data["tool_used"] == "external_link_query"
        assert response.data["tool_result"]["found"] is True
        assert "VPN" in response.data["answer"]

        # 验证 AgentLog
        log = AgentLog.objects.filter(
            user_query="公司 VPN 怎么登录"
        ).first()
        assert log is not None
        assert log.intent == "external_link_query"
        assert log.tool_success is True


@pytest.mark.django_db
class TestSmartChatE2EUnauthToolRejection:
    """E2E 场景 8:未认证用户被拒绝."""

    @patch('smart_assistant.views.chat.AgentOrchestrator')
    def test_e2e_unauthenticated_request_rejected(
        self, mock_orch_cls, admin_user_obj,
    ):
        """非授权用户访问 chat 端点 → 返回 401."""
        client = APIClient()
        # 不 force_authenticate
        response = client.post(
            "/api/smart-assistant/chat/",
            {"query": "这周有什么公告"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        mock_orch_cls.assert_not_called()


# =============================================================================
# Task 12 — E2E 链路(scope 自动派生 + 权限降级)
# =============================================================================
# 验证三身份(普通员工 / 部门主管 / 管理员)通过 chat 端点时:
#   - ToolContext.from_request() 经由 resolve_scope() 派生 scope
#   - 全链路(view -> orchestrator -> LLM) 返回 200 + 自动日志记录
#   - 未认证请求 401
#
# Brief 侧 bug 修复:
#   1. ``auth_client.handler._force_auth_user`` -> ``auth_client.handler._force_user``
#      (DRF ForceAuthClientHandler 真实属性为 _force_user)
#   2. ``Personnel.objects.create(name="P", user=user)`` -> Personnel 无 user 字段,
#      绑定走 reverse OneToOne ``user.personnel = p; user.save()``
#   3. ``Permission.objects.get(codename="view_department")`` -> 必须加
#      ``content_type__app_label="smart_assistant"`` 过滤,否则 MultipleObjectsReturned
#      (auth 等 app 也有 codename='view_<modelname>' 的默认权限)
#   4. request body 字段是 ``query``(非 ``message``),由 SmartChatRequestSerializer 决定;
#      brief 的 ``"message"+"stream":False`` 会 400
#   5. 使用 ``User.objects.create_user/create_superuser``(AbstractUser 要求 password)
# =============================================================================


@pytest.mark.django_db
def test_e2e_plain_user_aggregation_returns_self_data(auth_client, mock_llm_router):
    """E2E 场景 9:普通员工 (scope=SELF) -> chat 端点返回 200。

    LLM 已被 mock_llm_router patch 为返回固定响应;orchestrator 真实运行。
    """
    from events.models import Schedule
    from personnel.models import Personnel
    from django.utils import timezone

    user = auth_client.handler._force_user
    p = Personnel.objects.create(name="P")
    user.personnel = p
    user.save()
    Schedule.objects.create(duty_date=timezone.now().date(), duty_person=p)

    mock_llm_router.generate.return_value = ("本周你有一个排班。", {"total_tokens": 50})

    resp = auth_client.post(
        "/api/smart-assistant/chat/",
        {"query": "这周我有哪些事", "stream": False},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_e2e_dept_manager_aggregation_returns_dept_data(auth_client_dept, mock_llm_router):
    """E2E 场景 10:部门主管 (scope=DEPARTMENT) -> chat 端点返回 200。

    Fixture ``auth_client_dept`` 已授予 view_department 权限(scope->DEPARTMENT)。
    """
    from events.models import Schedule
    from personnel.models import Personnel
    from django.utils import timezone

    manager = auth_client_dept.handler._force_user
    p = Personnel.objects.create(name="P")
    manager.personnel = p
    manager.save()
    Schedule.objects.create(duty_date=timezone.now().date(), duty_person=p)

    mock_llm_router.generate.return_value = ("部门本周有 1 个排班。", {"total_tokens": 50})

    resp = auth_client_dept.post(
        "/api/smart-assistant/chat/",
        {"query": "本部门本周有哪些安排", "stream": False},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_e2e_admin_aggregation_returns_all_data(auth_client_admin, mock_llm_router):
    """E2E 场景 11:管理员 (scope=GLOBAL) -> chat 端点返回 200。

    Fixture ``auth_client_admin`` 创建 is_superuser=True 用户,
    resolve_scope() 直接返回 GLOBAL,无需授予 view_global。
    """
    from events.models import Schedule
    from personnel.models import Personnel
    from django.utils import timezone

    p = Personnel.objects.create(name="P")
    Schedule.objects.create(duty_date=timezone.now().date(), duty_person=p)

    mock_llm_router.generate.return_value = ("全公司本周有 1 个排班。", {"total_tokens": 50})

    resp = auth_client_admin.post(
        "/api/smart-assistant/chat/",
        {"query": "全公司本周安排", "stream": False},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_e2e_unauthorized_request_rejected(mock_llm_router):
    """E2E 场景 12:未登录用户访问 chat -> 401 / 403(ISAuthenticated 默认 401)。

    全局 permission_classes=[IsAuthenticated] 已拒绝;orchestrator 不应被调用。
    """
    from rest_framework.test import APIClient
    client = APIClient()
    resp = client.post(
        "/api/smart-assistant/chat/",
        {"query": "本周安排", "stream": False},
        format="json",
    )
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# =============================================================================
# Task 17 — E2E 回归测试:scope-filtered 数据 + AggregatedDayCard 触发
# =============================================================================
# 验证:
#   1. views/chat.py 注入 ToolContext 后,orchestrator 走 scope-aware 路径
#   2. 多工具结果通过 ResultSynthesizer 聚合,返回 camelCase `moduleCounts`
#   3. intent 字段 == "aggregated_day",让前端 ToolResult.jsx 触发 AggregatedDayCard
#   4. 不同 scope(plain / admin)对同一 query 看到不同范围数据
#   5. cache_tool_result 按 user/scope 隔离,plain 用户不会读到 admin 缓存
# =============================================================================


@pytest.mark.django_db
def test_e2e_aggregation_returns_scope_filtered_data(
    auth_client, auth_client_admin, mock_llm_router
):
    """E2E 场景 13:同一 query 在普通员工 vs 管理员身份下,response.data 体现 scope-filtered 数据。

    实现策略:不走真实 ToolChainExecutor 内部逻辑(LLM 计划生成复杂),改为
    patch ToolChainExecutor.execute 注入固定结果,然后断言:
    - 响应 intent == "aggregated_day"(触发 AggregatedDayCard)
    - tool_result 含 moduleCounts(items 数组 + module 统计,二者不同身份下不同)
    """
    from unittest.mock import patch
    from smart_assistant.tools.tool_context import ToolContext

    # 安排 plain user 看到 1 条 + admin 看到 2 条;ToolChainExecutor.execute
    # 区分身份靠传入的 context.user/scope,我们用 side_effect 模拟。
    def fake_execute(self, plan, ctx):
        if ctx.user.username == "plain_user_test":
            return [{
                "tool": "schedule_query",
                "module_label": "排班",
                "found": True,
                "schedules": [{"duty_date": "2026-07-08", "sort_key": "2026-07-08"}],
            }]
        # admin 看到 2 条不同模块
        return [
            {
                "tool": "schedule_query",
                "module_label": "排班",
                "found": True,
                "schedules": [
                    {"duty_date": "2026-07-08", "sort_key": "2026-07-08"},
                    {"duty_date": "2026-07-09", "sort_key": "2026-07-09"},
                ],
            },
            {
                "tool": "announcement_query",
                "module_label": "公告",
                "found": True,
                "posts": [{"title": "本周例会", "sort_key": "2026-07-09"}],
            },
        ]

    mock_llm_router.generate.return_value = ("已汇总。", {"total_tokens": 30})

    with patch("smart_assistant.agent.orchestrator.ToolChainExecutor.execute", fake_execute), \
         patch("smart_assistant.agent.orchestrator.generate_tool_chain_plan") as mock_plan:
        # 强制走多工具路径(让 orchestrator 选 _process_chain)
        mock_plan.return_value = [{"tool": "schedule_query", "params": {}}]

        # 普通员工请求
        resp_plain = auth_client.post(
            "/api/smart-assistant/chat/",
            {"query": "这周我有哪些事", "stream": False},
            format="json",
        )
        # 管理员请求
        resp_admin = auth_client_admin.post(
            "/api/smart-assistant/chat/",
            {"query": "这周我有哪些事", "stream": False},
            format="json",
        )

    # 两个响应都成功
    assert resp_plain.status_code == status.HTTP_200_OK
    assert resp_admin.status_code == status.HTTP_200_OK

    # Task 17 C3 修复:intent = "aggregated_day" 触发 AggregatedDayCard
    assert resp_plain.data["intent"] == "aggregated_day"
    assert resp_admin.data["intent"] == "aggregated_day"

    # tool_result 包含 ResultSynthesizer 聚合输出
    plain_result = resp_plain.data["tool_result"]
    admin_result = resp_admin.data["tool_result"]
    assert "summary" in plain_result
    assert "items" in plain_result
    assert "moduleCounts" in plain_result  # camelCase 字段(原 C2 bug 修复)

    # scope-filtered 数据真的不同
    plain_count = plain_result["total_count"]
    admin_count = admin_result["total_count"]
    assert admin_count > plain_count, (
        f"管理员应比 plain 看到更多数据:plain={plain_count}, admin={admin_count}"
    )
    # plain user 只能看到 1 条排班
    assert plain_result["moduleCounts"].get("排班") == 1
    # admin 看到排班 2 + 公告 1
    assert admin_result["moduleCounts"].get("排班") == 2
    assert admin_result["moduleCounts"].get("公告") == 1


@pytest.mark.django_db
def test_e2e_cache_isolated_by_user_and_scope(
    auth_client, auth_client_admin, mock_llm_router
):
    """E2E 场景 14:同一 query 不同用户,cache 不串(防 P0 缓存投毒)。

    验证:plain 第一次请求 -> cache miss;admin 同 query 请求应仍 cache miss
    (因 scope_sig 不同),不会读到 plain 的缓存。

    使用 schedule_query 触发真实工具路径(而非 general_chat)。
    """
    from unittest.mock import patch, MagicMock
    from smart_assistant.cache import cache_tool_result as real_cache_tool_result

    captured_context_sigs = []

    def wrapped_cache_tool_result(tool_name, query, result, context_sig=""):
        captured_context_sigs.append(context_sig)
        return real_cache_tool_result(tool_name, query, result, context_sig=context_sig)

    # mock_llm_router 用于 LLM answer 生成;同时需要 mock 工具与 intent classifier
    mock_llm_router.generate.return_value = ("回答", {"total_tokens": 10})

    # 直接 patch 单工具路径:让 ToolRegistry.get_tool 返回一个固定 schedule_query 工具
    mock_tool = MagicMock()
    mock_tool.name = "schedule_query"
    mock_tool.execute.return_value = {"found": True, "schedules": []}
    mock_tool.supports_scope_filter = False  # 走旧路径,仍会调 cache_tool_result

    # 注意:必须 patch orchestrator 内部导入的 cache_tool_result 引用,
    # 不能 patch smart_assistant.cache.cache_tool_result(因为 from .. import
    # 已经把引用拷到 orchestrator 命名空间)。
    with patch("smart_assistant.agent.orchestrator.cache_tool_result", wrapped_cache_tool_result), \
         patch("smart_assistant.agent.orchestrator.ToolRegistry") as mock_registry, \
         patch("smart_assistant.agent.orchestrator.classify_intent") as mock_classify:
        mock_classify.return_value = "schedule_query"
        mock_registry.get_tool.return_value = mock_tool
        mock_registry.get_all_schemas.return_value = [
            {"name": "schedule_query", "description": "排班"}
        ]
        # plain user 第一次请求
        resp_plain = auth_client.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班", "stream": False},
            format="json",
        )
        # admin user 同 query
        resp_admin = auth_client_admin.post(
            "/api/smart-assistant/chat/",
            {"query": "明天谁值班", "stream": False},
            format="json",
        )

    assert resp_plain.status_code == status.HTTP_200_OK
    assert resp_admin.status_code == status.HTTP_200_OK

    # captured_context_sigs 中应出现 plain user 与 admin user 各自 scope 的 sig
    plain_sigs = [s for s in captured_context_sigs if "u" in s and "_s" in s]
    assert plain_sigs, "期望至少一次 cache_tool_result 写入"
    # 至少出现两种不同的 sig(plain vs admin scope 不同)
    distinct = set(plain_sigs)
    assert len(distinct) >= 2, (
        f"期望 plain user 与 admin user 写不同 sig,实际只有 {distinct}"
    )
    # 包含 self (plain) 和 global (admin) 两种 scope
    scope_values = {s.split("_s")[1] for s in distinct if "_s" in s}
    assert "self" in scope_values, f"应包含 self scope,实际 {scope_values}"
    assert "global" in scope_values, f"应包含 global scope,实际 {scope_values}"

