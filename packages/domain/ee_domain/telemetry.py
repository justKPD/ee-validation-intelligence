"""Minimal OpenTelemetry setup shared by services.

`EE_OTEL_EXPORTER`: `none` (default), `console`, or `otlp` (needs
opentelemetry-exporter-otlp and OTEL_EXPORTER_OTLP_ENDPOINT).
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

_configured = False


def configure_tracing(service_name: str) -> TracerProvider:
    global _configured
    provider = trace.get_tracer_provider()
    if _configured and isinstance(provider, TracerProvider):
        return provider
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter: SpanExporter | None = None
    mode = os.environ.get("EE_OTEL_EXPORTER", "none").lower()
    if mode == "console":
        exporter = ConsoleSpanExporter()
    elif mode == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _configured = True
    return provider


def tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
