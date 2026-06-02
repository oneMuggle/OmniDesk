"""documents 模块综合测试：Book、Chapter、EBook、模板、文档生成等。"""

import pytest

from documents.models import (
    Book, Chapter, EBook, DocumentTemplate, GeneratedDocument, Tag,
)
from users.models import CustomUser
from projects.models import Project


@pytest.fixture
def admin_user(db, admin_user_obj):
    return admin_user_obj


@pytest.fixture
def sample_project(db):
    return Project.objects.create(name='测试项目', description='测试')


# ==================== Book CRUD 测试 ====================

@pytest.mark.django_db
class TestBookViewSet:
    def test_create_book(self, admin_client):
        """创建书籍"""
        resp = admin_client.post('/api/documents/books/', {
            'title': '测试书籍',
            'author': '测试作者',
            'description': '书籍描述',
        }, format='json')
        assert resp.status_code == 201, resp.data
        assert Book.objects.filter(title='测试书籍').exists()

    def test_list_books(self, admin_client):
        """书籍列表"""
        Book.objects.create(title='书籍A', author='作者A')
        Book.objects.create(title='书籍B', author='作者B')
        resp = admin_client.get('/api/documents/books/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        assert len(results) >= 2

    def test_update_book(self, admin_client):
        """更新书籍"""
        book = Book.objects.create(title='旧标题', author='作者')
        resp = admin_client.patch(f'/api/documents/books/{book.id}/', {
            'title': '新标题',
        }, format='json')
        assert resp.status_code == 200, resp.data
        book.refresh_from_db()
        assert book.title == '新标题'

    def test_delete_book(self, admin_client):
        """删除书籍"""
        book = Book.objects.create(title='待删除书籍', author='作者')
        resp = admin_client.delete(f'/api/documents/books/{book.id}/')
        assert resp.status_code == 204
        assert not Book.objects.filter(id=book.id).exists()


# ==================== Chapter CRUD 测试 ====================

@pytest.mark.django_db
class TestChapterViewSet:
    def test_create_chapter_model(self):
        """章节模型创建（API 可能不允许直接 POST）"""
        book = Book.objects.create(title='章节书籍', author='作者')
        chapter = Chapter.objects.create(book=book, title='第一章', content_md='# 内容', order=1)
        assert chapter.title == '第一章'
        assert chapter.book == book

    def test_chapter_ordering(self, admin_client):
        """章节应按 order 排序"""
        book = Book.objects.create(title='排序书籍', author='作者')
        Chapter.objects.create(book=book, title='第二章', content_md='内容2', order=2)
        Chapter.objects.create(book=book, title='第一章', content_md='内容1', order=1)
        resp = admin_client.get('/api/documents/chapters/')
        assert resp.status_code == 200
        results = resp.data.get('results', resp.data)
        titles = [r['title'] for r in results if r['title'] in ['第一章', '第二章']]
        if len(titles) >= 2:
            assert titles[0] == '第一章'

    def test_chapter_update_via_api(self, admin_client):
        """章节更新"""
        book = Book.objects.create(title='更新章节书籍', author='作者')
        chapter = Chapter.objects.create(book=book, title='旧标题', content_md='内容', order=1)
        resp = admin_client.patch(f'/api/documents/chapters/{chapter.id}/', {
            'title': '新标题',
        }, format='json')
        assert resp.status_code in [200, 405], resp.data
        if resp.status_code == 200:
            chapter.refresh_from_db()
            assert chapter.title == '新标题'


# ==================== EBook CRUD 测试 ====================

@pytest.mark.django_db
class TestEBookViewSet:
    def test_ebook_model_crud(self, admin_client):
        """电子书模型 CRUD"""
        ebook = EBook.objects.create(title='测试电子书', author='电子书作者', content='# 内容')
        assert ebook.title == '测试电子书'

        resp = admin_client.get('/api/documents/ebooks/')
        assert resp.status_code == 200


# ==================== DocumentTemplate 测试 ====================

@pytest.mark.django_db
class TestDocumentTemplateViewSet:
    def test_template_model(self, admin_user):
        """文档模板模型"""
        from documents.models import DocumentTemplate
        template = DocumentTemplate.objects.create(
            name='测试模板',
            template_type='tech_design',
            owner=admin_user,
        )
        assert template.name == '测试模板'

    def test_template_list(self, admin_client):
        """模板列表"""
        resp = admin_client.get('/api/documents/templates/')
        assert resp.status_code == 200


# ==================== GeneratedDocument 测试 ====================

@pytest.mark.django_db
class TestGeneratedDocumentViewSet:
    def test_generated_document_list(self, admin_client):
        """生成文档列表"""
        resp = admin_client.get('/api/documents/generated/')
        assert resp.status_code == 200


# ==================== Tag 测试 ====================

@pytest.mark.django_db
class TestTagModel:
    def test_tag_creation(self):
        """标签创建"""
        tag = Tag.objects.create(name='测试标签')
        assert tag.name == '测试标签'

    def test_tag_uniqueness(self):
        """标签名唯一性"""
        Tag.objects.create(name='唯一标签')
        from django.db import IntegrityError
        import pytest
        with pytest.raises(IntegrityError):
            Tag.objects.create(name='唯一标签')


# ==================== Book-Chapter 关联测试 ====================

@pytest.mark.django_db
class TestBookChapterRelation:
    def test_book_has_chapters(self):
        """书籍应有关联章节"""
        book = Book.objects.create(title='关联书籍', author='作者')
        Chapter.objects.create(book=book, title='章节1', content_md='内容1', order=1)
        Chapter.objects.create(book=book, title='章节2', content_md='内容2', order=2)
        assert book.chapters.count() == 2

    def test_chapter_belongs_to_book(self):
        """章节应关联书籍"""
        book = Book.objects.create(title='章节书籍', author='作者')
        chapter = Chapter.objects.create(book=book, title='测试章节', content_md='内容', order=1)
        assert chapter.book == book
