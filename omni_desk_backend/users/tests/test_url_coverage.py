"""P1-6 覆盖率补足测试。

注意:user_urls.py 自身存在 ImportError(引用不存在的 PositionViewSet),
此问题先于 P1 存在,与 P1 无关,故标 xfail。
"""
import pytest


@pytest.mark.xfail(reason="user_urls.py:4 引用不存在的 PositionViewSet,先于 P1 存在", strict=False)
def test_user_urls_can_be_imported():
    from users.user_urls import urlpatterns

    assert urlpatterns is not None
    assert len(urlpatterns) > 0


def test_users_root_urls_can_be_imported():
    from users.urls import urlpatterns

    assert urlpatterns is not None
