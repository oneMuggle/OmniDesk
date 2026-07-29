"""为智能助手播种默认 LLM 端点。

背景:离线部署的数据库 LlmEndpoint 表默认为空,智能助手对话会因
"所有 LLM 端点均不可用"而整体失败。本命令在部署流程(deploy_offline.sh
的 migrate 步骤之后)自动创建一条默认可用的端点配置。

用法::

    python manage.py seed_llm_endpoint [--dry-run]

环境变量(可选,均有默认值,在 handle 内读取以便容器 env / 测试覆盖生效):
    SEED_LLM_API_ENDPOINT  默认 http://localhost:11434/v1(Ollama OpenAI 兼容端点)
    SEED_LLM_MODEL         默认 qwen2.5:7b
    SEED_LLM_API_KEY       默认空字符串(Ollama 本地服务不需要密钥)

幂等性:若 LlmEndpoint 表已有任何记录(管理员已手动配置),命令跳过创建
并打印提示,因此重复执行安全。
"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand
from django.db import transaction

from smart_assistant.models import LlmAppConfig, LlmEndpoint

# 默认值:Ollama 本地服务的 OpenAI 兼容端点(离线内网常见配置)
DEFAULT_API_ENDPOINT = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b"

ENDPOINT_NAME = "default-llm-endpoint"
APP_NAME = "smart_assistant"


class Command(BaseCommand):
    help = "为智能助手播种默认 LLM 端点(幂等:LlmEndpoint 表非空时跳过)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅打印将要创建的配置,不写入数据库",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        api_endpoint = os.environ.get("SEED_LLM_API_ENDPOINT", DEFAULT_API_ENDPOINT)
        model_name = os.environ.get("SEED_LLM_MODEL", DEFAULT_MODEL)
        api_key = os.environ.get("SEED_LLM_API_KEY", "")

        existing = LlmEndpoint.objects.count()
        if existing > 0:
            self.stdout.write(
                self.style.WARNING(f"LlmEndpoint 表已有 {existing} 条记录,跳过播种(如需修改请在管理后台或手动调整)。")
            )
            return

        if dry_run:
            self.stdout.write("[dry-run] LlmEndpoint 表为空,将创建以下配置(未写入数据库):")
            self.stdout.write(
                f"  - LlmEndpoint: name={ENDPOINT_NAME}, api_endpoint={api_endpoint}, is_active=True, is_fallback=True"
            )
            self.stdout.write(f"  - LlmAppConfig: app_name={APP_NAME}, model_name={model_name}, is_active=True")
            return

        # 两步写入必须同事务:LlmAppConfig 创建失败时若留下孤儿 LlmEndpoint,
        # 幂等检查(表非空即跳过)会导致后续重试永远无法补建应用配置,
        # 智能助手持续不可用。atomic 保证失败整体回滚,下次执行可重新播种。
        with transaction.atomic():
            endpoint = LlmEndpoint.objects.create(
                name=ENDPOINT_NAME,
                api_endpoint=api_endpoint,
                api_key=api_key,
                is_active=True,
                is_fallback=True,
                priority=1,
            )
            app_config = LlmAppConfig.objects.create(
                app_name=APP_NAME,
                endpoint=endpoint,
                model_name=model_name,
                is_active=True,
            )
        self.stdout.write(
            self.style.SUCCESS(f"✅ 已创建默认 LLM 端点:{endpoint.api_endpoint}(模型:{app_config.model_name})")
        )
        self.stdout.write("  智能助手已关联该端点(is_fallback=True,作为默认/兜底配置)。")
