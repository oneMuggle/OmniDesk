"""Project-wide Django middleware."""

from __future__ import annotations

import uuid

from observability.context import request_id_var


class RequestIdMiddleware:
    """Attach a stable request_id to every request and response.

    Reads X-Request-ID from the incoming request, falling back to a fresh
    uuid4 hex when absent. The id is exposed on ``request.request_id``
    and pushed into the ``request_id_var`` ContextVar so that any logger
    call inside the request lifecycle automatically picks it up via the
    ``_EventLoggerAdapter`` in :mod:`observability`.
    """

    HEADER_NAME = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"
    REQUEST_ATTR = "request_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.META.get(self.HEADER_NAME) or uuid.uuid4().hex
        setattr(request, self.REQUEST_ATTR, rid)
        token = request_id_var.set(rid)
        try:
            response = self.get_response(request)
            response[self.RESPONSE_HEADER] = rid
            return response
        finally:
            request_id_var.reset(token)
