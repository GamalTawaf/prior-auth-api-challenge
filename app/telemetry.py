from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
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
    # ponytail: console when OTLP unset; Compose sets endpoint → grafana/otel-lgtm
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        span_exporter = OTLPSpanExporter()
        metric_exporter = OTLPMetricExporter()
        log_exporter = OTLPLogExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        logger_provider = LoggerProvider(resource=resource)
        log_processor = BatchLogRecordProcessor(log_exporter)
        logger_provider.add_log_record_processor(log_processor)
        set_logger_provider(logger_provider)
        otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logging.getLogger().addHandler(otel_handler)
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
