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

        TODO: Replace with actual ENG CSP API call
        """
        def _fetch():
            # Mock implementation for now
            # In production, replace with:
            # async with httpx.AsyncClient() as client:
            #     response = await client.get(
            #         f"{self.base_url}/current_user/accounts",
            #         headers={"Authorization": f"Bearer {self.token}"},
            #         timeout=self.timeout
            #     )
            #     response.raise_for_status()
            #     data = response.json()
            #     # Filter for sandbox accounts that are active
            #     return [
            #         {
            #             "id": sb["id"],
            #             "name": sb["name"],
            #             "external_id": sb["id"],
            #             "created_at": sb["created_at"],
            #         }
            #         for sb in data.get("results", [])
            #         if sb.get("account_type") == "sandbox" and sb.get("state") == "active"
            #     ]

            # Mock data (remove in production)
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

        # Call with circuit breaker protection
        return eng_csp_circuit_breaker.call(_fetch)

    async def delete_sandbox(self, external_id: str) -> bool:
        """
        Delete sandbox from ENG CSP tenant.

        Args:
            external_id: ENG CSP sandbox external ID

        Returns:
            True if successful, False otherwise

        Raises:
            CircuitBreakerError: If circuit breaker is open

        TODO: Replace with actual ENG CSP API call
        """
        def _delete():
            # Mock implementation for now
            # In production, replace with:
            # async with httpx.AsyncClient() as client:
            #     response = await client.delete(
            #         f"{self.base_url}/accounts/{external_id}",
            #         headers={"Authorization": f"Bearer {self.token}"},
            #         timeout=self.timeout
            #     )
            #     return response.status_code in (200, 204)

            # Mock: always succeed
            print(f"[MOCK] Deleting sandbox from ENG CSP: {external_id}")
            return True

        # Call with circuit breaker protection
        return eng_csp_circuit_breaker.call(_delete)

    async def create_sandbox(self, name: str) -> Dict[str, Any]:
        """
        Create new sandbox in ENG CSP tenant.

        Args:
            name: Sandbox name

        Returns:
            Sandbox dict with id, name, external_id

        TODO: Replace with actual ENG CSP API call
        """
        # Mock implementation
        import time
        import uuid

        sandbox_id = str(uuid.uuid4())
        return {
            "id": sandbox_id,
            "name": name,
            "external_id": f"ext-{sandbox_id}",
            "created_at": int(time.time()),
        }


# Global ENG CSP service instance
eng_csp_service = EngCspService()
