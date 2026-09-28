"""自动入库配置：``SMART_ASSISTANT_INGEST_DATASET_ID`` + 启用的 ``RagflowConfig``，缺一即整体关闭。"""

from __future__ import annotations

from django.conf import settings


def ingest_dataset_id() -> str:
    return (getattr(settings, "SMART_ASSISTANT_INGEST_DATASET_ID", "") or "").strip()


def active_ragflow_config():
    from ragflow_service.models import RagflowConfig

    return RagflowConfig.objects.filter(is_active=True).first()


def ingest_settings():
    """返回 ``(RagflowConfig, dataset_id)``；未配置返回 ``None``。"""
    dataset_id = ingest_dataset_id()
    if not dataset_id:
        return None
    config = active_ragflow_config()
    if config is None or not config.api_endpoint or not config.api_key:
        return None
    return config, dataset_id


def is_enabled() -> bool:
    return ingest_settings() is not None


def make_client(config):
    from ragflow_service.client import RagflowClient

    return RagflowClient(api_endpoint=config.api_endpoint, api_key=config.api_key)
