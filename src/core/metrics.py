"""Prometheus metrics helpers."""

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "onstream_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "onstream_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
JOB_ENQUEUED = Counter(
    "onstream_jobs_enqueued_total",
    "Video jobs enqueued",
)
JOB_PROCESSED = Counter(
    "onstream_jobs_processed_total",
    "Video jobs processed",
    ["status"],
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
