"""
Request-tracking middleware for the Vehicle Service Shop API.

Assigns a unique request ID to every inbound request, measures elapsed time,
and emits a structured JSON log record on completion.
"""

import logging  # Built-in logging library to record request details
import time  # Time library used for benchmarking process duration
import uuid  # Library used to generate random request correlation IDs (UUIDv4)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint  # Starlette tools to write custom HTTP request middlewares
from starlette.requests import Request  # Request type representing incoming HTTP calls
from starlette.responses import Response  # Response type representing returned HTTP payloads

# Instantiate logger for requests tracking
logger = logging.getLogger("auto_shop.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that intercepts all HTTP requests to:
    1. Retrieve or generate a unique X-Request-ID for request tracing.
    2. Measure how long it takes to process the request.
    3. Log structured request details (method, path, status, duration).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. RETRIEVE OR GENERATE REQUEST CORRELATION ID
        # Checks if the client sent an 'X-Request-ID' header, otherwise generates a random UUID.
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        client_ip = request.client.host if request.client else "unknown"

        # 2. START THE TIMERS
        # Using time.perf_counter() for accurate microsecond-level benchmarking
        start = time.perf_counter()

        try:
            # Pass the request down to the next middleware or router endpoint handler
            response = await call_next(request)
        except Exception:
            # If any unhandled exception occurs during endpoint execution, log the failure and raise it
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "duration_ms": duration_ms,
                    "status_code": 500,
                },
                exc_info=True, # Attaches the exception stack trace to the log message
            )
            raise

        # 3. CALCULATE PROCESS TIME
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Attach the request ID to the outgoing response headers so the client knows their Request ID
        response.headers["X-Request-ID"] = request_id

        # 4. CHOOSE APPROPRIATE LOG LEVEL
        status_code = response.status_code
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        # 5. EMIT STRUCTURED LOG
        # The 'extra' parameter injects structured fields into the JSON log entry
        log_fn(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            },
        )

        return response
