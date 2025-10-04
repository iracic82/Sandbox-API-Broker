"""ENG CSP service for interacting with ENG tenant sandboxes."""

import httpx
from typing import List, Dict, Any
from app.core.config import settings
from app.core.circuit_breaker import eng_csp_circuit_breaker, CircuitBreakerError


class EngCspService:
    """Service for interacting with ENG CSP tenant API."""

    def __init__(self):
        self.base_url = settings.csp_base_url
        self.token = settings.csp_api_token
        self.timeout = httpx.Timeout(
            timeout=10.0,  # Default timeout
            connect=settings.csp_timeout_connect_sec,
            read=settings.csp_timeout_read_sec,
        )

    async def fetch_sandboxes(self) -> List[Dict[str, Any]]:
        """
        Fetch all sandboxes from ENG CSP tenant.

        Returns:
            List of sandbox dicts with id, name, external_id, created_at

        Raises:
            CircuitBreakerError: If circuit breaker is open
            httpx.HTTPError: If API request fails
        """
        async def _fetch():
            # Check if we should use real API or mock
            if settings.csp_api_token == "your_csp_token_here" or not settings.csp_base_url:
                # Mock mode for development
                print("[ENG CSP] Using MOCK data (set CSP_API_TOKEN to use real API)")
                import time
                return [
                    {
                        "id": f"eng-sandbox-{i}",
                        "name": f"eng-sandbox-{i}",
                        "external_id": f"ext-eng-{i}",
                        "created_at": int(time.time()) - (i * 3600),
                    }
                    for i in range(1, 6)  # Mock 5 sandboxes
                ]

            # Real API call
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/current_user/accounts",
                    headers={"Authorization": f"Token {self.token}"},
                    timeout=self.timeout
                )
                response.raise_for_status()
                data = response.json()

                # Filter for sandbox accounts that are active
                # Based on your API response format:
                # {
                #   "results": [
                #     {
                #       "account_type": "sandbox",
                #       "state": "active",
                #       "id": "identity/accounts/...",
                #       "name": "My Sandbox Account",
                #       "csp_id": 2009521,
                #       "created_at": "2025-03-27T16:53:47.605459Z"
                #     }
                #   ]
                # }
                sandboxes = []
                for sb in data.get("results", []):
                    if sb.get("account_type") == "sandbox" and sb.get("state") == "active":
                        # Parse created_at timestamp
                        created_at_str = sb.get("created_at", "")
                        created_at = self._parse_iso_timestamp(created_at_str)

                        sandboxes.append({
                            "id": str(sb.get("csp_id", sb["id"])),  # Use csp_id as sandbox_id
                            "name": sb.get("name", f"sandbox-{sb['id']}"),
                            "external_id": sb.get("id"),  # Full identity path as external_id
                            "created_at": created_at,
                        })

                print(f"[ENG CSP] Fetched {len(sandboxes)} active sandbox accounts")
                return sandboxes

        # Call with circuit breaker protection
        return await eng_csp_circuit_breaker.call(_fetch)

    async def delete_sandbox(self, external_id: str) -> bool:
        """
        Delete sandbox from ENG CSP tenant.

        Args:
            external_id: ENG CSP external ID (e.g., "identity/accounts/27578a8f-...")

        Returns:
            True if successful, False otherwise

        Raises:
            CircuitBreakerError: If circuit breaker is open
            httpx.HTTPError: If API request fails
        """
        async def _delete():
            # Check if we should use real API or mock
            if settings.csp_api_token == "your_csp_token_here" or not settings.csp_base_url:
                # Mock mode for development
                print(f"[ENG CSP] MOCK: Deleting sandbox {external_id}")
                return True

            # Real API call
            # Extract UUID from external_id: "identity/accounts/{uuid}"
            uuid = external_id.split("/")[-1]
            delete_url = f"{self.base_url}/sandbox/accounts/{uuid}"
            print(f"[ENG CSP] DELETE URL: {delete_url}")

            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    delete_url,
                    headers={"Authorization": f"Token {self.token}"},
                    timeout=self.timeout
                )

                success = response.status_code in (200, 204, 404)  # 404 means already deleted
                if success:
                    print(f"[ENG CSP] Deleted sandbox {external_id} (status: {response.status_code})")
                else:
                    print(f"[ENG CSP] Failed to delete {external_id} (status: {response.status_code})")

                return success

        # Call with circuit breaker protection
        return await eng_csp_circuit_breaker.call(_delete)

    async def create_sandbox(self, name: str) -> Dict[str, Any]:
        """
        Create new sandbox in ENG CSP tenant.

        Args:
            name: Sandbox name

        Returns:
            Sandbox dict with id, name, external_id

        Raises:
            CircuitBreakerError: If circuit breaker is open
            httpx.HTTPError: If API request fails

        Note: This is typically not used in production - sandboxes are pre-created
        """
        async def _create():
            # Check if we should use real API or mock
            if settings.csp_api_token == "your_csp_token_here" or not settings.csp_base_url:
                # Mock mode for development
                import time
                import uuid
                sandbox_id = str(uuid.uuid4())
                print(f"[ENG CSP] MOCK: Created sandbox {name}")
                return {
                    "id": sandbox_id,
                    "name": name,
                    "external_id": f"ext-{sandbox_id}",
                    "created_at": int(time.time()),
                }

            # Real API call (need to know the parent_account_id)
            # This would require configuration of the parent account
            raise NotImplementedError(
                "create_sandbox not implemented for production - "
                "sandboxes should be pre-created in ENG CSP tenant"
            )

        # Call with circuit breaker protection
        return await eng_csp_circuit_breaker.call(_create)

    def _parse_iso_timestamp(self, timestamp_str: str) -> int:
        """
        Parse ISO 8601 timestamp to Unix timestamp.

        Args:
            timestamp_str: ISO 8601 timestamp (e.g., "2025-03-27T16:53:47.605459Z")

        Returns:
            Unix timestamp (seconds since epoch)
        """
        if not timestamp_str:
            import time
            return int(time.time())

        try:
            from datetime import datetime
            # Parse ISO 8601 timestamp
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except Exception as e:
            print(f"[ENG CSP] Failed to parse timestamp '{timestamp_str}': {e}")
            import time
            return int(time.time())


# Global ENG CSP service instance
eng_csp_service = EngCspService()
