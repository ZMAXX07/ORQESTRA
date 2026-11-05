"""Pydantic schemas for invoice lifecycle, allocation, and retrieval."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

InvoiceStatus = Literal["draft", "issued", "paid", "void", "cancelled"]


class InvoiceCreateRequest(BaseModel):
    """Payload to trigger invoice allocation for an approved order."""

    due_date: Optional[date] = Field(None, description="Optional payment due date; defaults to 30 days from issue")


class InvoiceResponse(BaseModel):
    """Detailed invoice record representation."""

    id: str
    business_id: str
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    customer_id: str
    customer_name: Optional[str] = None
    invoice_number: str
    status: InvoiceStatus
    amount_due: Decimal
    due_date: date
    pdf_storage_path: Optional[str] = None
    line_items_snapshot: Optional[List[dict]] = None
    customer_snapshot: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("amount_due", mode="before")
    @classmethod
    def round_amount(cls, v: Decimal) -> Decimal:
        return Decimal(str(v)).quantize(Decimal("0.01"))


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices for the business."""

    items: List[InvoiceResponse]
    total: int
    page: int
    page_size: int
