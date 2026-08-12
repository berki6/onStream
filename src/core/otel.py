"""Optional OpenTelemetry tracing setup."""

from __future__ import annotations

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_initialized = False


def setup_tracing(service_name: str = "onstream") -> bool:
    """
    Initialize OTel tracing when ``OTEL_ENABLED`` is true.

    Soft-fails (returns False) if packages or endpoint are missing.
    """
    global _initialized
    if _initialized:
        return True
    if not settings.OTEL_ENABLED:
        return False

    endpoint = (settings.OTEL_EXPORTER_OTLP_ENDPOINT or "").strip()
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except Exception as exp_exc:
                logger.warning("OTel OTLP exporter unavailable: %s", exp_exc)

        trace.set_tracer_provider(provider)

        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            # Caller may instrument app separately; keep import warm
            _ = FastAPIInstrumentor
        except Exception:
            pass

        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
        except Exception as httpx_exc:
            logger.debug("httpx instrumentation skipped: %s", httpx_exc)

        _initialized = True
        logger.info("OpenTelemetry tracing enabled (service=%s)", service_name)
        return True
    except Exception as exc:
        logger.warning("Failed to setup OpenTelemetry: %s", exc)
        return False


def instrument_fastapi(app) -> None:
    """Instrument a FastAPI app if OTel is enabled."""
    if not settings.OTEL_ENABLED:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("FastAPI OTel instrumentation failed: %s", exc)
