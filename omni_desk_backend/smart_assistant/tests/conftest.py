"""
smart_assistant 模块专用 pytest fixtures.

设计原则:
- 所有外部依赖(LLM/工具/缓存/Celery)可被替换,测试稳定快速(< 5s 全套)
- 复用全局 conftest.py 提供的 client/user fixture
- 不依赖真实网络/数据库,除非要测的逻辑本身需要 db

使用示例::

    def test_my_thing(mock_llm_router, mock_tool_registry):
        mock_llm_router.generate.return_value = ("answer", {"prompt_tokens": 10})
        ...

Fixtures:
    mock_llm_router          替换 llm_service.router.get_router()
    mock_tool_registry       替换 ToolRegistry 类方法
    mock_cache_backend       替换 Django cache(autouse 已清,本 fixture 验证状态)
    sample_smart_session     工厂函数生成 SmartAssistantSession
    sample_agent_log         工厂函数生成 AgentLog
"""

from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# LLM Router Mock
# =============================================================================


@pytest.fixture
def mock_llm_router():
    """替换 llm_service.router.get_router(),返回可定制的 mock 客户端。

    行为契约:
    - client.generate(prompt=...)  →  (response_text, usage_dict)
    - 默认 response = "Mock LLM response"
    - 默认 usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    示例::

        def test_xxx(mock_llm_router):
            mock_llm_router.generate.return_value = ("custom answer", {"total_tokens": 42})
            ...

    注意:该 fixture 同时 patch 了所有调用 get_router() 的模块:
        - smart_assistant.agent.intent_classifier
        - smart_assistant.agent.orchestrator
        - smart_assistant.agent.tool_chain_planner
        - smart_assistant.agent.tool_chain_executor
    """
    mock_client = MagicMock()
    mock_client.generate.return_value = (
        "Mock LLM response",
        {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )

    with patch("llm_service.router.get_router", return_value=mock_client), \
         patch("smart_assistant.agent.intent_classifier.get_router", return_value=mock_client), \
         patch("smart_assistant.agent.tool_chain_planner.get_router", return_value=mock_client):
        # 注:orchestrator.py 与 tool_chain_executor.py 都在函数内部 import get_router,
        # 或通过其他模块(已被 patch)间接调用,无需单独 patch 模块顶层。
        yield mock_client


# =============================================================================
# Tool Registry Mock
# =============================================================================


@pytest.fixture
def mock_tool_registry():
    """替换 ToolRegistry 类方法,允许测试动态注册/替换工具。

    行为契约:
    - get_tool(intent)          →  MagicMock(可定制 .name / .execute())
    - get_all_schemas()         →  [{"name": ..., "description": ...}, ...]

    示例::

        def test_xxx(mock_tool_registry):
            tool = mock_tool_registry.get_tool.return_value
            tool.name = "schedule_query"
            tool.execute.return_value = {"found": True, "schedules": [...]}
    """
    mock = MagicMock()
    mock.get_all_schemas.return_value = [
        {"name": "schedule_query", "description": "排班值班查询"},
        {"name": "personnel_query", "description": "人员信息查询"},
        {"name": "general_chat", "description": "通用对话"},
    ]
    mock.get_tool.return_value = None

    with patch("smart_assistant.tools.registry.ToolRegistry", mock), \
         patch("smart_assistant.agent.orchestrator.ToolRegistry", mock):
        yield mock


# =============================================================================
# Cache Backend Mock(autouse clear_cache_between_tests 已存在于全局 conftest)
# =============================================================================


@pytest.fixture
def mock_cache_backend():
    """提供一个可验证的 Django cache 句柄,方便测试断言缓存命中/失效。

    复用全局 autouse fixture(clear_cache_between_tests)确保测试间隔离。
    """
    from django.core.cache import cache

    yield cache


# =============================================================================
# Model Factories
# =============================================================================


@pytest.fixture
def sample_smart_session(db, admin_user_obj):
    """创建并返回一个 SmartAssistantSession 实例。

    默认字段:
        - user=admin_user_obj
        - title="测试会话"
        - messages=[]
        - turn_count=0
    """
    from smart_assistant.models import SmartAssistantSession

    def _create(**kwargs):
        defaults = {
            "user": admin_user_obj,
            "title": "测试会话",
            "messages": [],
            "turn_count": 0,
        }
        defaults.update(kwargs)
        return SmartAssistantSession.objects.create(**defaults)

    return _create


@pytest.fixture
def sample_agent_log(db, admin_user_obj, sample_smart_session):
    """创建并返回一个 AgentLog 实例,关联到一个 session(可定制)。

    默认字段:
        - user=admin_user_obj
        - user_query="测试问题"
        - intent="general_chat"
        - response="测试回答"
        - response_time_ms=100
    """
    from smart_assistant.models import AgentLog

    def _create(**kwargs):
        session = kwargs.pop("session", None) or sample_smart_session()
        defaults = {
            "session": session,
            "user": admin_user_obj,
            "user_query": "测试问题",
            "intent": "general_chat",
            "response": "测试回答",
            "response_time_ms": 100,
            "tool_used": "",
        }
        defaults.update(kwargs)
        return AgentLog.objects.create(**defaults)

    return _create


# =============================================================================
# Celery Eager Mode(单测默认开启)
# =============================================================================


@pytest.fixture
def celery_eager_mode(settings):
    """启用 Celery 同步执行模式,避免测试中触发真实异步任务。"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    yield


# =============================================================================
# E2E 用户身份 Fixtures (Task 12)
# =============================================================================
# 三种身份对应 ToolContext.from_request() / resolve_scope() 派生的 scope:
#   - auth_client          -> 普通员工, scope=SELF(默认,无任何权限)
#   - auth_client_dept     -> 部门主管, scope=DEPARTMENT(授予 smart_assistant.view_department)
#   - auth_client_admin    -> 管理员,   scope=GLOBAL(is_superuser=True,自动 GLOBAL)
#
# User 来自全局 conftest.py 的 CustomUser。
# Permission 由 Task 9 migration 0010_smart_assistant_permissions 提供,
#   挂在 ContentType(app_label='smart_assistant', model='smartassistantsession') 下,
#   故 lookup 必须过滤该 app_label,否则 MultipleObjectsReturned
#   (auth 等 app 也有 codename='view_<modelname>' 的 default permission)。
# =============================================================================


@pytest.fixture
def auth_client(db):
    """普通员工(无任何权限) -> APIClient.force_authenticate 注入。

    与现有 ``admin_client`` 同型 APIClient,但用户不带 superuser/staff。
    Test 通过 ``auth_client.handler._force_user`` 反查注入用户。
    """
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="plain_user_test", password="plain123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def auth_client_dept(db):
    """部门主管(拥有 ``smart_assistant.view_department``) -> DEPARTMENT scope。"""
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission

    User = get_user_model()
    user = User.objects.create_user(username="dept_manager_test", password="dept123")
    # 注意:必须按 ContentType app_label 过滤。Permission 表里许多 app 都有
    # codename='view_<modelname>' 的默认权限,无过滤会 MultipleObjectsReturned。
    perm = Permission.objects.get(
        content_type__app_label="smart_assistant",
        codename="view_department",
    )
    user.user_permissions.add(perm)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def auth_client_admin(db):
    """管理员(superuser) -> GLOBAL scope(无需授予 view_global)。

    is_superuser=True 时 ``resolve_scope`` 优先返回 ``GLOBAL``。
    """
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_superuser(
        username="admin_scope_test", password="admin_scope_123", email="a@x.com"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client
