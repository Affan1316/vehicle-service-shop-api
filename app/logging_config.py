"""
Structured logging configuration for the Vehicle Service Shop API.

Emits JSON-formatted log records so they can be ingested by log aggregators
(ELK, Datadog, CloudWatch, etc.) without custom parsing.
"""

import logging
import sys
from datetime import datetime, timezone


from pythonjsonlogger import json as json_logger

class CustomJsonFormatter(json_logger.JsonFormatter):
    """Format log records as single-line JSON objects using python-json-logger."""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure the root logger and key library loggers.

    Call this once at application startup (before any request is served).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers to avoid duplicates on reloads
    root.handlers.clear()

    # Console handler with JSON output
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(CustomJsonFormatter())
    root.addHandler(console)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
