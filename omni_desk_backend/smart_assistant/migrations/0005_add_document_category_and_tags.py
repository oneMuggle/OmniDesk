from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smart_assistant', '0004_llmendpoint_llmappconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='knowledgebasedocument',
            name='category',
            field=models.CharField(
                choices=[
                    ('general', '通用'),
                    ('technical', '技术'),
                    ('policy', '政策'),
                    ('procedure', '流程'),
                    ('faq', '常见问题'),
                ],
                default='general',
                max_length=20,
                verbose_name='文档分类',
            ),
        ),
        migrations.AddField(
            model_name='knowledgebasedocument',
            name='tags',
            field=models.CharField(
                blank=True,
                max_length=500,
                verbose_name='标签（逗号分隔）',
            ),
        ),
    ]
