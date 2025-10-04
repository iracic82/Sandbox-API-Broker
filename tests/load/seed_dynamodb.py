"""Seed DynamoDB with test sandboxes for load testing.

This script populates the DynamoDB table with available sandboxes
to enable load testing without calling the CSP API.

Usage:
    python tests/load/seed_dynamodb.py --count 200

Arguments:
    --count: Number of sandboxes to create (default: 100)
    --profile: AWS profile to use (default: okta-sso)
    --region: AWS region (default: eu-central-1)
    --table: DynamoDB table name (default: sandbox-broker-pool)
"""

import argparse
import boto3
import time
from decimal import Decimal


def create_sandbox_item(index: int) -> dict:
    """Create a sandbox item for DynamoDB."""
    sandbox_id = f"load-test-sb-{index:04d}"
    return {
        'PK': f'SBX#{sandbox_id}',
        'SK': 'META',
        'sandbox_id': sandbox_id,
        'name': f'load-test-sandbox-{index}',
        'external_id': f'identity/accounts/load-test-{index:04d}',
        'status': 'available',
        'lab_duration_hours': Decimal('4'),
        'deletion_retry_count': Decimal('0'),
        'allocated_at': Decimal('0'),
        'last_synced': Decimal(str(int(time.time()))),
        'created_at': Decimal(str(int(time.time()))),
        'updated_at': Decimal(str(int(time.time()))),
    }


def seed_table(table_name: str, count: int, profile: str, region: str):
    """Seed DynamoDB table with test sandboxes."""
    print(f"🌱 Seeding {count} sandboxes to table '{table_name}'...")

    # Create session with profile
    session = boto3.Session(profile_name=profile, region_name=region)
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Batch write items (25 at a time - DynamoDB limit)
    batch_size = 25
    total_created = 0

    for batch_start in range(0, count, batch_size):
        batch_end = min(batch_start + batch_size, count)

        with table.batch_writer() as batch:
            for i in range(batch_start, batch_end):
                item = create_sandbox_item(i)
                batch.put_item(Item=item)
                total_created += 1

        print(f"  ✅ Created {total_created}/{count} sandboxes...")

        # Small delay to avoid throttling
        if batch_end < count:
            time.sleep(0.1)

    print(f"✅ Successfully seeded {total_created} sandboxes!")
    print(f"\n📊 Table stats:")

    # Get table item count (approximate)
    response = table.scan(Select='COUNT')
    print(f"  Total items in table: ~{response['Count']}")

    # Query available sandboxes
    response = table.query(
        IndexName='StatusIndex',
        KeyConditionExpression='#status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'available'},
        Select='COUNT'
    )
    print(f"  Available sandboxes: {response['Count']}")


def cleanup_test_sandboxes(table_name: str, profile: str, region: str):
    """Delete all load-test sandboxes from the table."""
    print(f"🧹 Cleaning up load-test sandboxes from '{table_name}'...")

    session = boto3.Session(profile_name=profile, region_name=region)
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Scan for load-test sandboxes
    response = table.scan(
        FilterExpression='begins_with(sandbox_id, :prefix)',
        ExpressionAttributeValues={':prefix': 'load-test-sb-'}
    )

    items_to_delete = response.get('Items', [])
    deleted_count = 0

    # Batch delete
    with table.batch_writer() as batch:
        for item in items_to_delete:
            batch.delete_item(Key={'PK': item['PK'], 'SK': item['SK']})
            deleted_count += 1

    print(f"✅ Deleted {deleted_count} load-test sandboxes")


def main():
    parser = argparse.ArgumentParser(description='Seed DynamoDB with test sandboxes')
    parser.add_argument('--count', type=int, default=100, help='Number of sandboxes to create')
    parser.add_argument('--profile', type=str, default='okta-sso', help='AWS profile')
    parser.add_argument('--region', type=str, default='eu-central-1', help='AWS region')
    parser.add_argument('--table', type=str, default='sandbox-broker-pool', help='DynamoDB table name')
    parser.add_argument('--cleanup', action='store_true', help='Clean up load-test sandboxes')

    args = parser.parse_args()

    try:
        if args.cleanup:
            cleanup_test_sandboxes(args.table, args.profile, args.region)
        else:
            seed_table(args.table, args.count, args.profile, args.region)

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
