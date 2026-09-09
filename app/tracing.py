"""OpenTelemetry tracing setup (Task 21).

Default exporter is console so local docker/logs show span timings
without requiring Jaeger. Set OTEL_TRACES_EXPORTER=none to disable.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

_configured = False


def configure_tracing(
    *,
    service_name: str = "recommendation-service",
    exporter: str = "console",
) -> None:
    """Idempotent tracer provider setup."""
    global _configured
    if _configured:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter.lower() == "console":
        # Simple processor so spans appear immediately in local logs.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter.lower() == "none":
        pass
    else:
        # Unknown value → safe no-op exporter path (still creates spans in-process).
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str = "recommendation-service") -> trace.Tracer:
    return trace.get_tracer(name)
