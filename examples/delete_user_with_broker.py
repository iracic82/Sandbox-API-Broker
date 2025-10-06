#!/usr/bin/env python3
"""
Delete Infoblox CSP User from Broker-Allocated Sandbox

This script deletes a user from the CSP sandbox that was allocated via the broker.
It uses external_id.txt (CSP account ID) and user_id.txt (created by create_user_with_broker.py).

Usage:
1. Run this script before instruqt_broker_cleanup.py
2. This deletes the user from CSP
3. Then run instruqt_broker_cleanup.py to mark sandbox for deletion
"""

import os
import sys
import requests
import time

# === Required Environment Variables ===
BASE_URL = "https://csp.infoblox.com"
EMAIL = os.getenv("INFOBLOX_EMAIL")
PASSWORD = os.getenv("INFOBLOX_PASSWORD")

# === File Paths ===
EXTERNAL_ID_FILE = "external_id.txt"  # CSP account UUID
USER_ID_FILE = "user_id.txt"         # User ID created by create_user script

if not all([EMAIL, PASSWORD]):
    print("❌ Missing one of: INFOBLOX_EMAIL, INFOBLOX_PASSWORD", flush=True)
    sys.exit(1)

# === Step 1: Authenticate ===
print("🔐 Authenticating with CSP...", flush=True)
auth_url = f"{BASE_URL}/v2/session/users/sign_in"
auth_resp = requests.post(auth_url, json={"email": EMAIL, "password": PASSWORD})
auth_resp.raise_for_status()
jwt = auth_resp.json()["jwt"]
headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
print("✅ Logged in and obtained JWT", flush=True)

# === Step 2: Read CSP Account ID ===
print(f"📂 Reading CSP account ID from {EXTERNAL_ID_FILE}...", flush=True)
try:
    with open(EXTERNAL_ID_FILE, "r") as f:
        csp_account_id = f.read().strip()
except FileNotFoundError:
    print(f"⚠️ {EXTERNAL_ID_FILE} not found, nothing to clean up", flush=True)
    sys.exit(0)  # Not an error

if not csp_account_id:
    print(f"⚠️ {EXTERNAL_ID_FILE} is empty, nothing to clean up", flush=True)
    sys.exit(0)

print(f"✅ CSP Account ID: {csp_account_id}", flush=True)

# === Step 3: Read User ID ===
print(f"📂 Reading user ID from {USER_ID_FILE}...", flush=True)
try:
    with open(USER_ID_FILE, "r") as f:
        user_id = f.read().strip()
except FileNotFoundError:
    print(f"⚠️ {USER_ID_FILE} not found, no user to delete", flush=True)
    sys.exit(0)  # Not an error

if not user_id:
    print(f"⚠️ {USER_ID_FILE} is empty, no user to delete", flush=True)
    sys.exit(0)

print(f"✅ User ID: {user_id}", flush=True)

# === Step 4: Switch Account ===
print(f"🔁 Switching to CSP sandbox account {csp_account_id}...", flush=True)
switch_url = f"{BASE_URL}/v2/session/account_switch"
switch_payload = {"id": f"identity/accounts/{csp_account_id}"}
switch_resp = requests.post(switch_url, headers=headers, json=switch_payload)
switch_resp.raise_for_status()
jwt = switch_resp.json()["jwt"]
headers["Authorization"] = f"Bearer {jwt}"
print(f"✅ Switched to sandbox account", flush=True)
time.sleep(2)

# === Step 5: Delete User ===
print(f"🗑️  Deleting user {user_id}...", flush=True)
delete_url = f"{BASE_URL}/v2/users/identity/users/{user_id}"

try:
    delete_resp = requests.delete(delete_url, headers=headers)

    if delete_resp.status_code == 200:
        print("✅ User deleted successfully", flush=True)
    elif delete_resp.status_code == 404:
        print("⚠️ User not found (may have already been deleted)", flush=True)
    else:
        print(f"⚠️ Unexpected response: HTTP {delete_resp.status_code}", flush=True)
        print(f"   Response: {delete_resp.text}", flush=True)
        # Don't exit with error - user deletion is best-effort

except Exception as e:
    print(f"⚠️ Error deleting user: {e}", flush=True)
    # Don't exit with error - user deletion is best-effort

print("\n" + "="*60, flush=True)
print("🧹 User Cleanup Complete!", flush=True)
print(f"   User ID: {user_id}", flush=True)
print(f"   CSP Account: {csp_account_id}", flush=True)
print("\n💡 Next step: Run instruqt_broker_cleanup.py to mark sandbox for deletion", flush=True)
print("="*60, flush=True)
