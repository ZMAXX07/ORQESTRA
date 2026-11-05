"""Product domain schemas with strict decimal validation."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    """Payload to create a new product in a business."""

    sku: str = Field(..., min_length=1, max_length=100, description="Unique stock keeping unit")
    name: str = Field(..., min_length=1, max_length=255, description="Product title/name")
    description: Optional[str] = Field(None, max_length=2000)
    unit_price: Decimal = Field(..., ge=Decimal("0.00"), description="Selling price per unit")
    cost_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"), description="Cost price per unit")
    initial_stock: int = Field(0, ge=0, description="Initial quantity placed in inventory")
    reorder_threshold: int = Field(5, ge=0, description="Minimum threshold for low stock alert")

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("SKU cannot be empty or whitespace only")
        return v.upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Product name cannot be empty")
        return v

    @field_validator("unit_price", "cost_price", mode="before")
    @classmethod
    def round_currency(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v)).quantize(Decimal("0.01"))


class ProductUpdate(BaseModel):
    """Payload to update an existing product."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    cost_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    is_active: Optional[bool] = None

    @field_validator("unit_price", "cost_price", mode="before")
    @classmethod
    def round_currency(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v)).quantize(Decimal("0.01"))


class ProductResponse(BaseModel):
    """Serialized product representation."""

    id: str
    business_id: str
    sku: str
    name: str
    description: Optional[str] = None
    unit_price: Decimal
    cost_price: Optional[Decimal] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    quantity_on_hand: int = 0
    reorder_threshold: int = 5
    is_low_stock: bool = False


class ProductListResponse(BaseModel):
    """Paginated list of products."""

    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
