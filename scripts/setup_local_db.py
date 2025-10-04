#!/usr/bin/env python3
"""Setup local DynamoDB table and seed with test data."""

import asyncio
import time
import uuid
from app.db.dynamodb import db_client
from app.models.sandbox import Sandbox, SandboxStatus


async def main():
    """Create table and seed test data."""
    print("🔧 Setting up local DynamoDB...")

    # Create table
    print("📋 Creating table...")
    await db_client.create_table()

    # Seed test data
    print("🌱 Seeding test sandboxes...")

    test_sandboxes = [
        Sandbox(
            sandbox_id=str(uuid.uuid4()),
            name=f"test-sandbox-{i}",
            external_id=f"ext-{uuid.uuid4()}",
            status=SandboxStatus.AVAILABLE,
            created_at=int(time.time()),
            updated_at=int(time.time()),
            last_synced=int(time.time()),
        )
        for i in range(1, 11)  # Create 10 test sandboxes
    ]

    for sandbox in test_sandboxes:
        await db_client.put_sandbox(sandbox)
        print(f"  ✅ Created: {sandbox.name} ({sandbox.sandbox_id})")

    print(f"\n✨ Successfully created {len(test_sandboxes)} test sandboxes!")
    print("\n📍 You can now:")
    print("  1. Run: uvicorn app.main:app --reload")
    print("  2. Visit: http://localhost:8080/v1/docs")
    print("  3. Test allocation with X-Track-ID header")


if __name__ == "__main__":
    asyncio.run(main())
