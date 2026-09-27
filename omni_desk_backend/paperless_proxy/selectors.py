"""文档库（DocumentBinding）的可见性规则（HTTP 接口与 AI 工具共用）。

- staff：全部文档；
- 其他已登录用户：只看自己上传（owner）的文档；
- 未登录：空集。
"""

from __future__ import annotations

from paperless_proxy.models import DocumentBinding


def visible_bindings(user, qs=None):
    if qs is None:
        qs = DocumentBinding.objects.all()
    if not user or not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.is_staff:
        return qs
    return qs.filter(owner=user)
