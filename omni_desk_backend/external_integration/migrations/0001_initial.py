# Generated migration for external_integration app

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list[tuple[str, str]] = [
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='名称')),
                ('url', models.URLField(max_length=500, verbose_name='链接地址')),
                ('icon', models.CharField(blank=True, max_length=50, null=True, verbose_name='图标类名')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('category', models.CharField(db_index=True, max_length=100, verbose_name='分类')),
                ('sso_enabled', models.BooleanField(default=False, verbose_name='是否启用 SSO')),
                ('sso_token_endpoint', models.URLField(blank=True, max_length=500, null=True, verbose_name='SSO Token 端点')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否激活')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': '外链',
                'verbose_name_plural': '外链管理',
                'db_table': 'external_link',
                'ordering': ['category', 'sort_order', 'name'],
            },
        ),
    ]
