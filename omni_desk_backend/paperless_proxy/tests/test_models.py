import pytest
from django.contrib.auth import get_user_model
from ..models import DocumentBinding, OutboxItem, PaperlessHealth, UserPaperlessBinding

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


@pytest.mark.django_db
class TestUserPaperlessBinding:
    def test_create_binding(self, user):
        """验证:能创建 UserPaperlessBinding"""
        b = UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        assert b.id is not None
        assert b.is_active is True

    def test_one_to_one(self, user):
        """验证:一个 OmniDesk 用户只能绑定一个 paperless 用户"""
        UserPaperlessBinding.objects.create(
            user=user, paperless_user_id=5, paperless_username='alice'
        )
        from django.contrib.auth import get_user_model
        CustomUser = get_user_model()
        u2 = CustomUser.objects.create_user(username='bob', password='p')
        with pytest.raises(Exception):
            UserPaperlessBinding.objects.create(
                user=u2, paperless_user_id=5, paperless_username='duplicate'
            )


@pytest.mark.django_db
class TestPaperlessHealth:
    def test_singleton(self):
        """验证:健康状态单例(只能有一行)"""
        h = PaperlessHealth.objects.create(is_healthy=True)
        assert h.id is not None
        # 第二次创建会创建新行(不是物理单例),但通过 get_singleton 始终返回第一行
        singleton = PaperlessHealth.get_singleton()
        assert singleton.id == h.id

    def test_get_singleton_creates_default(self):
        """验证:get_singleton 找不到时自动创建默认值"""
        assert PaperlessHealth.objects.count() == 0
        s = PaperlessHealth.get_singleton()
        assert s.is_healthy is True
        assert s.consecutive_failures == 0


@pytest.mark.django_db
def test_paperless_id_nullable():
    """DocumentBinding.paperless_id 必须允许 NULL,避免二次上传 unique 冲突"""
    CustomUser2 = get_user_model()
    user = CustomUser2.objects.create_user(username='u_null', password='p')
    binding = DocumentBinding.objects.create(
        source_type='contract', source_id=1,
        paperless_id=None, paperless_checksum='',
        owner=user, title='No paperless yet',
    )
    binding.refresh_from_db()
    assert binding.paperless_id is None
