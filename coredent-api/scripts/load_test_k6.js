/**
 * k6 Load Test for CoreDent API
 * Industry-standard load testing with k6
 *
 * Installation:
 *   k6 install
 *   k6 run scripts/load_test_k6.js
 *
 * Or with Docker:
 *   docker run -i loadimpact/k6 run - < scripts/load_test_k6.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const latencyTrend = new Trend('latency');

// Test configuration
export const options = {
  stages: [
    { duration: '30s', target: 20 },   // Ramp up
    { duration: '1m', target: 50 },    // Steady load
    { duration: '30s', target: 100 },  // Stress test
    { duration: '1m', target: 100 },  // Sustain
    { duration: '30s', target: 0 },   // Cool down
  ],
  thresholds: {
    'http_req_duration': ['p(99)<500'],  // P99 < 500ms
    'http_req_failed': ['rate<0.01'],    // Error rate < 1%
    'errors': ['rate<0.05'],             // 5% max error rate
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const API_BASE = `${BASE_URL}/api/v1`;

export function setup() {
  const res = http.post(`${API_BASE}/auth/login`, JSON.stringify({
    email: __ENV.TEST_EMAIL || 'admin@coredent.com',
    password: __ENV.TEST_PASSWORD || 'SecurePass123!',
  }), {
    headers: { 'Content-Type': 'application/json' },
  });

  const data = res.json();
  return { token: data.access_token };
}

export default function(data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // Health check
  group('Health', () => {
    const res = http.get(`${BASE_URL}/health`);
    check(res, { 'health is 200': (r) => r.status === 200 });
  });

  // Authentication endpoints
  group('Auth', () => {
    const res = http.get(`${API_BASE}/auth/me`, { headers });
    check(res, { 'me is 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  // Patients endpoints
  group('Patients', () => {
    const res = http.get(`${API_BASE}/patients?page=1&limit=20`, { headers });
    const latency = latencyTrend.add(res.timings.duration);
    check(res, {
      'patients is 200': (r) => r.status === 200,
      'has data': (r) => r.json('data') !== undefined,
    });
    errorRate.add(res.status !== 200);
  });

  // Appointments endpoints
  group('Appointments', () => {
    const res = http.get(`${API_BASE}/appointments?page=1&limit=20`, { headers });
    latencyTrend.add(res.timings.duration);
    check(res, {
      'appointments is 200': (r) => r.status === 200,
    });
    errorRate.add(res.status !== 200);
  });

  // Billing endpoints
  group('Billing', () => {
    const res = http.get(`${API_BASE}/billing/invoices?page=1&limit=20`, { headers });
    latencyTrend.add(res.timings.duration);
    check(res, { 'billing is 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  // Reports endpoints
  group('Reports', () => {
    const res = http.get(`${API_BASE}/reports/production?start_date=2026-01-01&end_date=2026-12-31`, { headers });
    latencyTrend.add(res.timings.duration);
    check(res, { 'reports is 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  // Settings endpoints
  group('Settings', () => {
    const res = http.get(`${API_BASE}/settings`, { headers });
    latencyTrend.add(res.timings.duration);
    check(res, { 'settings is 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  });

  sleep(1);
}

export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'load_test_results.json': JSON.stringify(data, null, 2),
  };
}

function textSummary(data, options) {
  const { metrics } = data;
  const rps = metrics.http_reqs.values.count / (metrics.http_req_duration.values.tt > 1000 ? metrics.http_req_duration.values.tt / 1000 : 1);

  return `
============================================================
CoreDent API Load Test Summary
============================================================
Duration: ${(metrics.http_req_duration.values.tt / 1000).toFixed(2)}s
Total Requests: ${metrics.http_reqs.values.count.toFixed(0)}
Requests/sec: ${rps.toFixed(2)}

Latency (ms):
  Min:    ${metrics.http_req_duration.values.min.toFixed(2)}
  Mean:   ${metrics.http_req_duration.values.median.toFixed(2)}
  P95:    ${metrics.http_req_duration.values['p(95)'].toFixed(2)}
  P99:    ${metrics.http_req_duration.values['p(99)'].toFixed(2)}
  Max:    ${metrics.http_req_duration.values.max.toFixed(2)}

Error Rate: ${(metrics.http_req_failed.values.rate * 100).toFixed(2)}%
============================================================
  `.trim();
}
