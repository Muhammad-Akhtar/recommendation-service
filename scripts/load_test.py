"""
Task 24 — simple HTTP load test (no Locust required).

Examples (PowerShell):

  # Against port-forwarded Kubernetes Service
  python scripts/load_test.py --url http://localhost:8000/health --concurrency 20 --requests 500

  # Push CPU for HPA demos
  python scripts/load_test.py --url "http://localhost:8000/demo/cpu-burn?duration_ms=80" --concurrency 40 --requests 2000

Reports: RPS, avg latency, p95, error count.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx


async def _worker(
    client: httpx.AsyncClient,
    url: str,
    n: int,
    latencies: list[float],
    statuses: Counter[int],
    errors: list[str],
) -> None:
    for _ in range(n):
        started = time.perf_counter()
        try:
            response = await client.get(url)
            latencies.append(time.perf_counter() - started)
            statuses[response.status_code] += 1
        except Exception as exc:  # noqa: BLE001 — surface any transport failure
            latencies.append(time.perf_counter() - started)
            errors.append(str(exc))
            statuses[0] += 1


async def run_load_test(
    *,
    url: str,
    concurrency: int,
    requests: int,
    timeout: float,
) -> None:
    if concurrency < 1 or requests < 1:
        raise SystemExit("concurrency and requests must be >= 1")

    base, rem = divmod(requests, concurrency)
    per_worker = [base + (1 if i < rem else 0) for i in range(concurrency)]

    latencies: list[float] = []
    statuses: Counter[int] = Counter()
    errors: list[str] = []

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        wall_start = time.perf_counter()
        await asyncio.gather(
            *[
                _worker(client, url, count, latencies, statuses, errors)
                for count in per_worker
                if count > 0
            ]
        )
        wall = time.perf_counter() - wall_start

    ok = sum(c for code, c in statuses.items() if 200 <= code < 400)
    err_count = requests - ok
    lat_ms = [x * 1000 for x in latencies]
    avg = statistics.mean(lat_ms) if lat_ms else 0.0
    p95 = (
        statistics.quantiles(lat_ms, n=20)[18]
        if len(lat_ms) >= 20
        else (max(lat_ms) if lat_ms else 0.0)
    )

    print("=== Load test results ===")
    print(f"url:          {url}")
    print(f"requests:     {requests}")
    print(f"concurrency:  {concurrency}")
    print(f"wall_seconds: {wall:.3f}")
    print(f"rps:          {requests / wall:.1f}" if wall > 0 else "rps:          n/a")
    print(f"ok:           {ok}")
    print(f"errors:       {err_count}")
    print(f"avg_ms:       {avg:.2f}")
    print(f"p95_ms:       {p95:.2f}")
    print(f"status_codes: {dict(statuses)}")
    if errors:
        print(f"sample_error: {errors[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Task 24 HTTP load test")
    parser.add_argument("--url", default="http://localhost:8000/health")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    asyncio.run(
        run_load_test(
            url=args.url,
            concurrency=args.concurrency,
            requests=args.requests,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
