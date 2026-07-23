# omni_desk_backend/paperless_proxy/exceptions.py
"""paperless_proxy 自定义异常"""


class PaperlessError(Exception):
    """paperless 调用相关错误的基类"""


class PaperlessUnavailableError(PaperlessError):
    """paperless 服务不可用(网络/超时/5xx)"""


class PaperlessAuthError(PaperlessError):
    """paperless 认证失败(401/403)"""


class PaperlessNotFoundError(PaperlessError):
    """paperless 资源不存在(404)"""
