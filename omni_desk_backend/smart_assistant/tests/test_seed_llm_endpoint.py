"""seed_llm_endpoint 管理命令测试。

覆盖:
- 首次执行创建 LlmEndpoint + LlmAppConfig
- 幂等性(连续执行两次只创建一条记录)
- 默认环境变量值(Ollama localhost:11434/v1 + qwen2.5:7b)
- 自定义环境变量(SEED_LLM_API_ENDPOINT / SEED_LLM_MODEL / SEED_LLM_API_KEY)
- --dry-run 不写库
- 表非空时跳过且不覆盖已有配置
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from smart_assistant.models import LlmAppConfig, LlmEndpoint


@pytest.mark.django_db
class TestSeedLlmEndpoint:
    def test_seed_creates_endpoint_and_app_config(self):
        """首次执行:创建激活的 fallback 端点并关联 smart_assistant 应用配置"""
        out = StringIO()
        call_command("seed_llm_endpoint", stdout=out)

        assert LlmEndpoint.objects.count() == 1
        assert LlmAppConfig.objects.count() == 1

        endpoint = LlmEndpoint.objects.first()
        assert endpoint.is_active is True
        assert endpoint.is_fallback is True

        app_config = LlmAppConfig.objects.first()
        assert app_config.app_name == "smart_assistant"
        assert app_config.endpoint == endpoint
        assert app_config.is_active is True

    def test_seed_is_idempotent(self):
        """幂等:执行两次只创建一条记录,第二次输出跳过提示"""
        call_command("seed_llm_endpoint", stdout=StringIO())
        out = StringIO()
        call_command("seed_llm_endpoint", stdout=out)

        assert LlmEndpoint.objects.count() == 1
        assert LlmAppConfig.objects.count() == 1
        assert "跳过" in out.getvalue()

    def test_seed_uses_default_env_values(self):
        """未设置环境变量时使用 Ollama 默认端点与模型"""
        call_command("seed_llm_endpoint", stdout=StringIO())

        endpoint = LlmEndpoint.objects.first()
        assert endpoint.api_endpoint == "http://localhost:11434/v1"
        # EncryptedCharField 对空串透明处理,读回应仍为空串
        assert endpoint.api_key == ""
        assert LlmAppConfig.objects.first().model_name == "qwen2.5:7b"

    def test_seed_reads_custom_env_values(self, monkeypatch):
        """自定义环境变量:端点 / 模型 / API Key 均按环境值落库"""
        monkeypatch.setenv("SEED_LLM_API_ENDPOINT", "http://llm.internal:8080/v1")
        monkeypatch.setenv("SEED_LLM_MODEL", "deepseek-r1:7b")
        monkeypatch.setenv("SEED_LLM_API_KEY", "sk-test-123")

        call_command("seed_llm_endpoint", stdout=StringIO())

        endpoint = LlmEndpoint.objects.first()
        assert endpoint.api_endpoint == "http://llm.internal:8080/v1"
        # EncryptedCharField 透明加解密:读回应为明文
        assert endpoint.api_key == "sk-test-123"
        assert LlmAppConfig.objects.first().model_name == "deepseek-r1:7b"

    def test_seed_dry_run_does_not_write(self):
        """--dry-run:打印计划但不写库"""
        out = StringIO()
        call_command("seed_llm_endpoint", "--dry-run", stdout=out)

        assert LlmEndpoint.objects.count() == 0
        assert LlmAppConfig.objects.count() == 0
        assert "dry-run" in out.getvalue()

    def test_seed_rolls_back_endpoint_when_app_config_fails(self, monkeypatch):
        """LlmAppConfig 创建失败 → 整体事务回滚,不遗留孤儿 LlmEndpoint。

        否则幂等检查(表非空即跳过)会使后续重试永远无法补建应用配置。
        """

        def _raise(*args, **kwargs):
            raise IntegrityError("模拟 LlmAppConfig 创建失败")

        monkeypatch.setattr(
            "smart_assistant.management.commands.seed_llm_endpoint.LlmAppConfig.objects.create",
            _raise,
        )

        with pytest.raises(IntegrityError):
            call_command("seed_llm_endpoint", stdout=StringIO())

        # 事务回滚:端点未被遗留
        assert LlmEndpoint.objects.count() == 0
        assert LlmAppConfig.objects.count() == 0

    def test_seed_skips_when_endpoint_exists(self):
        """已有记录(如管理员手动配置)时跳过,不覆盖、不新增"""
        LlmEndpoint.objects.create(
            name="manual",
            api_endpoint="http://existing:11434/v1",
            api_key="",
            is_active=True,
        )

        out = StringIO()
        call_command("seed_llm_endpoint", stdout=out)

        assert LlmEndpoint.objects.count() == 1
        assert LlmAppConfig.objects.count() == 0
        assert LlmEndpoint.objects.first().name == "manual"
        assert "跳过" in out.getvalue()
