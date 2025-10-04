#!/usr/bin/env python3
import asyncio
import time
from app.db.dynamodb import db_client
from app.models.sandbox import Sandbox, SandboxStatus

async def main():
    await db_client.create_table()

    data = [
        ('avail-1', 'Available 1', 'ext-a1', SandboxStatus.AVAILABLE, None, 0, None),
        ('avail-2', 'Available 2', 'ext-a2', SandboxStatus.AVAILABLE, None, 0, None),
        ('alloc-1', 'Allocated 1', 'ext-al1', SandboxStatus.ALLOCATED, 'track-1', int(time.time()), None),
        ('alloc-2', 'Allocated 2', 'ext-al2', SandboxStatus.ALLOCATED, 'track-2', int(time.time()), None),
        ('pend-1', 'Pending 1', 'ext-p1', SandboxStatus.PENDING_DELETION, 'track-3', int(time.time()), int(time.time())),
        ('pend-2', 'Pending 2', 'ext-p2', SandboxStatus.PENDING_DELETION, 'track-4', int(time.time()), int(time.time())),
    ]

    for sid, name, eid, status, track, alloc_at, del_at in data:
        sb = Sandbox(
            sandbox_id=sid,
            name=name,
            external_id=eid,
            status=status,
            allocated_to_track=track,
            allocated_at=alloc_at,
            deletion_requested_at=del_at,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        await db_client.put_sandbox(sb)

    print('✅ 6 sandboxes created (2 available, 2 allocated, 2 pending_deletion)')

asyncio.run(main())
