from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_integration', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IntegrationService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='服务名称')),
                ('slug', models.SlugField(unique=True, verbose_name='标识符')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('integration_type', models.CharField(choices=[('iframe', 'iframe 嵌入'), ('api', 'API 代理调用'), ('widget', '组件嵌入')], max_length=20, verbose_name='集成类型')),
                ('endpoint_url', models.URLField(max_length=500, verbose_name='服务端点')),
                ('api_key', models.CharField(blank=True, default='', max_length=255, verbose_name='API 密钥')),
                ('embed_path', models.CharField(blank=True, default='', max_length=500, verbose_name='嵌入路径/模板')),
                ('config_schema', models.JSONField(default=dict, verbose_name='配置 Schema')),
                ('metadata', models.JSONField(default=dict, verbose_name='元数据')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '集成服务',
                'verbose_name_plural': '集成服务管理',
                'db_table': 'integration_service',
                'ordering': ['name'],
            },
        ),
    ]
