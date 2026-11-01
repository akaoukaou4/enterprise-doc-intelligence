import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

# Probes and UI polling would flood the log, so they are logged at DEBUG.
QUIET_PATH_PREFIXES = ("/health",)


class RequestLogMiddleware:
    """One log line per request: id, method, path, status, latency. No query, no body (I9)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Always our own id: a client-supplied one could inject text into the log.
        # No reset afterwards: each request runs in its own task, and the error
        # handler for unexpected errors runs after this middleware and needs the id.
        request_id = uuid.uuid4().hex[:12]
        request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500  # stays 500 if an unexpected error escapes before a response starts

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            path = scope["path"]
            level = logging.DEBUG if path.startswith(QUIET_PATH_PREFIXES) else logging.INFO
            logger.log(
                level,
                "%s %s -> %d in %.0f ms",
                scope["method"],
                path,
                status,
                elapsed_ms,
            )
