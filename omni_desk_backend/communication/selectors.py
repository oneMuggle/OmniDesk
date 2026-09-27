"""交流帖子的可见性规则（HTTP 接口与 AI 工具共用）。

当前规则：所有已登录用户都可以阅读未归档的帖子；修改、删除只允许作者本人
（由 ``views.IsAuthorOrReadOnly`` 负责）。
"""

from __future__ import annotations

from communication.models import Post


def visible_posts(user=None):
    """返回 ``user`` 可阅读的帖子；未登录用户返回空集。

    ``user`` 为 ``None`` 时只套用归档规则，供类属性 ``queryset`` 使用
    （DRF 的 ``IsAuthenticated`` 已拦截匿名请求）。
    """
    qs = Post.objects.filter(is_archived=False)
    if user is not None and not getattr(user, "is_authenticated", False):
        return qs.none()
    return qs
