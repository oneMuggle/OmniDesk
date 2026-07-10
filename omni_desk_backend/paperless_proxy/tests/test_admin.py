from django.contrib import admin
from ..models import DocumentBinding, OutboxItem, UserPaperlessBinding, PaperlessHealth


def test_all_paperless_models_registered_in_admin():
    """4 个 paperless 模型必须在 Django admin 中已注册"""
    registered = set(admin.site._registry.keys())
    for model in (DocumentBinding, OutboxItem, UserPaperlessBinding, PaperlessHealth):
        assert model in registered, f"{model.__name__} 未注册到 Django admin"


def test_document_binding_admin_has_list_display():
    from ..models import DocumentBinding
    ma = admin.site._registry[DocumentBinding]
    display = ma.list_display
    assert 'owner' in display or any('owner' in str(c) for c in display)
