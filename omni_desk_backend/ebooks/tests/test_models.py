import pytest

from ebooks.models import Ebook


@pytest.mark.django_db
class TestEbookModel:
    def test_ebook_creation(self):
        ebook = Ebook.objects.create(
            title='Test Book',
            author='Test Author',
        )
        assert ebook.pk is not None
        assert str(ebook) == 'Test Book'

    def test_ebook_optional_fields(self):
        ebook = Ebook.objects.create(title='Minimal Book')
        assert ebook.author == ''
        assert ebook.file is None
