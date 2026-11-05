"""Modular repository layer for business and membership queries."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from backend.app.schemas.auth import AppRole, BusinessMembership

logger = logging.getLogger("orqestra.repository")


class BaseBusinessRepository(ABC):
    """Abstract interface for business membership retrieval."""

    @abstractmethod
    async def get_user_memberships(self, user_id: str) -> List[BusinessMembership]:
        """Retrieve all active business memberships for a user."""
        pass

    @abstractmethod
    async def get_user_membership_for_business(
        self, user_id: str, business_id: str
    ) -> Optional[BusinessMembership]:
        """Retrieve user's membership in a specific business."""
        pass


class InMemoryBusinessRepository(BaseBusinessRepository):
    """In-memory business repository for testing and standalone local execution.
    
    FOR TEST AND LOCAL DEVELOPMENT ONLY.
    Must never be used in a production environment.
    """

    def __init__(self, initial_data: Optional[List[Dict[str, Any]]] = None):
        # Format: [{"user_id": "...", "business_id": "...", "business_name": "...", "role": "owner", "is_active": True}]
        self._memberships = initial_data or []

    def add_membership(
        self, user_id: str, business_id: str, business_name: str, role: AppRole, currency: str = "USD"
    ) -> None:
        """Register a membership record."""
        self._memberships.append({
            "user_id": user_id,
            "business_id": business_id,
            "business_name": business_name,
            "role": role,
            "is_active": True,
            "currency": currency,
        })

    async def get_user_memberships(self, user_id: str) -> List[BusinessMembership]:
        results = []
        for m in self._memberships:
            if m["user_id"] == user_id and m.get("is_active", True):
                results.append(
                    BusinessMembership(
                        business_id=m["business_id"],
                        business_name=m["business_name"],
                        role=m["role"],
                        is_active=m.get("is_active", True),
                        currency=m.get("currency", "USD"),
                    )
                )
        return results

    async def get_user_membership_for_business(
        self, user_id: str, business_id: str
    ) -> Optional[BusinessMembership]:
        for m in self._memberships:
            if (
                m["user_id"] == user_id
                and m["business_id"] == business_id
                and m.get("is_active", True)
            ):
                return BusinessMembership(
                    business_id=m["business_id"],
                    business_name=m["business_name"],
                    role=m["role"],
                    is_active=m.get("is_active", True),
                    currency=m.get("currency", "USD"),
                )
        return None


class SupabaseBusinessRepository(BaseBusinessRepository):
    """Database-backed business repository connecting directly to Supabase PostgREST API.
    
    Used in production to verify authentic database-backed tenant memberships.
    """

    def __init__(self, supabase_url: str, service_role_key: str, timeout: float = 5.0):
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_user_memberships(self, user_id: str) -> List[BusinessMembership]:
        """Fetch all active business memberships for user via PostgREST."""
        endpoint = f"{self.supabase_url}/rest/v1/business_members"
        params = {
            "user_id": f"eq.{user_id}",
            "is_active": "eq.true",
            "select": "business_id,role,is_active,businesses(name,currency)",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(endpoint, params=params, headers=self._headers)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch memberships from Supabase: {resp.status_code}")
                    return []
                data = resp.json()
        except Exception as e:
            logger.error(f"Error querying Supabase business_members: {e}")
            return []

        memberships: List[BusinessMembership] = []
        for row in data:
            bus_data = row.get("businesses") or {}
            bus_name = bus_data.get("name", "Business")
            bus_currency = bus_data.get("currency", "USD") or "USD"
            memberships.append(
                BusinessMembership(
                    business_id=row["business_id"],
                    business_name=bus_name,
                    role=row["role"],
                    is_active=row.get("is_active", True),
                    currency=bus_currency,
                )
            )
        return memberships

    async def get_user_membership_for_business(
        self, user_id: str, business_id: str
    ) -> Optional[BusinessMembership]:
        """Fetch user's membership for specific business via PostgREST."""
        endpoint = f"{self.supabase_url}/rest/v1/business_members"
        params = {
            "user_id": f"eq.{user_id}",
            "business_id": f"eq.{business_id}",
            "is_active": "eq.true",
            "select": "business_id,role,is_active,businesses(name,currency)",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(endpoint, params=params, headers=self._headers)
                if resp.status_code != 200:
                    logger.error(f"Failed to fetch business membership from Supabase: {resp.status_code}")
                    return None
                data = resp.json()
        except Exception as e:
            logger.error(f"Error querying Supabase business_member: {e}")
            return None

        if not data:
            return None

        row = data[0]
        bus_data = row.get("businesses") or {}
        bus_name = bus_data.get("name", "Business")
        bus_currency = bus_data.get("currency", "USD") or "USD"
        return BusinessMembership(
            business_id=row["business_id"],
            business_name=bus_name,
            role=row["role"],
            is_active=row.get("is_active", True),
            currency=bus_currency,
        )
