"""Application settings (env/.env)."""

from __future__ import annotations

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for the MCP server and Joplin Data API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    joplin_token: str = Field(alias="JOPLIN_TOKEN", min_length=1)
    joplin_base_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("http://127.0.0.1:41184"),
        alias="JOPLIN_BASE_URL",
    )

    mcp_api_key: str = Field(alias="MCP_API_KEY", min_length=1)
    mcp_host: str = Field(default="127.0.0.1", alias="MCP_HOST")
    mcp_port: int = Field(default=5005, alias="MCP_PORT", ge=1, le=65535)

    http_timeout_seconds: float = Field(
        default=15.0,
        alias="HTTP_TIMEOUT_SECONDS",
        gt=0,
    )
