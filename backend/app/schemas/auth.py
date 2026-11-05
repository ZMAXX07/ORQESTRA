"""Pydantic schemas for authentication and authorization."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

AppRole = Literal["owner", "admin", "staff"]


class AuthenticatedUser(BaseModel):
    """User identity extracted and verified from Supabase JWT."""

    user_id: str = Field(description="Unique Supabase Auth subject UUID")
    email: Optional[str] = Field(default=None, description="User email address if present in claims")
    role: Optional[str] = Field(default="authenticated", description="Supabase auth role claim")


class BusinessMembership(BaseModel):
    """Business membership record associating a user with a specific business role."""

    business_id: str = Field(description="Unique business UUID")
    business_name: str = Field(description="Display name of the business")
    role: AppRole = Field(description="Role assigned to user within this business")
    is_active: bool = Field(default=True, description="Whether membership is active")
    currency: Optional[str] = Field(default="USD", description="Business primary operating currency")


class AuthContextResponse(BaseModel):
    """Response schema proving verified server-side authentication and business access."""

    status: Literal["authenticated"] = "authenticated"
    user: AuthenticatedUser
    active_business: Optional[BusinessMembership] = None
    memberships: List[BusinessMembership] = Field(default_factory=list)
