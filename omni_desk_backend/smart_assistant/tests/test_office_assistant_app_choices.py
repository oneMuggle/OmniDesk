"""LlmAppConfig.APP_CHOICES 注册 office_assistant(配置面)。"""
from smart_assistant.models import LlmAppConfig


def test_app_choices_includes_office_assistant():
    choices = dict(LlmAppConfig.APP_CHOICES)
    assert "office_assistant" in choices
    assert choices["office_assistant"]  # 非空 label


def test_app_choices_preserves_smart_assistant():
    """不破坏既有 smart_assistant 注册。"""
    choices = dict(LlmAppConfig.APP_CHOICES)
    assert "smart_assistant" in choices
