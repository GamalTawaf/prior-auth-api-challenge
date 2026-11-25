from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.config import settings

_request_counter = None
_claim_conflict_counter = None
_intake_rejection_counter = None


def setup_telemetry(app: FastAPI) -> None:
    global _request_counter, _claim_conflict_counter, _intake_rejection_counter

    resource = Resource.create({"service.name": settings.otel_service_name})
    tracer_provider = TracerProvider(resource=resource)
    # ponytail: console exporter when OTLP endpoint unset; swap for prod collector
    import os

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    else:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter())

    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    LoggingInstrumentor().instrument(set_logging_format=True)
    FastAPIInstrumentor.instrument_app(app)

    meter = metrics.get_meter("prior-auth-api")
    _request_counter = meter.create_counter("http_requests", unit="1")
    _claim_conflict_counter = meter.create_counter("claim_conflicts", unit="1")
    _intake_rejection_counter = meter.create_counter("intake_rejections", unit="1")
    logging.getLogger(__name__).info("telemetry configured")


def record_claim_conflict() -> None:
    if _claim_conflict_counter is not None:
        _claim_conflict_counter.add(1)


def record_intake_rejection() -> None:
    if _intake_rejection_counter is not None:
        _intake_rejection_counter.add(1)
