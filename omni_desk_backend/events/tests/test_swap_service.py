"""swap_service 单元测试"""

import pytest

from events.services.swap_service import (
    SwapServiceError,
    SwapPermissionError,
    SwapNotFoundError,
)


class TestSwapServiceExceptions:
    """异常类可正确实例化 + 抛出/捕获语义正确"""

    def test_swap_service_error_inherits_exception(self):
        """SwapServiceError 是 Exception 子类"""
        assert issubclass(SwapServiceError, Exception)

    def test_swap_permission_error_inherits_exception(self):
        """SwapPermissionError 是 Exception 子类"""
        assert issubclass(SwapPermissionError, Exception)

    def test_swap_not_found_error_inherits_exception(self):
        """SwapNotFoundError 是 Exception 子类"""
        assert issubclass(SwapNotFoundError, Exception)

    def test_swap_service_error_catchable(self):
        """SwapServiceError 可被 except Exception 捕获"""
        with pytest.raises(SwapServiceError, match="业务错误"):
            raise SwapServiceError("业务错误")

    def test_swap_permission_error_distinct_from_service(self):
        """SwapPermissionError 不是 SwapServiceError 子类(独立异常层级)"""
        assert not issubclass(SwapPermissionError, SwapServiceError)

    def test_swap_not_found_error_distinct_from_service(self):
        """SwapNotFoundError 不是 SwapServiceError 子类"""
        assert not issubclass(SwapNotFoundError, SwapServiceError)
