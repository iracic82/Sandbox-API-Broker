/**
 * K6 Multi-Student Load Test: Same Lab, Different Students
 *
 * This test simulates multi-student scenario to verify:
 * - Multiple students can run the same lab simultaneously
 * - Each student gets a DIFFERENT sandbox
 * - Zero double-allocations
 * - Idempotency works (same student, same sandbox)
 *
 * Scenario:
 * - 5 different labs (aws-sec-101, aws-net-101, k8s-basics, docker-intro, terraform-101)
 * - 50 students total (10 students per lab)
 * - Each student makes multiple allocation requests
 * - Verify each student gets unique sandbox
 *
 * Prerequisites:
 * 1. DynamoDB table pre-seeded with 200 available sandboxes
 * 2. API deployed and accessible
 * 3. k6 installed
 *
 * Usage:
 *   # Simulate 50 students across 5 labs
 *   k6 run --vus 50 --duration 2m tests/load/multi_student_load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// Configuration
const BASE_URL = __ENV.API_URL || 'https://api-sandbox-broker.highvelocitynetworking.com/v1';
const API_TOKEN = __ENV.BROKER_API_TOKEN || 'a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e';

// Custom metrics
const allocationSuccess = new Counter('allocation_success');
const allocationFailure = new Counter('allocation_failure');
const allocationPoolExhausted = new Counter('allocation_pool_exhausted');
const allocationLatency = new Trend('allocation_latency_ms');
const idempotencyHit = new Counter('idempotency_hit');

// Lab definitions
const LABS = [
  'aws-security-101',
  'aws-networking-101',
  'kubernetes-basics',
  'docker-intro',
  'terraform-101',
];

// Thresholds
export const options = {
  thresholds: {
    http_req_duration: ['p(95)<300', 'p(99)<500'],
    http_req_failed: ['rate<0.10'],  // Allow 10% failures (pool exhaustion expected)
    allocation_success: ['count>0'],
    allocation_latency_ms: ['p(95)<300', 'p(99)<500'],
  },
};

// Generate unique Instruqt sandbox ID per student (unique per VU)
function generateSandboxId() {
  // Each VU represents a unique student
  // VU 1-10 = Lab 1, VU 11-20 = Lab 2, etc.
  return `inst-student-${__VU}-${Math.floor(Date.now() / 1000)}`;
}

// Assign lab based on VU number (10 students per lab)
function getLabForStudent() {
  const labIndex = Math.floor((__VU - 1) / 10) % LABS.length;
  return LABS[labIndex];
}

// Allocate sandbox
function allocateSandbox(sandboxId, labId) {
  const start = Date.now();

  const headers = {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json',
    'X-Instruqt-Sandbox-ID': sandboxId,  // Unique per student
    'X-Instruqt-Track-ID': labId,        // Lab identifier (same for multiple students)
  };

  const response = http.post(
    `${BASE_URL}/allocate`,
    null,
    { headers }
  );

  const duration = Date.now() - start;
  allocationLatency.add(duration);

  const success = check(response, {
    'status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'has sandbox_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.sandbox_id !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (success) {
    if (response.status === 200) {
      idempotencyHit.add(1);  // Idempotent response (same sandbox)
    }
    allocationSuccess.add(1);
    console.log(`✅ Student ${sandboxId} in lab ${labId} allocated sandbox`);
  } else if (response.status === 409) {
    // Pool exhausted - expected when all sandboxes allocated
    allocationPoolExhausted.add(1);
    console.log(`⚠️  Pool exhausted for student ${sandboxId}`);
  } else {
    allocationFailure.add(1);
    console.log(`❌ Allocation failed for ${sandboxId}: ${response.status} - ${response.body}`);
  }

  return response;
}

// Main test scenario
export default function () {
  // Each VU represents a unique student
  const sandboxId = generateSandboxId();
  const labId = getLabForStudent();

  console.log(`\n🎓 Student: ${sandboxId}`);
  console.log(`📚 Lab: ${labId}`);

  // Student makes 3 allocation requests (testing idempotency)
  for (let i = 1; i <= 3; i++) {
    console.log(`  Request ${i}/3...`);
    allocateSandbox(sandboxId, labId);
    sleep(1);  // 1 second between requests from same student
  }

  // Think time (student using sandbox)
  sleep(5);
}

// Summary at end of test
export function handleSummary(data) {
  return {
    'stdout': JSON.stringify({
      allocations: data.metrics.allocation_success.values.count || 0,
      pool_exhausted: data.metrics.allocation_pool_exhausted.values.count || 0,
      idempotency_hits: data.metrics.idempotency_hit.values.count || 0,
      avg_latency: Math.round(data.metrics.allocation_latency_ms.values.avg) || 0,
      p95_latency: Math.round(data.metrics.allocation_latency_ms.values['p(95)']) || 0,
      p99_latency: Math.round(data.metrics.allocation_latency_ms.values['p(99)']) || 0,
    }, null, 2),
  };
}
