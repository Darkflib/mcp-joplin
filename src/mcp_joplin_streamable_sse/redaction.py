"""Keep the Joplin token out of error messages and log output.

The Joplin Data API only accepts its token as a ``?token=`` query parameter, so
every request URL carries it. Anything that stringifies a URL (httpx's request
logging, exception messages, tracebacks) would otherwise leak it to the MCP
client or to whatever captures stdout (e.g. the sidecar launcher's log panel).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

REDACTED = "***"

# Matches the value of a ``token`` query parameter in any URL-ish string.
_TOKEN_PARAM_RE = re.compile(r"(?i)([?&]token=)[^&\s\"'#]+")

# Loggers that log full request URLs at INFO. Kept at WARNING regardless of the
# root level; the redacting filter is a backstop, not the primary control.
_NOISY_URL_LOGGERS = ("httpx", "httpcore")


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Return ``text`` with token query parameters and any literal secrets masked."""
    redacted = _TOKEN_PARAM_RE.sub(rf"\g<1>{REDACTED}", text)
    for secret in secrets:
        # Very short values would mangle unrelated text and aren't real tokens.
        if secret and len(secret) >= 8:
            redacted = redacted.replace(secret, REDACTED)
    return redacted


class RedactingFilter(logging.Filter):
    """Logging filter that masks secrets in the fully formatted message."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(s for s in secrets if s)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed record; let logging report it
            return True
        cleaned = redact(message, self._secrets)
        if cleaned != message:
            # Freeze the cleaned message so handlers don't re-interpolate args.
            record.msg = cleaned
            record.args = None
        if record.exc_info and not record.exc_text:
            # Pre-render the traceback so it can be redacted too.
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact(record.exc_text, self._secrets)
        return True


def install_log_redaction(secrets: Iterable[str] = ()) -> None:
    """Attach a RedactingFilter to every handler currently configured.

    Filters on a logger don't apply to records propagated from child loggers,
    so the filter goes on handlers. Call this after logging has been configured
    (FastMCP and uvicorn both install handlers of their own).
    """
    log_filter = RedactingFilter(secrets)
    for name in _NOISY_URL_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    loggers: list[logging.Logger] = [logging.getLogger()]
    loggers.extend(
        lg for lg in logging.Logger.manager.loggerDict.values() if isinstance(lg, logging.Logger)
    )
    for lg in loggers:
        for handler in lg.handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(log_filter)
