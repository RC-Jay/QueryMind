"""
Structured logging + request correlation.

Every log line is JSON and carries a `request_id` so all logs from one request
can be traced together. A middleware assigns the id (from an inbound
`X-Request-ID` header or a fresh one), times the request, and logs a structured
access line. This is sink-agnostic — Azure App Insights, Loki, CloudWatch, etc.
can all ingest JSON stdout.
"""
import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.requests import Request

# Propagates the current request id to every log record within the request.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Extra fields the formatter will surface when present on a record.
_EXTRA_KEYS = ("method", "path", "status_code", "duration_ms")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter + request-id filter on the root logger."""
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Quiet noisy libraries to WARNING; our access log covers request flow.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_access_logger = logging.getLogger("api.access")


async def request_logging_middleware(request: Request, call_next):
    """Assign/propagate a request id, time the request, emit a structured access log."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        _access_logger.exception(
            "request failed",
            extra={"method": request.method, "path": request.url.path, "duration_ms": duration_ms},
        )
        request_id_var.reset(token)
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    _access_logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    request_id_var.reset(token)
    return response
