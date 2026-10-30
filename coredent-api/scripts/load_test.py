"""
Load Testing Suite for CoreDent API
Tests API performance under realistic SaaS load

Usage:
    # Install k6
    pip install k6

    # Run tests
    k6 run scripts/load_test.js

    # Or with environment variables
    API_URL=https://your-api.com k6 run scripts/load_test.js
"""

import http.client
import json
import time
import random
import threading
import statistics
from datetime import datetime
from typing import Dict, List, Any


class LoadTestConfig:
    BASE_URL = "http://localhost:8000"
    API_V1 = "/api/v1"
    DURATION_SECONDS = 60
    VUS = 50
    THRESHOLD_RPS = 100
    THRESHOLD_P99_MS = 500


class LoadTestMetrics:
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.latencies: List[float] = []
        self.status_codes: Dict[int, int] = {}
        self.start_time = None
        self.end_time = None
        self._lock = threading.Lock()

    def record(self, latency_ms: float, status_code: int):
        with self._lock:
            self.request_count += 1
            if status_code >= 400:
                self.error_count += 1
            self.latencies.append(latency_ms)
            self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1

    def report(self) -> Dict[str, Any]:
        with self._lock:
            duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
            latencies = sorted(self.latencies)

            return {
                "summary": {
                    "duration_seconds": round(duration, 2),
                    "total_requests": self.request_count,
                    "errors": self.error_count,
                    "error_rate": round(self.error_count / max(self.request_count, 1) * 100, 2),
                    "requests_per_second": round(self.request_count / max(duration, 1), 2),
                },
                "latency": {
                    "min_ms": round(min(latencies), 2) if latencies else 0,
                    "max_ms": round(max(latencies), 2) if latencies else 0,
                    "mean_ms": round(statistics.mean(latencies), 2) if latencies else 0,
                    "median_ms": round(statistics.median(latencies), 2) if latencies else 0,
                    "p95_ms": round(latencies[int(len(latencies) * 0.95)] if latencies else 0, 2),
                    "p99_ms": round(latencies[int(len(latencies) * 0.99)] if latencies else 0, 2),
                },
                "status_codes": self.status_codes
            }


def make_request(method: str, path: str, headers: Dict = None, body: str = None) -> tuple:
    start = time.time()
    try:
        conn = http.client.HTTPConnection("localhost", 8000, timeout=30)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        latency = (time.time() - start) * 1000
        return latency, response.status, response.read()
    except Exception as e:
        latency = (time.time() - start) * 1000
        return latency, 0, str(e).encode()
    finally:
        conn.close()


def get_auth_token() -> str:
    import os
    if os.path.exists(".test_token"):
        return open(".test_token").read().strip()

    latency, status, body = make_request(
        "POST",
        "/api/v1/auth/login",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "email": "test@coredent.com",
            "password": "TestPassword123!"
        })
    )
    if status == 200:
        data = json.loads(body)
        return data.get("access_token", "")
    return ""


def simulate_user(metrics: LoadTestMetrics, vu_id: int):
    auth_token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    endpoints = [
        ("/api/v1/patients", "GET", None),
        ("/api/v1/appointments", "GET", None),
        ("/api/v1/billing/invoices", "GET", None),
        ("/api/v1/reports/production", "GET", None),
        ("/api/v1/settings", "GET", None),
    ]

    operations = [
        ("/api/v1/patients", "POST", {"first_name": "Load", "last_name": f"Test{vu_id}", "email": f"load{vu_id}@test.com", "date_of_birth": "1990-01-01"}),
        ("/api/v1/appointments", "POST", {"patient_id": "00000000-0000-0000-0000-000000000001", "start_time": "2026-06-01T10:00:00Z", "end_time": "2026-06-01T11:00:00Z", "appointment_type": "checkup", "duration": 60}),
    ]

    start_time = time.time()
    while time.time() - start_time < LoadTestConfig.DURATION_SECONDS:
        if random.random() < 0.9:
            endpoint, method, _ = random.choice(endpoints)
            path = endpoint + "?page=1&limit=20"
        else:
            endpoint, method, body = random.choice(operations)
            path = endpoint
            body = json.dumps(body)
        latency, status, _ = make_request(method, path, headers, body if method == "POST" else None)
        metrics.record(latency, status)
        time.sleep(random.uniform(0.01, 0.1))


def run_load_test():
    print("=" * 60)
    print("CoreDent API Load Test")
    print("=" * 60)
    print(f"Duration: {LoadTestConfig.DURATION_SECONDS}s")
    print(f"Virtual Users: {LoadTestConfig.VUS}")
    print(f"Target: {LoadTestConfig.THRESHOLD_RPS} RPS, P99 < {LoadTestConfig.THRESHOLD_P99_MS}ms")
    print("=" * 60)

    metrics = LoadTestMetrics()
    metrics.start_time = datetime.now()

    threads = []
    print(f"\nStarting {LoadTestConfig.VUS} virtual users...")
    for vu in range(LoadTestConfig.VUS):
        t = threading.Thread(target=simulate_user, args=(metrics, vu))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    metrics.end_time = datetime.now()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    report = metrics.report()
    print(f"\nRequests: {report['summary']['total_requests']}")
    print(f"Duration: {report['summary']['duration_seconds']}s")
    print(f"RPS: {report['summary']['requests_per_second']}")
    print(f"Errors: {report['summary']['errors']} ({report['summary']['error_rate']}%)")

    print("\nLatency (ms):")
    print(f"  Min: {report['latency']['min_ms']}")
    print(f"  Mean: {report['latency']['mean_ms']}")
    print(f"  Median: {report['latency']['median_ms']}")
    print(f"  P95: {report['latency']['p95_ms']}")
    print(f"  P99: {report['latency']['p99_ms']}")
    print(f"  Max: {report['latency']['max_ms']}")

    print("\nStatus Codes:")
    for code, count in sorted(report['status_codes'].items()):
        print(f"  {code}: {count}")

    print("\n" + "=" * 60)
    passed = (
        report['summary']['requests_per_second'] >= LoadTestConfig.THRESHOLD_RPS and
        report['latency']['p99_ms'] <= LoadTestConfig.THRESHOLD_P99_MS
    )
    print(f"RESULT: {'PASS ✅' if passed else 'FAIL ❌'}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    run_load_test()
