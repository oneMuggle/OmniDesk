"""get_router(app_name="office_assistant") 能加载 APP_CHOICES 配置。

端到端验证 Task 1 的 APP_CHOICES 注册:不仅 DB 写入能成功,
LLMRouter 也能从 DB 加载 office_assistant 的 LlmAppConfig 行,
且 full_clean() 不会拒绝 office_assistant 作为合法 choices。
"""
import pytest

from llm_service.router import LLMRouter
from smart_assistant.models import LlmAppConfig, LlmEndpoint


@pytest.mark.django_db
def test_office_assistant_router_loads_db_config():
    """为 office_assistant 创建 LlmEndpoint + LlmAppConfig 后,LLMRouter 应加载之。"""
    endpoint = LlmEndpoint.objects.create(
        name="office-test-endpoint",
        api_endpoint="https://example.com/v1",
        api_key="test-key",
        priority=1,
        is_fallback=False,
        is_active=True,
    )
    LlmAppConfig.objects.create(
        app_name="office_assistant",
        endpoint=endpoint,
        model_name="gpt-4o-mini",
        is_active=True,
    )

    # 重置单例缓存,使新 DB 行被加载
    from llm_service import router as router_module
    router_module._routers.clear()

    office_router = LLMRouter(app_name="office_assistant")
    assert len(office_router._configs) == 1
    assert office_router._configs[0].model_name == "gpt-4o-mini"


@pytest.mark.django_db
def test_office_assistant_app_name_is_valid_choice():
    """APP_CHOICES 校验不会拒绝 office_assistant。"""
    endpoint = LlmEndpoint.objects.create(
        name="x", api_endpoint="https://x", api_key="k",
        priority=1, is_fallback=False, is_active=True,
    )
    cfg = LlmAppConfig(app_name="office_assistant", endpoint=endpoint, model_name="m")
    cfg.full_clean()  # 触发 choices 校验