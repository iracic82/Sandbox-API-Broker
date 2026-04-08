"""NIOSXaaS cleanup service for deleting universal services in sandbox accounts."""

import httpx
from dataclasses import dataclass
from typing import List, Dict, Optional
from app.core.config import settings
from app.core.circuit_breaker import niosxaas_circuit_breaker, CircuitBreakerError
from app.core.metrics import niosxaas_auth_total, niosxaas_services_deleted


@dataclass
class CleanupResult:
    """Result of NIOSXaaS cleanup operation."""

    success: bool
    skipped: bool = False  # True if no services found
    error: Optional[str] = None  # Error message if failed
    services_deleted: int = 0  # Count of services deleted


class NiosXaaSService:
    """
    Service for cleaning up NIOSXaaS universal services in sandbox accounts.

    Workflow:
    1. Authenticate with CSP (email/password) -> get JWT
    2. Switch to sandbox account context -> get new JWT
    3. List universal services in sandbox
    4. Delete services matching the configured name filter
    """

    def __init__(self):
        self.base_url = settings.niosxaas_base_url
        self.email = settings.niosxaas_email
        self.password = settings.niosxaas_password
        self.service_name_filter = settings.niosxaas_service_name
        self.timeout = httpx.Timeout(timeout=settings.niosxaas_timeout_sec)
        self.shadow_mode = settings.niosxaas_shadow_mode

    async def authenticate(self) -> str:
        """
        Authenticate with CSP and get JWT token.

        POST {base_url}/v2/session/users/sign_in
        Body: {"email": "...", "password": "..."}

        Returns:
            JWT token string

        Raises:
            Exception: If authentication fails
        """
        async def _auth():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v2/session/users/sign_in",
                    json={"email": self.email, "password": self.password},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                jwt = response.json().get("jwt")
                if not jwt:
                    raise Exception("No JWT token in authentication response")
                niosxaas_auth_total.labels(outcome="success").inc()
                return jwt

        try:
            return await niosxaas_circuit_breaker.call_async(_auth)
        except Exception as e:
            niosxaas_auth_total.labels(outcome="failed").inc()
            raise

    async def switch_account(self, jwt: str, external_id: str) -> str:
        """
        Switch to sandbox account context.

        POST {base_url}/v2/session/account_switch
        Body: {"id": "identity/accounts/{uuid}"}

        Args:
            jwt: Current JWT token
            external_id: Sandbox external_id (e.g., "identity/accounts/{uuid}")

        Returns:
            New JWT token for sandbox context

        Raises:
            Exception: If account switch fails
        """
        async def _switch():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v2/session/account_switch",
                    headers={"Authorization": f"Bearer {jwt}"},
                    json={"id": external_id},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                new_jwt = response.json().get("jwt")
                if not new_jwt:
                    raise Exception("No JWT token in account switch response")
                return new_jwt

        return await niosxaas_circuit_breaker.call_async(_switch)

    async def list_universal_services(self, jwt: str) -> List[Dict]:
        """
        List all universal services in current account context.

        GET {base_url}/api/universalinfra/v1/universalservices

        Args:
            jwt: JWT token with sandbox context

        Returns:
            List of services with id and name

        Raises:
            Exception: If API call fails
        """
        async def _list():
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/universalinfra/v1/universalservices",
                    headers={"Authorization": f"Bearer {jwt}"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return response.json().get("results", [])

        return await niosxaas_circuit_breaker.call_async(_list)

    async def delete_service(self, jwt: str, service_id: str) -> bool:
        """
        Delete a universal service.

        DELETE {base_url}/api/universalinfra/v1/universalservices/{uuid}

        Args:
            jwt: JWT token with sandbox context
            service_id: Full service ID (e.g., "infra/universal_service/abc123")

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        # Extract UUID from full service ID
        service_uuid = service_id.split("/")[-1]

        async def _delete():
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/api/universalinfra/v1/universalservices/{service_uuid}",
                    headers={"Authorization": f"Bearer {jwt}"},
                    timeout=self.timeout,
                )
                # 200 = success, 404 = already deleted
                success = response.status_code in (200, 204, 404)
                if success:
                    niosxaas_services_deleted.inc()
                return success

        return await niosxaas_circuit_breaker.call_async(_delete)

    async def cleanup_sandbox(self, external_id: str, sandbox_id: str = "") -> CleanupResult:
        """
        Full cleanup flow for a sandbox.

        1. Authenticate (get fresh JWT)
        2. Switch to sandbox account
        3. List all universal services
        4. Delete each service (filtered by name if configured)

        Args:
            external_id: Sandbox external_id (e.g., "identity/accounts/{uuid}")
            sandbox_id: Sandbox ID for logging

        Returns:
            CleanupResult with success/skipped/error status
        """
        log_prefix = f"[NIOSXaaS:{sandbox_id or external_id}]"

        # Check if enabled
        if not settings.niosxaas_enabled:
            print(f"{log_prefix} NIOSXaaS cleanup is DISABLED")
            return CleanupResult(success=False, skipped=True, error="NIOSXaaS cleanup disabled")

        # Check credentials
        if not self.email or not self.password:
            print(f"{log_prefix} Missing NIOSXaaS credentials")
            return CleanupResult(success=False, error="Missing NIOSXaaS credentials")

        try:
            # Step 1: Authenticate
            print(f"{log_prefix} Authenticating with CSP...")
            jwt = await self.authenticate()

            # Step 2: Switch to sandbox account
            print(f"{log_prefix} Switching to sandbox account...")
            sandbox_jwt = await self.switch_account(jwt, external_id)

            # Step 3: List universal services
            print(f"{log_prefix} Listing universal services...")
            services = await self.list_universal_services(sandbox_jwt)
            print(f"{log_prefix} Found {len(services)} universal service(s)")

            if not services:
                print(f"{log_prefix} No services found, skipping")
                return CleanupResult(success=True, skipped=True)

            # Step 4: Delete services (filtered by name if configured)
            deleted_count = 0
            for service in services:
                svc_id = service.get("id", "")
                svc_name = service.get("name", "")

                # Apply name filter if configured
                if self.service_name_filter and svc_name != self.service_name_filter:
                    print(f"{log_prefix} Skipping service '{svc_name}' (filter: '{self.service_name_filter}')")
                    continue

                if self.shadow_mode:
                    print(f"{log_prefix} [SHADOW MODE] Would delete service: {svc_name} ({svc_id})")
                    deleted_count += 1
                else:
                    print(f"{log_prefix} Deleting service: {svc_name} ({svc_id})")
                    success = await self.delete_service(sandbox_jwt, svc_id)
                    if success:
                        deleted_count += 1
                        print(f"{log_prefix} Successfully deleted: {svc_name}")
                    else:
                        print(f"{log_prefix} Failed to delete: {svc_name}")

            print(f"{log_prefix} Cleanup complete: {deleted_count} service(s) deleted")
            return CleanupResult(
                success=True,
                skipped=False,
                services_deleted=deleted_count,
            )

        except CircuitBreakerError as e:
            print(f"{log_prefix} Circuit breaker OPEN: {e}")
            return CleanupResult(success=False, error=f"Circuit breaker open: {e}")

        except Exception as e:
            print(f"{log_prefix} Cleanup failed: {e}")
            return CleanupResult(success=False, error=str(e))


# Global NIOSXaaS service instance
niosxaas_service = NiosXaaSService()
