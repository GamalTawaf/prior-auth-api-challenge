from __future__ import annotations

import logging

from app.log_pii import (
    REDACTED,
    PiiRedactingFilter,
    _redact_value,
    install_pii_log_filter,
    redact_text,
)


def test_redact_text_masks_email_jwt_bearer_and_fields():
    raw = (
        "user=office@riverside.example.com "
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.sig "
        'clinical_note="patient has diabetes" '
        "denial_reason=Not medically necessary "
        "member_id=22222222-2222-2222-2222-222222222222"
    )
    out = redact_text(raw)
    assert "office@riverside.example.com" not in out
    assert "eyJhbGciOiJIUzI1NiJ9" not in out
    assert "patient has diabetes" not in out
    assert "Not medically necessary" not in out
    assert "22222222-2222-2222-2222-222222222222" not in out
    assert REDACTED in out


def test_filter_redacts_msg_and_args(caplog):
    logger = logging.getLogger("test.pii.filter")
    logger.addFilter(PiiRedactingFilter())
    logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="test.pii.filter"):
        logger.info("note=%s email=%s", 'clinical_note="secret chart"', "a@b.co")
        logger.info("payload %s", {"denial_reason": "too expensive", "ok": "keep"})
        logger.info("list %s", ["user@example.com"])
        logger.info("tuple %s", ("password=hunter2",))
    text = caplog.text
    assert "secret chart" not in text
    assert "a@b.co" not in text
    assert "too expensive" not in text
    assert "hunter2" not in text
    assert "user@example.com" not in text
    assert "keep" in text
    assert REDACTED in text


def test_filter_non_string_msg_and_empty_args():
    record = logging.LogRecord(
        name="test.pii",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=42,
        args=(),
        exc_info=None,
    )
    assert PiiRedactingFilter().filter(record) is True
    assert record.msg == 42


def test_redact_value_passthrough_and_containers():
    assert _redact_value(7) == 7
    assert _redact_value(("a@b.co",)) == (REDACTED,)
    assert _redact_value(["a@b.co"]) == [REDACTED]


def test_install_pii_log_filter_idempotent():
    install_pii_log_filter()
    root = logging.getLogger()
    before = sum(1 for f in root.filters if isinstance(f, PiiRedactingFilter))
    install_pii_log_filter()
    after = sum(1 for f in root.filters if isinstance(f, PiiRedactingFilter))
    assert after == before
    assert before >= 1
