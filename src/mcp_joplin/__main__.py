"""CLI entrypoint: ``serve`` (default), ``stdio``, and ``doctor``."""

from __future__ import annotations

import argparse
import asyncio
import errno
import socket
import sys
from collections.abc import Sequence

import uvicorn
from pydantic import ValidationError

from .asgi import create_app
from .health import JoplinHealth
from .mcp_server import create_mcp_server
from .settings import MIN_API_KEY_LENGTH, ConfigError, Settings

# Distinct from 1 (runtime failure) so a supervisor can tell "fix your config".
EXIT_CONFIG = 2


def _format_validation_error(exc: ValidationError) -> str:
    # Settings hides input values in errors; list field + reason only.
    lines = ["Invalid configuration:"]
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "(settings)"
        lines.append(f"  {field}: {err['msg']}")
    return "\n".join(lines)


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        print(_format_validation_error(exc), file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from None


def cmd_serve(_: argparse.Namespace) -> int:
    settings = _load_settings()
    try:
        app = create_app(settings)
    except ConfigError as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port, log_level="info")
    return 0


def cmd_stdio(_: argparse.Namespace) -> int:
    # For clients that launch the server themselves. No HTTP surface, so no API
    # key; all logging goes to stderr (stdout carries the protocol).
    settings = _load_settings()
    create_mcp_server(settings).run("stdio")
    return 0


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as sock:
        try:
            sock.bind((host, port))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                return True
            raise
    return False


async def _doctor(settings: Settings) -> list[tuple[str, str, str]]:
    """Return (level, check, message) rows; level is ok / warn / FAIL."""
    rows: list[tuple[str, str, str]] = [("ok", "settings", "configuration loaded")]

    if settings.mcp_api_key:
        rows.append(("ok", "MCP_API_KEY", f"set ({len(settings.mcp_api_key)} characters)"))
    else:
        rows.append(
            (
                "warn",
                "MCP_API_KEY",
                f"not set: required for `serve` (min {MIN_API_KEY_LENGTH} chars), "
                "not needed for `stdio`",
            )
        )

    checker = JoplinHealth(
        base_url=str(settings.joplin_base_url),
        token=settings.joplin_token,
        timeout_seconds=5.0,
        log_transitions=False,  # the report row says it already
    )
    try:
        result = await checker.check(force=True)
    finally:
        await checker.aclose()
    rows.append(
        (
            "ok" if result.ok else "FAIL",
            f"Joplin ({str(settings.joplin_base_url).rstrip('/')})",
            result.detail,
        )
    )

    try:
        in_use = _port_in_use(settings.mcp_host, settings.mcp_port)
    except OSError as exc:
        rows.append(("FAIL", "listen address", f"{settings.mcp_host}:{settings.mcp_port}: {exc}"))
    else:
        if in_use:
            rows.append(
                (
                    "warn",
                    "listen address",
                    f"{settings.mcp_host}:{settings.mcp_port} is in use "
                    "(already running, or another process holds it)",
                )
            )
        else:
            rows.append(("ok", "listen address", f"{settings.mcp_host}:{settings.mcp_port} free"))
    return rows


def cmd_doctor(_: argparse.Namespace) -> int:
    settings = _load_settings()
    rows = asyncio.run(_doctor(settings))
    for level, check, message in rows:
        print(f"[{level:>4}] {check}: {message}")
    return 1 if any(level == "FAIL" for level, _, _ in rows) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-joplin",
        description="MCP server for the Joplin Data API.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{serve,stdio,doctor}")
    sub.add_parser("serve", help="run the Streamable HTTP server (default)").set_defaults(
        func=cmd_serve
    )
    sub.add_parser("stdio", help="speak MCP over stdin/stdout").set_defaults(func=cmd_stdio)
    sub.add_parser("doctor", help="check configuration and Joplin connectivity").set_defaults(
        func=cmd_doctor
    )
    # No subcommand means `serve`, so existing launcher configs keep working.
    parser.set_defaults(func=cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(args.func(args))


def legacy_main(argv: Sequence[str] | None = None) -> None:
    """The pre-0.2 ``mcp-joplin-streamable-sse`` command: same CLI, plus a nudge.

    The notice goes to stderr so it can't corrupt the stdio transport, and it
    lands in the sidecar launcher's log panel where it will be seen.
    """
    print(
        "note: 'mcp-joplin-streamable-sse' is deprecated; run 'mcp-joplin' instead "
        "(same subcommands and settings).",
        file=sys.stderr,
    )
    main(argv)


if __name__ == "__main__":
    main()
