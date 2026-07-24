"""Prometheus metrics helpers."""

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

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

LIVE_STREAMS_ACTIVE = Gauge(
    "onstream_live_streams_active",
    "Number of streams currently marked live",
)
LIVE_STREAMS_STALE_TOTAL = Counter(
    "onstream_live_streams_stale_total",
    "Live streams marked idle/ended due to health checks",
    ["reason"],
)
LIVE_PLAYLIST_AGE = Histogram(
    "onstream_live_playlist_age_seconds",
    "Age of live HLS playlist files in seconds",
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300),
)
LIVE_ABR_ACTIVE = Gauge(
    "onstream_live_abr_active",
    "Number of live ABR FFmpeg processes running",
)
LIVE_AUTH_TOTAL = Counter(
    "onstream_live_auth_total",
    "MediaMTX auth webhook outcomes",
    ["action", "result"],
)
PLAYBACK_RESPONSES = Counter(
    "onstream_playback_responses_total",
    "HLS playback responses served",
    ["kind", "live"],
)
API_ERRORS = Counter(
    "onstream_api_errors_total",
    "Structured API / application errors",
    ["code", "http_status"],
)
QOE_PLAYLIST_AGE = Histogram(
    "onstream_qoe_playlist_age_seconds",
    "QoE canary observed playlist age",
    buckets=(1, 2, 5, 10, 20, 30, 60, 120),
)
QOE_FETCH_LATENCY = Histogram(
    "onstream_qoe_fetch_latency_seconds",
    "QoE canary local playlist read latency",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
