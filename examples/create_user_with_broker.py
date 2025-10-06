#!/usr/bin/env python3
"""
Create Infoblox CSP User in Broker-Allocated Sandbox

This script creates a user in the CSP sandbox that was allocated via the broker.
It uses external_id.txt (CSP account ID) instead of sandbox_id.txt (broker ID).

Usage:
1. Run instruqt_broker_allocation.py first (creates external_id.txt)
2. Run this script to create a user in that CSP sandbox
"""

import os
import json
import sys
import requests
import time
import random

# === Required Environment Variables ===
BASE_URL = "https://csp.infoblox.com"
EMAIL = os.getenv("INFOBLOX_EMAIL")
PASSWORD = os.getenv("INFOBLOX_PASSWORD")
USER_EMAIL = os.getenv("INSTRUQT_EMAIL")
USER_NAME = os.getenv("INSTRUQT_PARTICIPANT_ID")

# === File Paths ===
# CHANGED: Use external_id.txt (CSP account ID) instead of sandbox_id.txt (broker ID)
EXTERNAL_ID_FILE = "external_id.txt"  # CSP account UUID
USER_ID_FILE = "user_id.txt"

if not all([EMAIL, PASSWORD, USER_EMAIL, USER_NAME]):
    print("❌ Missing one of: INFOBLOX_EMAIL, INFOBLOX_PASSWORD, INSTRUQT_EMAIL, INSTRUQT_PARTICIPANT_ID", flush=True)
    sys.exit(1)

# === Step 1: Authenticate ===
print("🔐 Authenticating with CSP...", flush=True)
auth_url = f"{BASE_URL}/v2/session/users/sign_in"
auth_resp = requests.post(auth_url, json={"email": EMAIL, "password": PASSWORD})
auth_resp.raise_for_status()
jwt = auth_resp.json()["jwt"]
headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
print("✅ Logged in and obtained JWT", flush=True)

# === Step 2: Read CSP Account ID from external_id.txt ===
print(f"📂 Reading CSP account ID from {EXTERNAL_ID_FILE}...", flush=True)
try:
    with open(EXTERNAL_ID_FILE, "r") as f:
        csp_account_id = f.read().strip()
except FileNotFoundError:
    print(f"❌ {EXTERNAL_ID_FILE} not found!", flush=True)
    print("   Make sure you run instruqt_broker_allocation.py first.", flush=True)
    sys.exit(1)

if not csp_account_id:
    print(f"❌ {EXTERNAL_ID_FILE} is empty!", flush=True)
    sys.exit(1)

print(f"✅ CSP Account ID: {csp_account_id}", flush=True)

# === Step 3: Switch Account ===
print(f"🔁 Switching to CSP sandbox account {csp_account_id}...", flush=True)
switch_url = f"{BASE_URL}/v2/session/account_switch"
switch_payload = {"id": f"identity/accounts/{csp_account_id}"}
switch_resp = requests.post(switch_url, headers=headers, json=switch_payload)
switch_resp.raise_for_status()
jwt = switch_resp.json()["jwt"]
headers["Authorization"] = f"Bearer {jwt}"
print(f"✅ Switched to sandbox account {csp_account_id}", flush=True)
time.sleep(3)

# === Step 4: Get Groups ===
print("📋 Fetching user groups...", flush=True)
group_url = f"{BASE_URL}/v2/groups"
group_resp = requests.get(group_url, headers=headers)
group_resp.raise_for_status()
groups = group_resp.json().get("results", [])

user_group_id = next((g["id"] for g in groups if g.get("name") == "user"), None)
admin_group_id = next((g["id"] for g in groups if g.get("name") == "act_admin"), None)

if not user_group_id or not admin_group_id:
    print(f"❌ Could not find required groups. user: {user_group_id}, admin: {admin_group_id}", flush=True)
    sys.exit(1)

print(f"✅ Found user group: {user_group_id}", flush=True)
print(f"✅ Found admin group: {admin_group_id}", flush=True)

# === Step 5: Create User with retry ===
user_payload = {
    "name": USER_NAME,
    "email": USER_EMAIL,
    "type": "interactive",
    "group_ids": [user_group_id, admin_group_id]
}
user_url = f"{BASE_URL}/v2/users"

max_retries = 5
for attempt in range(max_retries):
    try:
        print(f"📤 Creating user '{USER_NAME}'... (attempt {attempt+1}/{max_retries})", flush=True)
        user_resp = requests.post(user_url, headers=headers, json=user_payload)
        user_resp.raise_for_status()
        user_data = user_resp.json()
        break
    except requests.RequestException as e:
        print(f"⚠️ Attempt {attempt+1} failed: {e}", flush=True)
        if attempt < max_retries - 1:
            sleep_time = (2**attempt) + random.random()
            print(f"   Retrying in {sleep_time:.1f} seconds...", flush=True)
            time.sleep(sleep_time)
else:
    print("❌ User creation failed after all retries", flush=True)
    sys.exit(1)

print("✅ User created successfully.", flush=True)
print(json.dumps(user_data, indent=2), flush=True)

# === Step 6: Save user_id.txt ===
user_id = user_data.get("result", {}).get("id")
if user_id and user_id.startswith("identity/users/"):
    user_id = user_id.split("/")[-1]
    with open(USER_ID_FILE, "w") as f:
        f.write(user_id)
    print(f"✅ User ID saved to {USER_ID_FILE}: {user_id}", flush=True)
else:
    print("❌ User ID not found or unexpected format. Aborting.", flush=True)
    sys.exit(1)

print("\n" + "="*60, flush=True)
print("🎉 User Creation Complete!", flush=True)
print(f"   User Name: {USER_NAME}", flush=True)
print(f"   User Email: {USER_EMAIL}", flush=True)
print(f"   User ID: {user_id}", flush=True)
print(f"   CSP Account: {csp_account_id}", flush=True)
print("="*60, flush=True)
