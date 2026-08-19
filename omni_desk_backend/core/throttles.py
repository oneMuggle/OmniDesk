"""DRF throttle classes for the OmniDesk backend.

See https://www.django-rest-framework.org/api-guide/throttling/

Each throttle class binds a unique ``scope`` so DRF's cache backend can
track per-key (IP or user) hit counts independently.
"""

from rest_framework.throttling import AnonRateThrottle


class ClientErrorAnonThrottle(AnonRateThrottle):
    """前端错误上报端点限流(10/min/IP)。

    浏览器侧上报可能因错误循环或异常刷屏触发高频请求,需限流防止后端负载/日志爆掉。
    选 AnonRateThrottle 而非 UserRateThrottle 是因为该端点必须 AllowAny(覆盖未登录错误),
    未登录场景下只有 IP 可用。
    """

    scope = "client_error"
