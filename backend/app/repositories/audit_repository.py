"""Audit log repository interface and implementations."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from backend.app.schemas.audit import AuditLogResponse

logger = logging.getLogger("orqestra.audit")


class BaseAuditLogRepository(ABC):
    """Abstract interface for audit logging."""

    @abstractmethod
    async def log_event(
        self,
        business_id: str,
        user_id: Optional[str],
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogResponse:
        """Record an immutable audit log entry."""
        pass

    @abstractmethod
    async def list_audit_logs(
        self,
        business_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AuditLogResponse], int]:
        """Query audit log history for a business."""
        pass


class InMemoryAuditLogRepository(BaseAuditLogRepository):
    """In-memory audit log repository for tests and local development."""

    def __init__(self):
        self._logs: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def log_event(
        self,
        business_id: str,
        user_id: Optional[str],
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogResponse:
        async with self._lock:
            log_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            entry = {
                "id": log_id,
                "business_id": business_id,
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_values": old_values,
                "new_values": new_values,
                "ip_address": ip_address,
                "created_at": now,
            }
            self._logs.insert(0, entry)
            return AuditLogResponse(**entry)

    async def list_audit_logs(
        self,
        business_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AuditLogResponse], int]:
        async with self._lock:
            filtered = [
                log for log in self._logs
                if log["business_id"] == business_id
                and (entity_type is None or log["entity_type"] == entity_type)
                and (entity_id is None or log["entity_id"] == entity_id)
            ]
            total = len(filtered)
            start = (page - 1) * page_size
            paginated = filtered[start : start + page_size]
            return [AuditLogResponse(**log) for log in paginated], total


class SupabaseAuditLogRepository(BaseAuditLogRepository):
    """Database-backed audit repository connecting via PostgREST."""

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

    async def log_event(
        self,
        business_id: str,
        user_id: Optional[str],
        action: str,
        entity_type: str,
        entity_id: Optional[str],
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogResponse:
        endpoint = f"{self.supabase_url}/rest/v1/audit_logs"
        payload = {
            "business_id": business_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": ip_address,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code not in (200, 201):
                logger.error(f"Failed to record audit log: {resp.status_code}")
                # Fallback record
                return AuditLogResponse(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    user_id=user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    old_values=old_values,
                    new_values=new_values,
                    created_at=datetime.now(timezone.utc),
                )
            data = resp.json()[0]
            return AuditLogResponse(**data)

    async def list_audit_logs(
        self,
        business_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[AuditLogResponse], int]:
        endpoint = f"{self.supabase_url}/rest/v1/audit_logs"
        params = {
            "business_id": f"eq.{business_id}",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if entity_type:
            params["entity_type"] = f"eq.{entity_type}"
        if entity_id:
            params["entity_id"] = f"eq.{entity_id}"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to query audit logs: {resp.status_code}")
                return [], 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)
            return [AuditLogResponse(**row) for row in data], total
