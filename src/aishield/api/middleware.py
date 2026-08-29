"""HTTP middleware that correlates and times every API request."""

import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aishield.core.logging import request_context

logger = logging.getLogger("aishield.api.request")

REQUEST_ID_HEADER = "X-Request-ID"
# Bound the accepted client-supplied id so it cannot bloat or poison log lines.
_MAX_CLIENT_REQUEST_ID = 128


def _resolve_request_id(request: Request) -> str:
    """Reuse a well-formed caller id so traces span a proxy, otherwise mint one."""

    supplied = request.headers.get(REQUEST_ID_HEADER)
    if supplied and 0 < len(supplied) <= _MAX_CLIENT_REQUEST_ID and supplied.isprintable():
        return supplied
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id to logs and echo it back on the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _resolve_request_id(request)
        started = time.perf_counter()
        with request_context(request_id):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "request failed",
                    extra={
                        "http_method": request.method,
                        "http_path": request.url.path,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    },
                )
                raise
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            logger.info(
                "request completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
