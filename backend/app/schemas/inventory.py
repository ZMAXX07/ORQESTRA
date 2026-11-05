"""Inventory and stock movement schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class InventoryItemResponse(BaseModel):
    """Real-time inventory levels for a product."""

    id: str
    business_id: str
    product_id: str
    product_name: str
    product_sku: str
    unit_price: Decimal
    quantity_on_hand: int
    reorder_threshold: int
    is_low_stock: bool
    updated_at: datetime


class InventoryListResponse(BaseModel):
    """Paginated list of inventory items with low-stock counts."""

    items: List[InventoryItemResponse]
    total: int
    page: int
    page_size: int
    total_low_stock: int


class StockAdjustmentRequest(BaseModel):
    """Payload for manual, authorized inventory adjustments with required reason."""

    product_id: str = Field(..., description="Target product ID")
    quantity_change: int = Field(..., description="Quantity delta (positive or negative, non-zero)")
    movement_type: Literal["adjustment", "restock", "return"] = Field(
        "adjustment", description="Classification of movement"
    )
    notes: str = Field(..., min_length=3, max_length=500, description="Mandatory reason for manual adjustment")

    @field_validator("quantity_change")
    @classmethod
    def validate_non_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Adjustment quantity change cannot be zero")
        return v

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("A clear reason (at least 3 characters) is required for stock adjustments")
        return v


class StockAdjustmentResponse(BaseModel):
    """Result of an atomic stock adjustment."""

    inventory_id: str
    product_id: str
    new_quantity: int
    movement_id: str
    quantity_change: int
    notes: str


class StockMovementResponse(BaseModel):
    """Immutable audit entry of an inventory level change."""

    id: str
    business_id: str
    product_id: str
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity_change: int
    movement_type: str
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime


class StockMovementListResponse(BaseModel):
    """Paginated list of stock movements."""

    items: List[StockMovementResponse]
    total: int
    page: int
    page_size: int
