#!/usr/bin/env python3
"""Test Phase 2 admin endpoints."""

import requests
import json

BASE_URL = "http://localhost:8080/v1/admin"
ADMIN_TOKEN = "admin-secret-token-12345"

headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

print("=" * 60)
print("TESTING ADMIN ENDPOINTS")
print("=" * 60)

# Test 1: List all sandboxes
print("\nTest 1: List All Sandboxes")
r = requests.get(f"{BASE_URL}/sandboxes", headers=headers)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  Count: {len(data.get('sandboxes', []))}")
    for sb in data.get("sandboxes", [])[:3]:
        print(f"    - {sb['sandbox_id']}: {sb['status']}")
else:
    print(f"  Error: {r.text}")

# Test 2: Filter by status
print("\nTest 2: Filter by Status (available)")
r = requests.get(f"{BASE_URL}/sandboxes?status=available", headers=headers)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  Available: {len(data.get('sandboxes', []))}")
else:
    print(f"  Error: {r.text}")

# Test 3: Get stats
print("\nTest 3: Get Stats")
r = requests.get(f"{BASE_URL}/stats", headers=headers)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    print(f"  Stats: {r.json()}")
else:
    print(f"  Error: {r.text}")

# Test 4: Trigger sync
print("\nTest 4: Trigger Sync")
r = requests.post(f"{BASE_URL}/sync", headers=headers)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    print(f"  Result: {r.json()}")
else:
    print(f"  Error: {r.text}")

# Test 5: Trigger cleanup
print("\nTest 5: Trigger Cleanup")
r = requests.post(f"{BASE_URL}/cleanup", headers=headers)
print(f"  Status: {r.status_code}")
if r.status_code == 200:
    print(f"  Result: {r.json()}")
else:
    print(f"  Error: {r.text}")

# Test 6: Auth check (no token)
print("\nTest 6: Auth Check (should fail with 403)")
r = requests.get(f"{BASE_URL}/sandboxes")
print(f"  Status: {r.status_code} (expected 403)")

print("\n" + "=" * 60)
print("TESTS COMPLETE")
print("=" * 60)
