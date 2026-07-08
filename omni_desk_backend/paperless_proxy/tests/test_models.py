import pytest
from django.contrib.auth import get_user_model
from ..models import DocumentBinding, OutboxItem

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='alice', password='pwd')


@pytest.fixture
def binding(db, user):
    return DocumentBinding.objects.create(
        source_type='project_document',
        source_id=1,
        paperless_id=999,
        paperless_checksum='h',
        owner=user,
        title='X',
    )


@pytest.mark.django_db
class TestDocumentBinding:
    def test_create_binding(self, user):
        """验证:能创建一个 DocumentBinding"""
        binding = DocumentBinding.objects.create(
            source_type='project_document',
            source_id=42,
            paperless_id=100,
            paperless_checksum='abc123',
            owner=user,
            title='测试文档.pdf',
        )
        assert binding.id is not None
        assert binding.source_type == 'project_document'
        assert binding.paperless_id == 100

    def test_unique_source(self, user):
        """验证:同一 source_type + source_id 不能重复"""
        DocumentBinding.objects.create(
            source_type='project_document',
            source_id=42,
            paperless_id=100,
            paperless_checksum='abc',
            owner=user,
            title='A',
        )
        with pytest.raises(Exception):  # IntegrityError
            DocumentBinding.objects.create(
                source_type='project_document',
                source_id=42,
                paperless_id=101,
                paperless_checksum='def',
                owner=user,
                title='B',
            )

    def test_unique_paperless_id(self, user):
        """验证:paperless_id 全局唯一"""
        DocumentBinding.objects.create(
            source_type='contract',
            source_id=1,
            paperless_id=200,
            paperless_checksum='x',
            owner=user,
            title='A',
        )
        with pytest.raises(Exception):
            DocumentBinding.objects.create(
                source_type='policy',
                source_id=2,
                paperless_id=200,
                paperless_checksum='y',
                owner=user,
                title='B',
            )


@pytest.mark.django_db
class TestOutboxItem:
    def test_create_outbox(self, user, binding):
        """验证:能创建 OutboxItem"""
        item = OutboxItem.objects.create(
            operation='upload',
            status='pending',
            payload={'title': 't.pdf', 'correspondent_id': None},
            binding=binding,
            created_by=user,
        )
        assert item.id is not None
        assert item.status == 'pending'
        assert item.retry_count == 0

    def test_default_next_retry_at(self, user, binding):
        """验证:默认 next_retry_at = now"""
        from django.utils import timezone
        from datetime import timedelta
        item = OutboxItem.objects.create(
            operation='upload',
            payload={},
            binding=binding,
            created_by=user,
        )
        delta = timezone.now() - item.next_retry_at
        assert abs(delta) < timedelta(seconds=5)
