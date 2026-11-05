"""Customer repository interface and implementations."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from backend.app.schemas.customers import CustomerCreate, CustomerResponse, CustomerUpdate

logger = logging.getLogger("orqestra.customers")


class BaseCustomerRepository(ABC):
    """Abstract interface for customer operations."""

    @abstractmethod
    async def list_customers(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CustomerResponse], int]:
        pass

    @abstractmethod
    async def get_customer(self, business_id: str, customer_id: str) -> Optional[CustomerResponse]:
        pass

    @abstractmethod
    async def create_customer(
        self, business_id: str, customer: CustomerCreate, user_id: str
    ) -> CustomerResponse:
        pass

    @abstractmethod
    async def update_customer(
        self, business_id: str, customer_id: str, update: CustomerUpdate, user_id: str
    ) -> Optional[CustomerResponse]:
        pass

    @abstractmethod
    async def deactivate_customer(
        self, business_id: str, customer_id: str, user_id: str
    ) -> Optional[CustomerResponse]:
        pass


class InMemoryCustomerRepository(BaseCustomerRepository):
    """In-memory customer repository for tests and local development."""

    def __init__(self, initial_customers: Optional[List[Dict[str, Any]]] = None):
        self._customers: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        if initial_customers:
            for c in initial_customers:
                self._customers[c["id"]] = dict(c)

    def _to_response(self, c: Dict[str, Any]) -> CustomerResponse:
        return CustomerResponse(
            id=c["id"],
            business_id=c["business_id"],
            name=c["name"],
            email=c.get("email"),
            phone=c.get("phone"),
            address=c.get("address"),
            notes=c.get("notes"),
            is_active=c.get("is_active", True),
            created_at=c["created_at"],
            updated_at=c["updated_at"],
        )

    async def list_customers(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CustomerResponse], int]:
        async with self._lock:
            results = []
            for c in self._customers.values():
                if c["business_id"] != business_id:
                    continue
                if is_active is not None and c.get("is_active", True) != is_active:
                    continue
                if search:
                    term = search.lower()
                    name_match = term in c["name"].lower()
                    email_match = c.get("email") and term in c["email"].lower()
                    phone_match = c.get("phone") and term in c["phone"].lower()
                    if not (name_match or email_match or phone_match):
                        continue
                results.append(self._to_response(c))

            results.sort(key=lambda x: x.created_at, reverse=True)
            total = len(results)
            start = (page - 1) * page_size
            return results[start : start + page_size], total

    async def get_customer(self, business_id: str, customer_id: str) -> Optional[CustomerResponse]:
        async with self._lock:
            c = self._customers.get(customer_id)
            if c and c["business_id"] == business_id:
                return self._to_response(c)
            return None

    async def create_customer(
        self, business_id: str, customer: CustomerCreate, user_id: str
    ) -> CustomerResponse:
        async with self._lock:
            cust_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            record = {
                "id": cust_id,
                "business_id": business_id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "address": customer.address,
                "notes": customer.notes,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            self._customers[cust_id] = record
            return self._to_response(record)

    async def update_customer(
        self, business_id: str, customer_id: str, update: CustomerUpdate, user_id: str
    ) -> Optional[CustomerResponse]:
        async with self._lock:
            c = self._customers.get(customer_id)
            if not c or c["business_id"] != business_id:
                return None

            if update.name is not None:
                c["name"] = update.name
            if update.email is not None:
                c["email"] = update.email
            if update.phone is not None:
                c["phone"] = update.phone
            if update.address is not None:
                c["address"] = update.address
            if update.notes is not None:
                c["notes"] = update.notes
            if update.is_active is not None:
                c["is_active"] = update.is_active

            c["updated_at"] = datetime.now(timezone.utc)
            return self._to_response(c)

    async def deactivate_customer(
        self, business_id: str, customer_id: str, user_id: str
    ) -> Optional[CustomerResponse]:
        return await self.update_customer(business_id, customer_id, CustomerUpdate(is_active=False), user_id)


class SupabaseCustomerRepository(BaseCustomerRepository):
    """Database-backed customer repository connecting via PostgREST."""

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
            "Prefer": "return=representation",
        }

    async def list_customers(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CustomerResponse], int]:
        endpoint = f"{self.supabase_url}/rest/v1/customers"
        params = {
            "business_id": f"eq.{business_id}",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if is_active is not None:
            params["is_active"] = f"eq.{str(is_active).lower()}"
        if search:
            params["or"] = f"(name.ilike.*{search}*,email.ilike.*{search}*,phone.ilike.*{search}*)"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to query customers: {resp.status_code}")
                return [], 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)
            return [CustomerResponse(**row) for row in data], total

    async def get_customer(self, business_id: str, customer_id: str) -> Optional[CustomerResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/customers"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{customer_id}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code != 200 or not resp.json():
                return None
            return CustomerResponse(**resp.json()[0])

    async def create_customer(
        self, business_id: str, customer: CustomerCreate, user_id: str
    ) -> CustomerResponse:
        endpoint = f"{self.supabase_url}/rest/v1/customers"
        payload = {
            "business_id": business_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "address": customer.address,
            "notes": customer.notes,
            "is_active": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Failed to create customer: {resp.status_code}")
            return CustomerResponse(**resp.json()[0])

    async def update_customer(
        self, business_id: str, customer_id: str, update: CustomerUpdate, user_id: str
    ) -> Optional[CustomerResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/customers"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{customer_id}"}
        payload = {}
        if update.name is not None:
            payload["name"] = update.name
        if update.email is not None:
            payload["email"] = update.email
        if update.phone is not None:
            payload["phone"] = update.phone
        if update.address is not None:
            payload["address"] = update.address
        if update.notes is not None:
            payload["notes"] = update.notes
        if update.is_active is not None:
            payload["is_active"] = update.is_active

        if not payload:
            return await self.get_customer(business_id, customer_id)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(endpoint, params=params, json=payload, headers=self._headers)
            if resp.status_code not in (200, 204) or not resp.json():
                return None
            return CustomerResponse(**resp.json()[0])

    async def deactivate_customer(
        self, business_id: str, customer_id: str, user_id: str
    ) -> Optional[CustomerResponse]:
        return await self.update_customer(business_id, customer_id, CustomerUpdate(is_active=False), user_id)
