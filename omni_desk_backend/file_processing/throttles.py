"""file_processing 限流类。

See core/throttles.py for the project-wide throttle conventions.
"""

from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """文件上传限流(10/h/user)。

    上传触发 Celery 解析任务 + AI 分析,单用户高频上传会拖垮 worker;
    内网正常使用远达不到该阈值。
    """

    scope = "upload"
