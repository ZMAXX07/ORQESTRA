"""Customer directory domain schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CustomerCreate(BaseModel):
    """Payload to register a new customer."""

    name: str = Field(..., min_length=1, max_length=255, description="Customer or company name")
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Customer name cannot be empty")
        return v

    @field_validator("email", "phone", "address", "notes")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class CustomerUpdate(BaseModel):
    """Payload to update an existing customer."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None

    @field_validator("name", "email", "phone", "address", "notes")
    @classmethod
    def strip_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None


class CustomerResponse(BaseModel):
    """Customer representation."""

    id: str
    business_id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    """Paginated list of customers."""

    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int
