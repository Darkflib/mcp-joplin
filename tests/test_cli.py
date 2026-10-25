"""CLI: subcommand dispatch, doctor report, config-error exit codes, real stdio run."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import pytest
import respx
from mcp import Client, StdioServerParameters

from mcp_joplin import __main__ as cli

BASE = "http://127.0.0.1:41184"
TOKEN = "SECRET-joplin-token-0123456789"
API_KEY = "test-api-key-123456"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No stray .env from the repo root, and a known baseline environment.
    monkeypatch.chdir(tmp_path)
    for name in ("JOPLIN_TOKEN", "JOPLIN_BASE_URL", "MCP_API_KEY", "MCP_HOST", "MCP_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JOPLIN_TOKEN", TOKEN)
    # A port nothing else in the test run binds.
    monkeypatch.setenv("MCP_PORT", "58231")


def run(argv: list[str]) -> int:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    code = excinfo.value.code
    assert isinstance(code, int)
    return code


def test_no_subcommand_means_serve() -> None:
    args = cli.build_parser().parse_args([])
    assert args.func is cli.cmd_serve


@respx.mock
def test_doctor_all_good(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MCP_API_KEY", API_KEY)
    respx.get(f"{BASE}/ping").mock(return_value=httpx.Response(200, text="JoplinClipService"))
    respx.get(f"{BASE}/folders").mock(return_value=httpx.Response(200, json={"items": []}))

    assert run(["doctor"]) == 0
    out = capsys.readouterr()
    assert "[  ok] Joplin (http://127.0.0.1:41184)" in out.out
    assert f"set ({len(API_KEY)} characters)" in out.out
    assert "127.0.0.1:58231 free" in out.out
    for stream in (out.out, out.err):
        assert TOKEN not in stream
        assert API_KEY not in stream


@respx.mock
def test_doctor_fails_on_bad_token_and_warns_on_missing_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    respx.get(f"{BASE}/ping").mock(return_value=httpx.Response(200, text="JoplinClipService"))
    respx.get(f"{BASE}/folders").mock(return_value=httpx.Response(403))

    assert run(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] Joplin" in out
    assert "rejected the API token" in out
    assert "[warn] MCP_API_KEY: not set" in out


def test_serve_without_key_exits_with_config_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["serve"]) == cli.EXIT_CONFIG
    err = capsys.readouterr().err
    assert "MCP_API_KEY is not set" in err
    assert "Traceback" not in err


def test_short_key_exits_with_config_code_without_echoing_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MCP_API_KEY", "elevenchars")
    assert run(["serve"]) == cli.EXIT_CONFIG
    err = capsys.readouterr().err
    assert "MCP_API_KEY: String should have at least 12 characters" in err
    assert "elevenchars" not in err


def test_missing_joplin_token_exits_with_config_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("JOPLIN_TOKEN")
    assert run(["doctor"]) == cli.EXIT_CONFIG
    assert "JOPLIN_TOKEN" in capsys.readouterr().err


async def test_stdio_serves_tools_without_api_key(tmp_path: Path) -> None:
    # A real subprocess, as an MCP client that launches the server would run it.
    # Joplin isn't needed to list tools; the API key isn't needed at all.
    env = {k: v for k, v in os.environ.items() if k != "MCP_API_KEY"}
    env["JOPLIN_TOKEN"] = TOKEN
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_joplin", "stdio"],
        env=env,
        cwd=str(tmp_path),
    )
    async with Client(params) as client:
        tools = await client.list_tools()
    assert "notes_get" in {t.name for t in tools.tools}


def test_legacy_command_still_works_and_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The pre-0.2 command name is kept for existing launcher/client configs.
    called: list[str] = []

    def fake_doctor(args: object) -> int:
        called.append("doctor")
        return 0

    monkeypatch.setattr(cli, "cmd_doctor", fake_doctor)
    with pytest.raises(SystemExit) as excinfo:
        cli.legacy_main(["doctor"])
    assert excinfo.value.code == 0
    assert called == ["doctor"]
    captured = capsys.readouterr()
    assert "deprecated" in captured.err and "mcp-joplin" in captured.err
    assert captured.out == ""  # stdout stays clean for the stdio transport
