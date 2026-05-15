from django.db import migrations, models
import django.db.models.deletion


def migrate_llm_config_to_endpoint_and_app(apps, schema_editor):
    """将 LlmConfig 数据拆分迁移到 LlmEndpoint 和 LlmAppConfig"""
    LlmConfig = apps.get_model('smart_assistant', 'LlmConfig')
    LlmEndpoint = apps.get_model('smart_assistant', 'LlmEndpoint')
    LlmAppConfig = apps.get_model('smart_assistant', 'LlmAppConfig')

    # 按 endpoint+key 分组，合并为 LlmEndpoint
    endpoint_cache = {}
    for config in LlmConfig.objects.all():
        key = (config.api_endpoint, config.api_key)
        if key not in endpoint_cache:
            endpoint = LlmEndpoint.objects.create(
                name=config.name,
                api_endpoint=config.api_endpoint,
                api_key=config.api_key,
                is_active=True,
            )
            endpoint_cache[key] = endpoint
        else:
            endpoint = endpoint_cache[key]

        # 创建对应的 LlmAppConfig
        LlmAppConfig.objects.create(
            app_name='smart_assistant',
            endpoint=endpoint,
            model_name=config.model_name,
            temperature=config.temperature,
            top_p=config.top_p,
            is_active=config.is_active,
        )


def reverse_migration(apps, schema_editor):
    """回滚：将 LlmAppConfig + LlmEndpoint 合并回 LlmConfig"""
    LlmConfig = apps.get_model('smart_assistant', 'LlmConfig')
    LlmAppConfig = apps.get_model('smart_assistant', 'LlmAppConfig')

    for app_config in LlmAppConfig.objects.select_related('endpoint').all():
        ep = app_config.endpoint
        LlmConfig.objects.create(
            name=f"{ep.name} - {app_config.model_name}",
            api_endpoint=ep.api_endpoint,
            api_key=ep.api_key,
            model_name=app_config.model_name,
            is_active=app_config.is_active,
            temperature=app_config.temperature,
            top_p=app_config.top_p,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('smart_assistant', '0003_llmconfig'),
    ]

    operations = [
        migrations.CreateModel(
            name='LlmEndpoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='配置名称')),
                ('api_endpoint', models.URLField(verbose_name='API 端点')),
                ('api_key', models.CharField(max_length=500, verbose_name='API 密钥')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'LLM API 端点',
                'verbose_name_plural': 'LLM API 端点',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LlmAppConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('app_name', models.CharField(choices=[('smart_assistant', '智能助手')], max_length=50, verbose_name='应用名称')),
                ('model_name', models.CharField(max_length=100, verbose_name='模型名称')),
                ('temperature', models.FloatField(blank=True, default=0.7, null=True)),
                ('top_p', models.FloatField(blank=True, default=0.9, null=True)),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='app_configs', to='smart_assistant.llmendpoint', verbose_name='API 端点')),
            ],
            options={
                'verbose_name': 'LLM 应用配置',
                'verbose_name_plural': 'LLM 应用配置',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RunPython(migrate_llm_config_to_endpoint_and_app, reverse_migration),
        migrations.DeleteModel(
            name='LlmConfig',
        ),
    ]
