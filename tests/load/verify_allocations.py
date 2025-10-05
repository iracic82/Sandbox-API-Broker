"""
Verify zero double-allocations after load test.

This script scans DynamoDB and verifies:
1. Each allocated sandbox has exactly ONE track_id
2. Each track_id has exactly ONE sandbox
3. No duplicate allocations

Usage:
    python tests/load/verify_allocations.py --region eu-central-1
"""

import argparse
import boto3
from collections import defaultdict


def verify_allocations(region: str, table_name: str = "sandbox-broker-pool"):
    """Verify no double-allocations in DynamoDB."""

    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)

    print(f"\n🔍 Scanning DynamoDB table '{table_name}'...")

    # Scan all items
    response = table.scan()
    items = response.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    print(f"📦 Total items: {len(items)}")

    # Analyze allocated sandboxes
    allocated_sandboxes = [item for item in items if item.get('status') == 'allocated']
    available_sandboxes = [item for item in items if item.get('status') == 'available']

    print(f"\n📊 Status breakdown:")
    print(f"  ✅ Allocated: {len(allocated_sandboxes)}")
    print(f"  🆓 Available: {len(available_sandboxes)}")

    # Check for double-allocations
    print(f"\n🔎 Checking for double-allocations...")

    # Map: track_id -> list of sandboxes
    track_to_sandboxes = defaultdict(list)

    # Map: sandbox_id -> track_id
    sandbox_to_track = {}

    for item in allocated_sandboxes:
        sandbox_id = item.get('sandbox_id')
        track_id = item.get('allocated_to_track')

        if track_id:
            track_to_sandboxes[track_id].append(sandbox_id)
            sandbox_to_track[sandbox_id] = track_id

    # Verify each track has exactly ONE sandbox
    print(f"\n✅ Unique tracks: {len(track_to_sandboxes)}")
    print(f"✅ Unique sandboxes: {len(sandbox_to_track)}")

    # Check for double-allocations (track with multiple sandboxes)
    double_allocations = {track: sandboxes for track, sandboxes in track_to_sandboxes.items() if len(sandboxes) > 1}

    if double_allocations:
        print(f"\n❌ DOUBLE-ALLOCATIONS FOUND: {len(double_allocations)}")
        for track, sandboxes in list(double_allocations.items())[:5]:  # Show first 5
            print(f"  Track {track}: allocated {len(sandboxes)} sandboxes {sandboxes}")
        return False
    else:
        print(f"\n✅ **ZERO DOUBLE-ALLOCATIONS** - Each track has exactly 1 sandbox!")

    # Check for sandbox allocated to multiple tracks (shouldn't happen with atomic writes)
    sandbox_allocation_count = defaultdict(int)
    for item in allocated_sandboxes:
        sandbox_id = item.get('sandbox_id')
        sandbox_allocation_count[sandbox_id] += 1

    multi_allocated = {sbx: count for sbx, count in sandbox_allocation_count.items() if count > 1}

    if multi_allocated:
        print(f"\n❌ SANDBOXES WITH MULTIPLE ALLOCATIONS: {len(multi_allocated)}")
        for sbx, count in list(multi_allocated.items())[:5]:
            print(f"  Sandbox {sbx}: allocated {count} times")
        return False
    else:
        print(f"✅ Each sandbox allocated exactly once!")

    # Show lab/track distribution if instruqt_track_id exists
    print(f"\n📚 Analyzing multi-student scenario...")

    # Extract lab names from track IDs (format: inst-student-X-TIMESTAMP in lab Y)
    lab_distribution = defaultdict(int)
    student_sandboxes = defaultdict(str)

    for track_id, sandbox_id in sandbox_to_track.items():
        student_sandboxes[track_id] = sandbox_id

    print(f"  Total students with allocations: {len(student_sandboxes)}")

    # Sample first 10 allocations
    print(f"\n📋 Sample allocations (first 10):")
    for i, (track_id, sandbox_id) in enumerate(list(student_sandboxes.items())[:10]):
        print(f"  {i+1}. Student: {track_id[:30]}... → Sandbox: {sandbox_id}")

    print(f"\n{'='*60}")
    print(f"✅ **VERIFICATION PASSED** - NO DOUBLE-ALLOCATIONS DETECTED")
    print(f"{'='*60}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify zero double-allocations")
    parser.add_argument('--region', default='eu-central-1', help='AWS region')
    parser.add_argument('--table', default='sandbox-broker-pool', help='DynamoDB table name')

    args = parser.parse_args()

    success = verify_allocations(args.region, args.table)

    exit(0 if success else 1)
