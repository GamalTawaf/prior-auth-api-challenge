"""OTLP logging attachment for Grafana Loki (root + uvicorn + SQLAlchemy)."""

from __future__ import annotations

import logging

from app.telemetry import attach_otlp_logging_handler
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk.resources import Resource


def test_attach_otlp_logging_handler_covers_api_and_db_loggers():
    provider = LoggerProvider(resource=Resource.create({"service.name": "test-logs"}))
    first = attach_otlp_logging_handler(provider, level=logging.INFO)
    second = attach_otlp_logging_handler(provider, level=logging.INFO)
    assert isinstance(first, LoggingHandler)
    assert isinstance(second, LoggingHandler)

    root = logging.getLogger()
    assert root.level == logging.INFO
    access = logging.getLogger("uvicorn.access")
    assert access.level == logging.INFO
    otel_on_access = [h for h in access.handlers if isinstance(h, LoggingHandler)]
    assert len(otel_on_access) == 1

    engine_log = logging.getLogger("sqlalchemy.engine")
    assert engine_log.level == logging.INFO
    pool_log = logging.getLogger("sqlalchemy.pool")
    assert pool_log.level == logging.INFO


def test_attach_otlp_logging_handler_respects_level(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    provider = LoggerProvider(resource=Resource.create({"service.name": "test-logs-warn"}))
    attach_otlp_logging_handler(provider)
    assert logging.getLogger().level == logging.WARNING
    assert logging.getLogger("uvicorn.access").level == logging.WARNING
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING


def test_resolve_log_level_falls_back_on_invalid(monkeypatch):
    from app.telemetry import _resolve_log_level

    monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")
    assert _resolve_log_level() == logging.INFO
