"""Audit log domain schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Immutable audit trail record."""

    id: str
    business_id: str
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""

    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
