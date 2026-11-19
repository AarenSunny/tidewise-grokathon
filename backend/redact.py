"""Redact secrets and sensitive URLs from errors/logs/health (review1-#13)."""

from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

_KEY_QUERY = re.compile(
    r"(?i)([?&](?:api[_-]?key|token|access[_-]?token|key|auth|password|secret)=)[^&]*"
)
_PATH_KEY = re.compile(r"(?i)/((?:MAP_KEY|api[_-]?key|token)[^/]*)")
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-._~+/]+=*")
_ABS_PATH = re.compile(r"(?:/workspace|/home|/Users|/var/folders)[^\s\"']+")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _secret_values() -> list[str]:
    out: list[str] = []
    for name in ("XAI_API_KEY", "FIRMS_MAP_KEY", "OPENAI_API_KEY", "API_KEY"):
        v = os.getenv(name)
        if v and len(v) >= 8:
            out.append(v)
    return out


def redact(text: Optional[str]) -> str:
    """Return a safe string for logs, SourceResult.notes, and /health."""
    if text is None:
        return ""
    s = str(text)
    for secret in _secret_values():
        s = s.replace(secret, "[REDACTED]")
    s = _KEY_QUERY.sub(r"\1[REDACTED]", s)
    s = _BEARER.sub(r"\1[REDACTED]", s)
    s = _EMAIL.sub("[REDACTED_EMAIL]", s)
    s = _ABS_PATH.sub("[PATH]", s)

    # Strip query from any embedded http(s) URL; mask suspicious path segments
    def _scrub_url(m: re.Match[str]) -> str:
        url = m.group(0)
        parts = urlsplit(url)
        path = _PATH_KEY.sub(r"/[REDACTED]", parts.path)
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    s = re.sub(r"https?://[^\s\"']+", _scrub_url, s)
    return s


def redact_error(exc: BaseException) -> str:
    return redact(f"{type(exc).__name__}: {exc}")
