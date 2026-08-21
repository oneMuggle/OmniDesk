"""LLMRouter 配置缓存失效信号(R5-B4)。

LlmAppConfig 变更 → 失效对应 app 的缓存;
LlmEndpoint 变更 → 影响所有引用它的 app 配置,全量失效。

注:llm_service 不在 INSTALLED_APPS(纯 Python 模块,无 models),
信号注册由 smart_assistant.apps.SmartAssistantConfig.ready() 导入触发
(模型 LlmAppConfig/LlmEndpoint 定义在 smart_assistant)。
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from llm_service.router import _router_cache_key

from smart_assistant.models import LlmAppConfig, LlmEndpoint

_APP_NAMES = [choice[0] for choice in LlmAppConfig.APP_CHOICES]


def _invalidate(app_name=None):
    if app_name:
        cache.delete(_router_cache_key(app_name))
    else:
        cache.delete_many([_router_cache_key(name) for name in _APP_NAMES])


@receiver(post_save, sender=LlmAppConfig)
@receiver(post_delete, sender=LlmAppConfig)
def invalidate_on_app_config_change(sender, instance, **kwargs):
    # 保存前后的 is_active/app_name 都可能影响路由,保守起见全量失效
    _invalidate()


@receiver(post_save, sender=LlmEndpoint)
@receiver(post_delete, sender=LlmEndpoint)
def invalidate_on_endpoint_change(sender, instance, **kwargs):
    _invalidate()
