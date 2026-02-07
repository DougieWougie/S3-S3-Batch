"""Structured JSON logging optimized for CloudWatch."""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for CloudWatch structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "function_name": os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local"),
            "request_id": getattr(record, "request_id", ""),
        }

        # Merge extra structured fields
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry.update(record.extra_data)

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stacktrace": traceback.format_exception(*record.exc_info),
            }

        return json.dumps(log_entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Create a structured JSON logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    request_id: str = "",
    **kwargs,
) -> None:
    """Log a message with structured context data."""
    extra = {"request_id": request_id, "extra_data": kwargs}
    logger.log(level, message, extra=extra)
