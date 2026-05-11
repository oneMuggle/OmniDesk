import pytest
from django.contrib.auth import get_user_model
from ..models import ExternalLink

CustomUser = get_user_model()


@pytest.fixture
def user(db):
    return CustomUser.objects.create_user(username='testuser', password='testpass')


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_superuser(username='admin', password='adminpass')


@pytest.fixture
def link(db):
    return ExternalLink.objects.create(
        name='Test GitLab',
        url='http://gitlab.internal',
        category='开发工具',
        description='内网 GitLab',
        sort_order=1,
    )


@pytest.mark.django_db
class TestExternalLinkModel:
    def test_create_link(self):
        link = ExternalLink.objects.create(
            name='Test Link',
            url='http://example.com',
            category='测试',
        )
        assert link.id is not None
        assert link.is_active is True
        assert link.sso_enabled is False

    def test_string_representation(self, link):
        assert str(link) == '开发工具 - Test GitLab'

    def test_ordering(self, db):
        ExternalLink.objects.create(name='B', url='http://b.com', category='A', sort_order=2)
        ExternalLink.objects.create(name='A', url='http://a.com', category='A', sort_order=1)
        links = list(ExternalLink.objects.all())
        assert links[0].name == 'A'
        assert links[1].name == 'B'
