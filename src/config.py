"""Configuration management (env vars + config file)."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Configuration related errors."""

    pass


class ConfigManager:
    """Manages configuration from environment variables and config files."""

    def __init__(self, config_file_path: str | None = None):
        """Initialize configuration manager."""
        self.config_file_path = config_file_path
        self._config: dict[str, Any] = {}

        # Load .env file if present
        self._load_env_file()

        # Load configuration
        self._load_configuration()

        logger.info(
            "Configuration manager initialized",
            extra={
                "config_file": config_file_path,
                "has_env_file": Path(".env").exists(),
            },
        )

    def _load_env_file(self) -> None:
        """Load environment variables from .env file."""
        env_files = [".env", ".env.local"]

        for env_file in env_files:
            if Path(env_file).exists():
                load_dotenv(env_file)
                logger.info(f"Loaded environment file: {env_file}")
                break

    def _load_configuration(self) -> None:
        """Load configuration from environment and file."""
        # Start with default configuration
        self._config = self._get_default_config()

        # Override with config file if provided
        if self.config_file_path:
            file_config = self._load_config_file(self.config_file_path)
            self._merge_config(self._config, file_config)

        # Override with environment variables
        env_config = self._load_env_config()
        self._merge_config(self._config, env_config)

        # Validate configuration
        self._validate_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration values."""
        return {
            "joplin": {
                "base_url": "http://localhost:41184",
                "api_token": "",
                "timeout": 30.0,
                "rate_limit": 60,
                "max_retries": 3,
                "retry_delay": 1.0,
            },
            "server": {
                "host": "localhost",
                "port": 3000,
                "name": "joplin-mcp-server",
                "version": "0.1.0",
            },
            "rate_limiting": {"requests_per_minute": 60, "burst_size": 10},
            "logging": {"level": "INFO", "format": "json"},
        }

    def _load_config_file(self, file_path: str) -> dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            config_path = Path(file_path)
            if not config_path.exists():
                logger.warning(f"Config file not found: {file_path}")
                return {}

            with open(config_path, encoding="utf-8") as f:
                file_config = json.load(f)

            logger.info(f"Loaded config file: {file_path}")
            return file_config

        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in config file {file_path}: {e}"
            ) from e
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load config file {file_path}: {e}"
            ) from e

    def _load_env_config(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}

        # Joplin configuration
        joplin_config = {}
        if os.getenv("JOPLIN_API_URL"):
            joplin_config["base_url"] = os.getenv("JOPLIN_API_URL")
        if os.getenv("JOPLIN_API_TOKEN"):
            joplin_config["api_token"] = os.getenv("JOPLIN_API_TOKEN")
        if os.getenv("JOPLIN_TIMEOUT"):
            joplin_config["timeout"] = float(os.getenv("JOPLIN_TIMEOUT"))
        if os.getenv("JOPLIN_RATE_LIMIT"):
            joplin_config["rate_limit"] = int(os.getenv("JOPLIN_RATE_LIMIT"))
        if os.getenv("JOPLIN_MAX_RETRIES"):
            joplin_config["max_retries"] = int(os.getenv("JOPLIN_MAX_RETRIES"))

        if joplin_config:
            env_config["joplin"] = joplin_config

        # Server configuration
        server_config = {}
        if os.getenv("MCP_SERVER_HOST"):
            server_config["host"] = os.getenv("MCP_SERVER_HOST")
        if os.getenv("MCP_SERVER_PORT"):
            server_config["port"] = int(os.getenv("MCP_SERVER_PORT"))

        if server_config:
            env_config["server"] = server_config

        # Rate limiting configuration
        rate_config = {}
        if os.getenv("RATE_LIMIT_RPM"):
            rate_config["requests_per_minute"] = int(os.getenv("RATE_LIMIT_RPM"))
        if os.getenv("RATE_LIMIT_BURST"):
            rate_config["burst_size"] = int(os.getenv("RATE_LIMIT_BURST"))

        if rate_config:
            env_config["rate_limiting"] = rate_config

        # Logging configuration
        log_config = {}
        if os.getenv("LOG_LEVEL"):
            log_config["level"] = os.getenv("LOG_LEVEL").upper()
        if os.getenv("LOG_FORMAT"):
            log_config["format"] = os.getenv("LOG_FORMAT")

        if log_config:
            env_config["logging"] = log_config

        if env_config:
            logger.info("Loaded configuration from environment variables")

        return env_config

    def _merge_config(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        """Merge override configuration into base configuration."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                self._merge_config(base[key], value)
            else:
                # Override value
                base[key] = value

    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        errors = []

        # Validate Joplin configuration
        joplin_config = self._config.get("joplin", {})

        if not joplin_config.get("api_token"):
            errors.append("Joplin API token is required (JOPLIN_API_TOKEN)")

        if not joplin_config.get("base_url"):
            errors.append("Joplin base URL is required (JOPLIN_API_URL)")

        # Validate numeric values
        try:
            timeout = joplin_config.get("timeout", 30.0)
            if not isinstance(timeout, int | float) or timeout <= 0:
                errors.append("Joplin timeout must be a positive number")
        except (TypeError, ValueError):
            errors.append("Invalid Joplin timeout value")

        try:
            rate_limit = joplin_config.get("rate_limit", 60)
            if not isinstance(rate_limit, int) or rate_limit <= 0:
                errors.append("Joplin rate limit must be a positive integer")
        except (TypeError, ValueError):
            errors.append("Invalid Joplin rate limit value")

        # Validate server configuration
        server_config = self._config.get("server", {})
        try:
            port = server_config.get("port", 3000)
            if not isinstance(port, int) or not (1 <= port <= 65535):
                errors.append("Server port must be an integer between 1 and 65535")
        except (TypeError, ValueError):
            errors.append("Invalid server port value")

        # Raise errors if any
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"- {error}" for error in errors
            )
            raise ConfigurationError(error_msg)

        logger.info("Configuration validation passed")

    def get_config(self) -> dict[str, Any]:
        """Get the complete configuration."""
        return self._config.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)."""
        keys = key.split(".")
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key (supports dot notation)."""
        keys = key.split(".")
        config = self._config

        # Navigate to parent
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set value
        config[keys[-1]] = value

        logger.info(f"Configuration updated: {key} = {value}")

    def get_joplin_config(self) -> dict[str, Any]:
        """Get Joplin-specific configuration."""
        return self._config.get("joplin", {})

    def get_server_config(self) -> dict[str, Any]:
        """Get server-specific configuration."""
        return self._config.get("server", {})

    def get_logging_config(self) -> dict[str, Any]:
        """Get logging-specific configuration."""
        return self._config.get("logging", {})


def load_config(config_file: str | None = None) -> ConfigManager:
    """Load configuration from file and environment."""
    return ConfigManager(config_file)
