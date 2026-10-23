"""Application settings (env/.env)."""

from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_API_KEY_LENGTH = 12


class Settings(BaseSettings):
    """Settings for the MCP server and Joplin Data API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Validation errors otherwise echo the rejected value, and startup
        # tracebacks land in logs (e.g. the sidecar launcher's panel).
        hide_input_in_errors=True,
    )

    joplin_token: str = Field(alias="JOPLIN_TOKEN", min_length=1)
    joplin_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://127.0.0.1:41184"),
        alias="JOPLIN_BASE_URL",
    )

    # Required for HTTP serving (see require_api_key); unused over stdio, where
    # the client launches the process and there is no network surface.
    # Anything shorter is guessable, and secrets under 8 characters are also
    # exempt from log redaction (see redaction.redact).
    mcp_api_key: str | None = Field(
        default=None, alias="MCP_API_KEY", min_length=MIN_API_KEY_LENGTH
    )
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=5005, alias="MCP_PORT", ge=1, le=65535)

    http_timeout_seconds: float = Field(
        default=15.0,
        alias="HTTP_TIMEOUT_SECONDS",
        gt=0,
    )

    def require_api_key(self) -> str:
        """Return the API key, or raise if HTTP serving was asked for without one."""
        if not self.mcp_api_key:
            raise ConfigError(
                "MCP_API_KEY is not set. It is required for the HTTP server "
                f"(at least {MIN_API_KEY_LENGTH} characters). Generate one with: "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return self.mcp_api_key

    def secrets(self) -> list[str]:
        """Every configured credential, for log redaction."""
        return [s for s in (self.joplin_token, self.mcp_api_key) if s]


class ConfigError(RuntimeError):
    """Configuration is invalid for the requested mode."""
