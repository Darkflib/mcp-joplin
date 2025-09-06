"""Error handling middleware for all tools."""

import logging
import traceback
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from mcp import types

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling for MCP tools."""

    @staticmethod
    def handle_tool_error(tool_name: str, error: Exception) -> list[types.TextContent]:
        """Handle tool execution errors with appropriate responses."""
        error_type = type(error).__name__
        error_message = str(error)

        # Log the error with context
        logger.error(
            "Tool execution failed",
            extra={
                "tool_name": tool_name,
                "error_type": error_type,
                "error_message": error_message,
                "traceback": traceback.format_exc(),
            },
        )

        # Determine user-friendly error message
        user_message = ErrorHandler._get_user_friendly_message(
            error_type, error_message
        )

        return [types.TextContent(type="text", text=f"Error: {user_message}")]

    @staticmethod
    def _get_user_friendly_message(error_type: str, error_message: str) -> str:
        """Convert technical errors to user-friendly messages."""
        # Connection related errors
        if "connection" in error_message.lower():
            if "refused" in error_message.lower():
                return "Cannot connect to Joplin. Please ensure Joplin is running and Web Clipper is enabled."
            elif "timeout" in error_message.lower():
                return "Connection to Joplin timed out. Please check your network connection."
            else:
                return "Failed to connect to Joplin. Please check your connection settings."

        # Authentication errors
        if (
            error_type == "AuthenticationError"
            or "401" in error_message
            or "unauthorized" in error_message.lower()
        ):
            return "Authentication failed. Please check your Joplin API token."

        # Validation errors
        if error_type == "ValueError" or "validation" in error_message.lower():
            if "required field" in error_message.lower():
                return f"Missing required parameter: {error_message}"
            elif "invalid type" in error_message.lower():
                return f"Invalid parameter type: {error_message}"
            elif "pattern" in error_message.lower():
                return (
                    "Invalid parameter format. Please check the parameter requirements."
                )
            else:
                return f"Invalid input: {error_message}"

        # Not found errors
        if "not found" in error_message.lower() or "404" in error_message:
            return "The requested item was not found in Joplin."

        # Rate limiting errors
        if "rate limit" in error_message.lower() or "429" in error_message:
            return "Too many requests. Please wait a moment and try again."

        # JSON parsing errors
        if "json" in error_message.lower() and "decode" in error_message.lower():
            return "Received invalid response from Joplin. Please try again."

        # Generic server errors
        if "500" in error_message or "server error" in error_message.lower():
            return "Joplin server error. Please try again later."

        # Default fallback
        return f"An error occurred: {error_message}"

    @staticmethod
    def with_error_handling(tool_name: str):
        """Decorator to add error handling to tool functions."""

        def decorator(func: Callable[..., Awaitable[list[types.TextContent]]]):
            @wraps(func)
            async def wrapper(*args, **kwargs) -> list[types.TextContent]:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    return ErrorHandler.handle_tool_error(tool_name, e)

            return wrapper

        return decorator


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class AuthenticationError(Exception):
    """Custom exception for authentication errors."""

    pass


class ConnectionError(Exception):
    """Custom exception for connection errors."""

    pass


class RateLimitError(Exception):
    """Custom exception for rate limiting errors."""

    pass


def validate_required_field(arguments: dict[str, Any], field_name: str) -> Any:
    """Validate that a required field is present and not empty."""
    if field_name not in arguments:
        raise ValidationError(f"Missing required field: {field_name}")

    value = arguments[field_name]
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"Field '{field_name}' cannot be empty")

    return value


def validate_field_type(
    arguments: dict[str, Any],
    field_name: str,
    expected_type: type,
    required: bool = True,
) -> Any:
    """Validate that a field has the expected type."""
    if field_name not in arguments:
        if required:
            raise ValidationError(f"Missing required field: {field_name}")
        return None

    value = arguments[field_name]
    if value is None:
        if required:
            raise ValidationError(f"Field '{field_name}' cannot be null")
        return None

    if not isinstance(value, expected_type):
        raise ValidationError(
            f"Field '{field_name}' has invalid type, expected {expected_type.__name__}"
        )

    return value


def validate_id_format(id_value: str, field_name: str) -> str:
    """Validate Joplin ID format (32-character hex)."""
    if not isinstance(id_value, str):
        raise ValidationError(f"Field '{field_name}' must be a string")

    if len(id_value) != 32:
        raise ValidationError(f"Field '{field_name}' must be 32 characters long")

    if not all(c in "0123456789abcdef" for c in id_value.lower()):
        raise ValidationError(
            f"Field '{field_name}' must contain only hexadecimal characters"
        )

    return id_value.lower()


def validate_range(
    value: int, field_name: str, min_val: int = None, max_val: int = None
) -> int:
    """Validate that a numeric value is within range."""
    if min_val is not None and value < min_val:
        raise ValidationError(f"Field '{field_name}' must be >= {min_val}")

    if max_val is not None and value > max_val:
        raise ValidationError(f"Field '{field_name}' must be <= {max_val}")

    return value


class ContextualLogger:
    """Logger that includes tool context in all messages."""

    def __init__(self, tool_name: str, logger: logging.Logger = None):
        """Initialize contextual logger."""
        self.tool_name = tool_name
        self.logger = logger or logging.getLogger(__name__)

    def debug(self, message: str, **extra):
        """Log debug message with tool context."""
        extra["tool_name"] = self.tool_name
        self.logger.debug(message, extra=extra)

    def info(self, message: str, **extra):
        """Log info message with tool context."""
        extra["tool_name"] = self.tool_name
        self.logger.info(message, extra=extra)

    def warning(self, message: str, **extra):
        """Log warning message with tool context."""
        extra["tool_name"] = self.tool_name
        self.logger.warning(message, extra=extra)

    def error(self, message: str, **extra):
        """Log error message with tool context."""
        extra["tool_name"] = self.tool_name
        self.logger.error(message, extra=extra)

    def critical(self, message: str, **extra):
        """Log critical message with tool context."""
        extra["tool_name"] = self.tool_name
        self.logger.critical(message, extra=extra)
