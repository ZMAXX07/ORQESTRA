"""Structured logging configuration for Orqestra backend."""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "cookie",
    "credentials",
}


def sanitize_data(data: Any) -> Any:
    """Recursively mask sensitive values in dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    if isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


class StructuredJsonFormatter(logging.Formatter):
    """Format log records as clean JSON objects without leaking sensitive data."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if provided, after sanitizing
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_payload["data"] = sanitize_data(record.extra_data)

        return json.dumps(log_payload)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure root logger with structured JSON formatting."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on reinitialization
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(stream_handler)

    # Reduce verbosity of third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    return logging.getLogger("orqestra")
