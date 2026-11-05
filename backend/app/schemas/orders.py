"""Order and order-item domain schemas with exact decimal calculations."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

OrderStatus = Literal["draft", "pending_approval", "approved", "rejected", "fulfilled", "cancelled"]


class OrderItemCreate(BaseModel):
    """Line item in order creation or update."""

    product_id: str = Field(..., description="Target product ID belonging to business")
    quantity: int = Field(..., ge=1, description="Quantity ordered (must be >= 1)")
    unit_price: Optional[Decimal] = Field(
        None, ge=Decimal("0.00"), description="Optional override price; if omitted, pulls catalog price"
    )

    @field_validator("unit_price", mode="before")
    @classmethod
    def round_currency(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v)).quantize(Decimal("0.01"))


class OrderItemResponse(BaseModel):
    """Line item representation."""

    id: str
    order_id: str
    product_id: str
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class OrderCreate(BaseModel):
    """Payload to create a new order."""

    customer_id: Optional[str] = Field(None, description="Optional customer ID belonging to business")
    notes: Optional[str] = Field(None, max_length=2000)
    items: List[OrderItemCreate] = Field(..., min_length=1, description="At least one line item is required")


class OrderUpdate(BaseModel):
    """Payload to update an existing draft order."""

    customer_id: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=2000)
    items: Optional[List[OrderItemCreate]] = Field(None, min_length=1)


class OrderActionRequest(BaseModel):
    """Payload for consequential order lifecycle changes."""

    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for status change")


class OrderResponse(BaseModel):
    """Complete order representation with line items."""

    id: str
    business_id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    tax: Decimal
    total_amount: Decimal
    notes: Optional[str] = None
    created_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    items: List[OrderResponse]
    total: int
    page: int
    page_size: int
