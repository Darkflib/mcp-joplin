"""Structured logging configuration with JSON output."""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self):
        """Initialize JSON formatter."""
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add any extra attributes passed to logger
        excluded_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "extra_fields",
        }

        for key, value in record.__dict__.items():
            if key not in excluded_attrs and not key.startswith("_"):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter."""

    def __init__(self):
        """Initialize text formatter."""
        super().__init__(
            fmt="%(asctime)s | %(levelname)8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with extra fields."""
        # Format base message
        formatted = super().format(record)

        # Add extra fields if present
        excluded_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
            "extra_fields",
        }

        extra_fields = []
        for key, value in record.__dict__.items():
            if key not in excluded_attrs and not key.startswith("_"):
                extra_fields.append(f"{key}={value}")

        if extra_fields:
            formatted += f" | {' '.join(extra_fields)}"

        return formatted


def setup_logging(level: str = "INFO", format_type: str = "json") -> None:
    """Setup logging configuration."""

    # Determine log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Choose formatter
    if format_type.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Configure specific loggers
    loggers_config = {
        "httpx": logging.WARNING,  # Reduce httpx verbosity
        "urllib3": logging.WARNING,  # Reduce urllib3 verbosity
        "asyncio": logging.WARNING,  # Reduce asyncio verbosity
    }

    for logger_name, logger_level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(logger_level)

    # Log configuration
    root_logger.info(
        "Logging configured",
        extra={"level": level, "format": format_type, "handlers": ["console"]},
    )


class StructuredLogger:
    """Wrapper for structured logging with extra context."""

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.context = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set persistent context for all log messages."""
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear persistent context."""
        self.context.clear()

    def _log_with_context(
        self, level: int, message: str, extra: dict[str, Any] = None
    ) -> None:
        """Log message with context and extra fields."""
        combined_extra = self.context.copy()
        if extra:
            combined_extra.update(extra)

        self.logger.log(level, message, extra=combined_extra)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log_with_context(logging.ERROR, message, kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, message, kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance."""
    return StructuredLogger(name)
