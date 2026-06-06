import os
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# 每用户每分钟最大请求数
SMART_CHAT_RATE_LIMIT = int(os.environ.get("SMART_ASSISTANT_CHAT_RATE_LIMIT", "30"))
RATE_WINDOW = 60


def check_rate_limit(user_id):
    """检查用户是否超出速率限制。

    Returns:
        (allowed, remaining, retry_after)
    """
    key = f"smart_assistant:rate_limit:{user_id}"
    current = cache.get(key, 0)

    if current >= SMART_CHAT_RATE_LIMIT:
        # 注意:cache.ttl 仅 Redis 等后端支持,locmem 没有。
        # 取不到 TTL 时退化为默认窗口。
        try:
            ttl = cache.ttl(key) or RATE_WINDOW
        except (AttributeError, NotImplementedError):
            ttl = RATE_WINDOW
        return False, 0, ttl

    # 注意:Django locmem cache 的 incr 在 key 不存在时抛 ValueError;
    # 而 cache.get 默认值 0 不会创建 key。先 set 再 incr 以兼容两类 backend。
    try:
        new_value = cache.incr(key)
    except ValueError:
        cache.set(key, 1, RATE_WINDOW)
        new_value = 1
    else:
        cache.set(key, new_value, RATE_WINDOW)

    remaining = SMART_CHAT_RATE_LIMIT - new_value
    return True, max(remaining, 0), 0


class RateLimitMiddleware:
    """智能助手速率限制中间件。

    仅对 /api/smart-assistant/chat/ 路径生效，基于用户 ID + 固定窗口。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/smart-assistant/chat/"):
            return self.get_response(request)

        if not hasattr(request, "user") or not request.user.is_authenticated:
            return self.get_response(request)

        allowed, remaining, retry_after = check_rate_limit(request.user.id)

        if not allowed:
            logger.warning("智能助手速率限制: user_id=%d, 重试后=%ds", request.user.id, retry_after)
            return JsonResponse(
                {
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
                status=429,
            )

        response = self.get_response(request)
        response["X-RateLimit-Remaining"] = str(remaining)
        response["X-RateLimit-Limit"] = str(SMART_CHAT_RATE_LIMIT)
        return response
