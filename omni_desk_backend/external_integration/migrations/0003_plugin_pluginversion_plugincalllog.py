from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('external_integration', '0002_integration_service'),
    ]

    operations = [
        migrations.CreateModel(
            name='Plugin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True, verbose_name='插件名称')),
                ('slug', models.SlugField(unique=True, verbose_name='标识符')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('category', models.CharField(db_index=True, max_length=100, verbose_name='分类')),
                ('icon', models.CharField(blank=True, max_length=50, null=True, verbose_name='图标')),
                ('status', models.CharField(choices=[('draft', '草稿'), ('pending_review', '待审核'), ('approved', '已批准'), ('rejected', '已拒绝'), ('disabled', '已禁用')], default='draft', max_length=20, verbose_name='状态')),
                ('interface_version', models.CharField(default='v1', max_length=20, verbose_name='接口版本')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plugins', to=settings.AUTH_USER_MODEL, verbose_name='作者')),
            ],
            options={
                'verbose_name': '插件',
                'verbose_name_plural': '插件管理',
                'db_table': 'plugin',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='PluginVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=20, verbose_name='版本号')),
                ('upload_file', models.FileField(upload_to='plugins/', verbose_name='插件文件')),
                ('file_hash', models.CharField(max_length=64, verbose_name='文件哈希')),
                ('manifest', models.JSONField(default=dict, verbose_name='插件清单')),
                ('is_active', models.BooleanField(default=False, verbose_name='是否激活')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('review_notes', models.TextField(blank=True, null=True, verbose_name='审核备注')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
                ('plugin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='external_integration.plugin', verbose_name='所属插件')),
            ],
            options={
                'verbose_name': '插件版本',
                'verbose_name_plural': '插件版本管理',
                'db_table': 'plugin_version',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='PluginCallLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(max_length=20, verbose_name='调用方法')),
                ('args_summary', models.CharField(blank=True, default='', max_length=500, verbose_name='参数摘要')),
                ('status', models.CharField(max_length=20, verbose_name='执行状态')),
                ('execution_time_ms', models.IntegerField(null=True, verbose_name='执行耗时(ms)')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='错误信息')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('plugin_version', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='external_integration.pluginversion', verbose_name='插件版本')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='调用用户')),
            ],
            options={
                'verbose_name': '插件调用日志',
                'verbose_name_plural': '插件调用日志',
                'db_table': 'plugin_call_log',
                'ordering': ['-created_at'],
            },
        ),
    ]
