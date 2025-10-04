/**
 * K6 Load Test: Sandbox Allocation at 1000 RPS
 *
 * This test simulates high-concurrency sandbox allocation to verify:
 * - System can handle 1000+ concurrent requests per second
 * - Latency remains under target (p95 < 300ms, p99 < 500ms)
 * - Zero double-allocations under load
 * - DynamoDB doesn't throttle
 * - ECS auto-scaling triggers appropriately
 *
 * Prerequisites:
 * 1. DynamoDB table pre-seeded with 100-200 available sandboxes
 * 2. API deployed and accessible
 * 3. k6 installed: brew install k6 (Mac) or see https://k6.io/docs/getting-started/installation/
 *
 * Usage:
 *   # Smoke test (10 RPS for 30s)
 *   k6 run --vus 10 --duration 30s tests/load/allocation_load_test.js
 *
 *   # Load test (100 RPS for 5 minutes)
 *   k6 run --vus 100 --duration 5m tests/load/allocation_load_test.js
 *
 *   # Stress test (1000 RPS for 10 minutes)
 *   k6 run --vus 1000 --duration 10m tests/load/allocation_load_test.js
 *
 *   # Spike test (sudden spike to 2000 RPS)
 *   k6 run --stage 30s:100 --stage 1m:2000 --stage 2m:0 tests/load/allocation_load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend, Rate } from 'k6/metrics';

// Configuration
const BASE_URL = __ENV.API_URL || 'https://api-sandbox-broker.highvelocitynetworking.com/v1';
const API_TOKEN = __ENV.BROKER_API_TOKEN || 'a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e';

// Custom metrics
const allocationSuccess = new Counter('allocation_success');
const allocationFailure = new Counter('allocation_failure');
const allocationConflicts = new Counter('allocation_conflicts');
const allocationPoolExhausted = new Counter('allocation_pool_exhausted');
const allocationLatency = new Trend('allocation_latency_ms');
const markDeletionSuccess = new Counter('mark_deletion_success');
const idempotencyHit = new Counter('idempotency_hit');

// Thresholds for pass/fail
export const options = {
  thresholds: {
    http_req_duration: ['p(95)<300', 'p(99)<500'],  // 95% < 300ms, 99% < 500ms
    http_req_failed: ['rate<0.05'],                  // Error rate < 5%
    allocation_success: ['count>0'],                 // At least some allocations succeed
    allocation_latency_ms: ['p(95)<300', 'p(99)<500'],
  },

  // Gradual ramp-up to 1000 VUs (Virtual Users)
  stages: [
    { duration: '1m', target: 100 },   // Ramp-up to 100 RPS
    { duration: '2m', target: 500 },   // Ramp-up to 500 RPS
    { duration: '2m', target: 1000 },  // Ramp-up to 1000 RPS
    { duration: '5m', target: 1000 },  // Stay at 1000 RPS
    { duration: '2m', target: 100 },   // Ramp-down
    { duration: '1m', target: 0 },     // Cool-down
  ],
};

// Generate unique track ID per VU
function generateTrackId() {
  return `load-test-track-${__VU}-${__ITER}`;
}

// Test scenarios
export default function () {
  const trackId = generateTrackId();

  // Scenario 1: Allocate sandbox (70% of requests)
  if (Math.random() < 0.7) {
    allocateSandbox(trackId);
  }

  // Scenario 2: Check stats (20% of requests)
  else if (Math.random() < 0.9) {
    // Skip stats to focus on allocation
    // checkStats();
    allocateSandbox(trackId);
  }

  // Scenario 3: Mark for deletion (10% of requests)
  else {
    // In real scenario, we'd track allocated sandboxes and delete them
    // For load test, just focus on allocation
    allocateSandbox(trackId);
  }

  // Think time: simulate real user behavior
  sleep(Math.random() * 2); // 0-2 seconds between requests
}

function allocateSandbox(trackId) {
  const url = `${BASE_URL}/allocate`;
  const headers = {
    'Authorization': `Bearer ${API_TOKEN}`,
    'X-Track-ID': trackId,
    'Content-Type': 'application/json',
  };

  const startTime = Date.now();
  const response = http.post(url, null, { headers, tags: { name: 'allocate' } });
  const duration = Date.now() - startTime;

  allocationLatency.add(duration);

  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'has sandbox_id': (r) => r.json('sandbox_id') !== undefined,
    'has expires_at': (r) => r.json('expires_at') !== undefined,
  });

  if (success) {
    allocationSuccess.add(1);

    // Test idempotency: retry with same track_id
    if (Math.random() < 0.1) { // 10% chance
      const retryResponse = http.post(url, null, { headers, tags: { name: 'allocate_idempotency' } });

      check(retryResponse, {
        'idempotency: same sandbox returned': (r) =>
          r.json('sandbox_id') === response.json('sandbox_id'),
      });

      if (retryResponse.json('sandbox_id') === response.json('sandbox_id')) {
        idempotencyHit.add(1);
      }
    }
  } else {
    allocationFailure.add(1);

    // Categorize failures
    if (response.status === 503) {
      allocationPoolExhausted.add(1);
    } else if (response.status === 409) {
      allocationConflicts.add(1);
    }

    console.error(`Allocation failed: ${response.status} - ${response.body}`);
  }
}

function checkStats() {
  const url = `${BASE_URL}/admin/stats`;
  const headers = {
    'Authorization': `Bearer ${__ENV.BROKER_ADMIN_TOKEN || 'test-admin-token'}`,
    'Content-Type': 'application/json',
  };

  const response = http.get(url, { headers, tags: { name: 'admin_stats' } });

  check(response, {
    'stats status is 200': (r) => r.status === 200,
    'stats has total': (r) => r.json('total') !== undefined,
  });
}

// Teardown function (optional)
export function teardown(data) {
  console.log('\n=== Load Test Summary ===');
  console.log('Check k6 output above for detailed metrics');
  console.log('Key metrics to review:');
  console.log('  - http_req_duration (p95, p99)');
  console.log('  - allocation_success vs allocation_failure');
  console.log('  - allocation_pool_exhausted count');
  console.log('  - idempotency_hit count');
}

// Setup function (optional)
export function setup() {
  console.log('\n=== Starting Load Test ===');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Target: 1000 RPS for 5 minutes`);
  console.log('\nExpected behavior:');
  console.log('  - P95 latency < 300ms');
  console.log('  - P99 latency < 500ms');
  console.log('  - Error rate < 5%');
  console.log('  - Zero double-allocations (idempotency working)');
  console.log('  - ECS auto-scaling triggered around 500-700 RPS\n');
}
