"""Redact PHI/PII from stdlib log records before handlers (incl. OTel) see them."""

from __future__ import annotations

import logging
import re
from typing import Any

REDACTED = "[REDACTED]"

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")
_FIELD_NAMES = (
    "clinical_note|denial_reason|authorization|password|ssn|date_of_birth|dob|jwt_secret|member_id"
)
# Quoted value, or unquoted run until the next known field / end.
_SENSITIVE_FIELD = re.compile(
    rf"(?i)([\"']?(?:{_FIELD_NAMES})[\"']?\s*[:=]\s*)"
    rf"([\"'](?:\\.|[^\"'\\])*[\"']|.+?)"
    rf"(?=,\s*[\"']?(?:{_FIELD_NAMES})|"
    rf"\s+[\"']?(?:{_FIELD_NAMES})[\"']?\s*[:=]|\s*$)"
)


def redact_text(text: str) -> str:
    out = _EMAIL.sub(REDACTED, text)
    out = _JWT.sub(REDACTED, out)
    out = _BEARER.sub(f"Bearer {REDACTED}", out)
    out = _SENSITIVE_FIELD.sub(rf"\1{REDACTED}", out)
    return out


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_mapped(key, item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        redacted = [_redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(redacted)
        return redacted
    return value


_SENSITIVE_KEYS = frozenset(
    {
        "clinical_note",
        "denial_reason",
        "authorization",
        "password",
        "ssn",
        "date_of_birth",
        "dob",
        "jwt_secret",
        "member_id",
    }
)


def _redact_mapped(key: Any, value: Any) -> Any:
    key_text = str(key).lower()
    if key_text in _SENSITIVE_KEYS:
        return REDACTED
    return _redact_value(value)


class PiiRedactingFilter(logging.Filter):
    """Mutates the record in place so every handler sees redacted text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = _redact_value(record.args)
        return True


_filter_installed = False


def install_pii_log_filter() -> None:
    """Attach once on the root logger (covers child loggers that propagate)."""
    global _filter_installed
    if _filter_installed:
        return
    root = logging.getLogger()
    pii_filter = PiiRedactingFilter()
    root.addFilter(pii_filter)
    _filter_installed = True
