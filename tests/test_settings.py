from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_joplin.settings import Settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", "t")
    monkeypatch.setenv("MCP_API_KEY", "test-api-key-123456")
    s = Settings()
    assert s.joplin_token == "t"
    assert s.mcp_api_key == "test-api-key-123456"


def test_short_api_key_rejected_without_echoing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", "t")
    monkeypatch.setenv("MCP_API_KEY", "elevenchars")  # 11 characters
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    message = str(excinfo.value)
    assert "MCP_API_KEY" in message
    assert "at least 12 characters" in message
    assert "elevenchars" not in message


def test_twelve_char_api_key_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JOPLIN_TOKEN", "t")
    monkeypatch.setenv("MCP_API_KEY", "twelve-chars")
    assert Settings().mcp_api_key == "twelve-chars"


def test_env_example_copied_unchanged_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    # The README says to copy .env.example to .env; that must not fail validation
    # for stdio/doctor, which need no API key. (A short placeholder once did.)
    import shutil
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / ".env.example"
    shutil.copy(example, ".env")  # cwd is a temporary directory (conftest)
    for name in ("JOPLIN_TOKEN", "MCP_API_KEY", "MCP_READ_ONLY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.mcp_api_key is None
    assert settings.read_only is False
