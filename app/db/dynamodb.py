"""DynamoDB client wrapper with atomic operations."""

import time
import random
from typing import Optional
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
from app.models.sandbox import Sandbox, SandboxStatus


class DynamoDBClient:
    """DynamoDB client for sandbox operations."""

    def __init__(self):
        """Initialize DynamoDB client."""
        session_kwargs = {"region_name": settings.aws_region}

        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self.dynamodb = boto3.resource("dynamodb", **session_kwargs)

        if settings.ddb_endpoint_url:
            # Override for local DynamoDB
            self.dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=settings.ddb_endpoint_url,
                region_name=settings.aws_region,
                aws_access_key_id="local",
                aws_secret_access_key="local",
            )

        self.table = self.dynamodb.Table(settings.ddb_table_name)

    def _to_item(self, sandbox: Sandbox) -> dict:
        """Convert Sandbox model to DynamoDB item."""
        item = {
            "PK": f"SBX#{sandbox.sandbox_id}",
            "SK": "META",
            "sandbox_id": sandbox.sandbox_id,
            "name": sandbox.name,
            "external_id": sandbox.external_id,
            "status": sandbox.status.value,
            "lab_duration_hours": sandbox.lab_duration_hours,
            "deletion_retry_count": sandbox.deletion_retry_count,
            "allocated_at": sandbox.allocated_at or 0,  # GSI sort key - default to 0 for available
        }

        # Optional fields
        if sandbox.allocated_to_track:
            item["allocated_to_track"] = sandbox.allocated_to_track
        if sandbox.deletion_requested_at:
            item["deletion_requested_at"] = sandbox.deletion_requested_at
        if sandbox.last_synced:
            item["last_synced"] = sandbox.last_synced
        if sandbox.idempotency_key:
            item["idempotency_key"] = sandbox.idempotency_key
        if sandbox.track_name:
            item["track_name"] = sandbox.track_name
        if sandbox.created_at:
            item["created_at"] = sandbox.created_at
        if sandbox.updated_at:
            item["updated_at"] = sandbox.updated_at

        return item

    def _from_item(self, item: dict) -> Sandbox:
        """Convert DynamoDB item to Sandbox model."""
        return Sandbox(
            sandbox_id=item["sandbox_id"],
            name=item["name"],
            external_id=item["external_id"],
            status=SandboxStatus(item["status"]),
            allocated_to_track=item.get("allocated_to_track"),
            allocated_at=int(item["allocated_at"]) if item.get("allocated_at") else None,
            lab_duration_hours=int(item.get("lab_duration_hours", 4)),
            deletion_requested_at=int(item["deletion_requested_at"]) if item.get("deletion_requested_at") else None,
            deletion_retry_count=int(item.get("deletion_retry_count", 0)),
            last_synced=int(item["last_synced"]) if item.get("last_synced") else None,
            idempotency_key=item.get("idempotency_key"),
            track_name=item.get("track_name"),
            created_at=int(item["created_at"]) if item.get("created_at") else None,
            updated_at=int(item["updated_at"]) if item.get("updated_at") else None,
        )

    async def get_sandbox(self, sandbox_id: str) -> Optional[Sandbox]:
        """Get sandbox by ID."""
        try:
            response = self.table.get_item(Key={"PK": f"SBX#{sandbox_id}", "SK": "META"})
            if "Item" in response:
                return self._from_item(response["Item"])
            return None
        except ClientError as e:
            raise Exception(f"DynamoDB error getting sandbox: {e}")

    async def get_available_candidates(self, k: int = 15) -> list[Sandbox]:
        """Get K available sandbox candidates from GSI1."""
        try:
            response = self.table.query(
                IndexName=settings.ddb_gsi1_name,
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": SandboxStatus.AVAILABLE.value},
                Limit=k,
            )

            sandboxes = [self._from_item(item) for item in response.get("Items", [])]
            # Shuffle to avoid thundering herd
            random.shuffle(sandboxes)
            return sandboxes

        except ClientError as e:
            raise Exception(f"DynamoDB error querying available sandboxes: {e}")

    async def atomic_allocate(
        self,
        sandbox_id: str,
        track_id: str,
        idempotency_key: str,
        current_time: int,
        track_name: Optional[str] = None,
    ) -> Optional[Sandbox]:
        """
        Atomically allocate sandbox using conditional write.
        Returns Sandbox if successful, None if condition failed.
        """
        try:
            # Build update expression dynamically based on whether track_name is provided
            update_expr = """
                SET #status = :allocated,
                    allocated_to_track = :track_id,
                    allocated_at = :now,
                    idempotency_key = :idem_key,
                    updated_at = :now
            """
            expr_values = {
                ":allocated": SandboxStatus.ALLOCATED.value,
                ":available": SandboxStatus.AVAILABLE.value,
                ":track_id": track_id,
                ":now": current_time,
                ":idem_key": idempotency_key,
            }

            # Add track_name if provided
            if track_name:
                update_expr += ", track_name = :track_name"
                expr_values[":track_name"] = track_name

            response = self.table.update_item(
                Key={"PK": f"SBX#{sandbox_id}", "SK": "META"},
                UpdateExpression=update_expr,
                ConditionExpression="attribute_exists(PK) AND #status = :available",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW",
            )

            return self._from_item(response["Attributes"])

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Sandbox not available (already allocated or doesn't exist)
                return None
            raise Exception(f"DynamoDB error allocating sandbox: {e}")

    async def find_allocation_by_idempotency_key(self, idempotency_key: str) -> Optional[Sandbox]:
        """Find existing allocation by idempotency key (for deduplication)."""
        try:
            response = self.table.query(
                IndexName=settings.ddb_gsi3_name,
                KeyConditionExpression="idempotency_key = :key",
                ExpressionAttributeValues={":key": idempotency_key},
                Limit=1,
            )

            items = response.get("Items", [])
            if items:
                sandbox = self._from_item(items[0])
                # Only return if still allocated
                if sandbox.status == SandboxStatus.ALLOCATED:
                    return sandbox
            return None

        except ClientError as e:
            # If GSI3 doesn't exist, just return None (idempotency is optional optimization)
            if "ResourceNotFoundException" in str(e):
                return None
            raise Exception(f"DynamoDB error finding by idempotency key: {e}")

    async def mark_for_deletion(
        self,
        sandbox_id: str,
        track_id: str,
        current_time: int,
        max_expiry_time: int,
    ) -> Optional[Sandbox]:
        """
        Mark sandbox for deletion with ownership and expiry checks.
        Returns Sandbox if successful, None if condition failed.
        """
        try:
            response = self.table.update_item(
                Key={"PK": f"SBX#{sandbox_id}", "SK": "META"},
                UpdateExpression="""
                    SET #status = :pending_deletion,
                        deletion_requested_at = :now,
                        updated_at = :now
                """,
                ConditionExpression="""
                    attribute_exists(PK) AND
                    #status = :allocated AND
                    allocated_to_track = :track_id AND
                    allocated_at > :max_expiry
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":pending_deletion": SandboxStatus.PENDING_DELETION.value,
                    ":allocated": SandboxStatus.ALLOCATED.value,
                    ":track_id": track_id,
                    ":now": current_time,
                    ":max_expiry": max_expiry_time,
                },
                ReturnValues="ALL_NEW",
            )

            return self._from_item(response["Attributes"])

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Not owner, already deleted, or expired
                return None
            raise Exception(f"DynamoDB error marking for deletion: {e}")

    async def put_sandbox(self, sandbox: Sandbox) -> Sandbox:
        """Put/upsert sandbox (for sync operations)."""
        try:
            sandbox.updated_at = int(time.time())
            if not sandbox.created_at:
                sandbox.created_at = sandbox.updated_at

            self.table.put_item(Item=self._to_item(sandbox))
            return sandbox

        except ClientError as e:
            raise Exception(f"DynamoDB error putting sandbox: {e}")

    async def create_table(self):
        """Create DynamoDB table with GSIs (for local development)."""
        try:
            table = self.dynamodb.create_table(
                TableName=settings.ddb_table_name,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                    {"AttributeName": "status", "AttributeType": "S"},
                    {"AttributeName": "allocated_at", "AttributeType": "N"},
                    {"AttributeName": "allocated_to_track", "AttributeType": "S"},
                    {"AttributeName": "idempotency_key", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": settings.ddb_gsi1_name,
                        "KeySchema": [
                            {"AttributeName": "status", "KeyType": "HASH"},
                            {"AttributeName": "allocated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": settings.ddb_gsi2_name,
                        "KeySchema": [
                            {"AttributeName": "allocated_to_track", "KeyType": "HASH"},
                            {"AttributeName": "allocated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                    {
                        "IndexName": settings.ddb_gsi3_name,
                        "KeySchema": [
                            {"AttributeName": "idempotency_key", "KeyType": "HASH"},
                            {"AttributeName": "allocated_at", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    },
                ],
                BillingMode="PROVISIONED",
                ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            )
            table.wait_until_exists()
            print(f"✅ Created table: {settings.ddb_table_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceInUseException":
                raise Exception(f"Error creating table: {e}")


# Global DynamoDB client instance
db_client = DynamoDBClient()
