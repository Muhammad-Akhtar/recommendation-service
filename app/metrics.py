"""Prometheus metrics for the recommendation API (Task 21)."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

RECOMMENDATION_REQUESTS = Counter(
    "recommendation_requests_total",
    "Total recommendation HTTP requests handled",
    ["source", "model_version"],
)

RECOMMENDATION_LATENCY = Histogram(
    "recommendation_latency_seconds",
    "Recommendation endpoint latency in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REDIS_HITS = Counter(
    "redis_hits_total",
    "Redis recommendation-cache hits",
)

REDIS_MISSES = Counter(
    "redis_misses_total",
    "Redis recommendation-cache misses",
)

REDIS_FAILURES = Counter(
    "redis_failures_total",
    "Redis errors during recommendation serving",
    ["operation"],
)

POSTGRES_FAILURES = Counter(
    "postgres_failures_total",
    "PostgreSQL errors during recommendation serving",
    ["operation"],
)

MODEL_PREDICTIONS = Counter(
    "model_predictions_total",
    "Model predict() invocations",
    ["model_version"],
)

MODEL_PREDICTION_ERRORS = Counter(
    "model_prediction_errors_total",
    "Model predict() failures",
    ["model_version"],
)

MODEL_PREDICTION_LATENCY = Histogram(
    "model_prediction_latency_seconds",
    "Time spent inside model.predict()",
    ["model_version"],
    buckets=(0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

RECOMMENDATION_COUNT = Histogram(
    "recommendation_count",
    "Number of recommendation IDs returned per model prediction",
    ["model_version"],
    buckets=(1, 2, 3, 4, 5, 10, 20),
)

RECOMMENDATIONS_SERVED = Counter(
    "recommendations_served_total",
    "Recommendation items shown to users (impressions)",
    ["model_version"],
)

RECOMMENDATIONS_CLICKED = Counter(
    "recommendations_clicked_total",
    "Clicks on items previously returned as recommendations",
    ["model_version"],
)
