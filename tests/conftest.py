"""Shared test setup."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_local_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run every test from an empty directory.

    Settings reads `.env` from the working directory, and the README tells
    people to create one. Without this, a developer's own MCP_READ_ONLY,
    JOPLIN_BASE_URL or MCP_HOST would leak into tests that build Settings().
    """
    monkeypatch.chdir(tmp_path)
