"""Pydantic schemas for AI-assisted order intake, product matching, and validation."""

from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class OrderIntakeRequest(BaseModel):
    """Payload containing raw pasted customer message for AI extraction."""

    message: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Raw customer message (e.g. from WhatsApp, SMS, or email)",
    )

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Customer message cannot be empty or whitespace only")
        return cleaned


class AIExtractedItem(BaseModel):
    """Candidate line item extracted by AI model."""

    candidate_product_name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., ge=1, le=10000, description="Quantity extracted (must be >= 1)")
    variant: Optional[str] = Field(None, max_length=100)
    raw_text: Optional[str] = Field(None, max_length=200)


class AIOrderExtractionOutput(BaseModel):
    """Strict schema-constrained output expected from the AI provider."""

    customer_name: Optional[str] = Field(None, max_length=200)
    delivery_instructions: Optional[str] = Field(None, max_length=500)
    items: List[AIExtractedItem] = Field(default_factory=list)
    notes: Optional[str] = Field(None, max_length=1000)
    ambiguities: List[str] = Field(default_factory=list)


class CandidateProductMatch(BaseModel):
    """Authoritative catalog product record matched from the database."""

    id: str
    name: str
    sku: str
    unit_price: Decimal
    quantity_on_hand: int
    is_low_stock: bool

    @field_validator("unit_price", mode="before")
    @classmethod
    def round_price(cls, v: Decimal) -> Decimal:
        return Decimal(str(v)).quantize(Decimal("0.01"))


class CandidateItemMatch(BaseModel):
    """Candidate line item after database catalog resolution and deterministic pricing."""

    candidate_product_name: str
    raw_text: Optional[str] = None
    quantity: int = Field(..., ge=1)
    variant: Optional[str] = None
    match_status: Literal["matched", "ambiguous", "unmatched"]
    matched_product: Optional[CandidateProductMatch] = None
    potential_matches: List[CandidateProductMatch] = Field(default_factory=list)
    unit_price: Optional[Decimal] = None
    line_total: Optional[Decimal] = None
    notes: Optional[str] = None

    @field_validator("unit_price", "line_total", mode="before")
    @classmethod
    def round_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v)).quantize(Decimal("0.01"))


class OrderIntakeResponse(BaseModel):
    """Complete candidate order proposal presented to operator for human review."""

    raw_message: str
    extracted_customer_name: Optional[str] = None
    matched_customer_id: Optional[str] = None
    matched_customer_name: Optional[str] = None
    delivery_instructions: Optional[str] = None
    items: List[CandidateItemMatch]
    subtotal: Decimal = Field(default=Decimal("0.00"))
    tax: Decimal = Field(default=Decimal("0.00"))
    total_amount: Decimal = Field(default=Decimal("0.00"))
    ambiguities: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    can_create_draft: bool = False

    @field_validator("subtotal", "tax", "total_amount", mode="before")
    @classmethod
    def round_totals(cls, v: Decimal) -> Decimal:
        return Decimal(str(v)).quantize(Decimal("0.01"))
