import pytest
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from ..models import OutboxItem, DocumentBinding
from ..services.outbox import OutboxService, OutboxDeadError

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='u', password='p')


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
class TestOutboxEnqueue:
    def test_enqueue_creates_pending(self, user, binding):
        """验证:enqueue 创建 pending 状态 outbox"""
        outbox = OutboxService.enqueue(
            operation='upload',
            payload={'file': 'x', 'title': 't'},
            binding=binding,
            created_by=user,
        )
        assert outbox.status == 'pending'
        assert outbox.retry_count == 0


@pytest.mark.django_db
class TestOutboxFetchPending:
    def test_fetch_returns_due_pending(self, user, binding):
        """验证:只返回 status=pending 且 next_retry_at <= now"""
        OutboxItem.objects.create(
            operation='upload', status='pending', payload={},
            next_retry_at=timezone.now() - timedelta(minutes=1),
            created_by=user, binding=binding,
        )
        OutboxItem.objects.create(
            operation='upload', status='pending', payload={},
            next_retry_at=timezone.now() + timedelta(minutes=5),
            created_by=user, binding=binding,
        )
        pending = OutboxService.fetch_pending(batch_size=10)
        assert len(pending) == 1


@pytest.mark.django_db
class TestOutboxRetry:
    @freeze_time("2026-01-01 10:00:00")
    def test_mark_failed_increments_and_backoff(self, user, binding):
        """验证:失败时 retry_count++ 且 next_retry_at 退避"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        OutboxService.mark_failed(outbox, 'connection timeout')
        outbox.refresh_from_db()
        assert outbox.retry_count == 1
        assert outbox.status == 'pending'
        # 30s * 2^1 = 60s
        expected = timezone.now() + timedelta(seconds=60)
        assert abs((outbox.next_retry_at - expected).total_seconds()) < 5

    @freeze_time("2026-01-01 10:00:00")
    def test_mark_failed_at_max_retries_raises_dead(self, user, binding):
        """验证:达到 max_retries 时抛 OutboxDeadError,status=dead"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        outbox.retry_count = outbox.max_retries  # 已是最后一次
        for _ in range(outbox.max_retries):
            try:
                OutboxService.mark_failed(outbox, 'persistent error')
            except OutboxDeadError:
                break
        outbox.refresh_from_db()
        assert outbox.status == 'dead'
        assert 'persistent error' in outbox.last_error


@pytest.mark.django_db
class TestOutboxMarkSynced:
    def test_mark_synced_clears_retry(self, user, binding):
        """验证:成功后 retry_count 重置"""
        outbox = OutboxService.enqueue(
            operation='upload', payload={}, binding=binding, created_by=user,
        )
        outbox.retry_count = 3
        outbox.save()
        OutboxService.mark_synced(outbox)
        outbox.refresh_from_db()
        assert outbox.status == 'synced'
        assert outbox.retry_count == 0
