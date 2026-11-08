"""Authentication and authorization verification endpoints for API v1."""

from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from backend.app.api.deps import (
    get_authorization_service,
    get_current_user,
    require_business_role,
)
from backend.app.schemas.auth import (
    AuthContextResponse,
    AuthenticatedUser,
    BusinessMembership,
)
from backend.app.services.authorization import AuthorizationService

router = APIRouter()


@router.get(
    "/me",
    response_model=AuthContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticated User & Memberships Context",
    description=(
        "Verifies the Supabase JWT bearer token signature and returns the authenticated "
        "user identity alongside all confirmed business memberships."
    ),
)
async def get_auth_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    auth_service: AuthorizationService = Depends(get_authorization_service),
    x_business_id: Optional[str] = Header(None, alias="X-Business-ID"),
) -> AuthContextResponse:
    """Return verified identity and business memberships."""
    memberships = await auth_service.get_user_memberships(current_user)
    active_business = None
    if x_business_id:
        for m in memberships:
            if m.business_id == x_business_id:
                active_business = m
                break
    if not active_business:
        active_business = memberships[0] if memberships else None

    return AuthContextResponse(
        status="authenticated",
        user=current_user,
        active_business=active_business,
        memberships=memberships,
    )


@router.get(
    "/business-context",
    response_model=BusinessMembership,
    status_code=status.HTTP_200_OK,
    summary="Verify Business Membership Access",
    description=(
        "Requires authenticated user and valid membership in the business passed in X-Business-ID. "
        "Returns 401 if unauthenticated and 403 if user lacks access to the business."
    ),
)
async def verify_business_access(
    membership: BusinessMembership = Depends(require_business_role("staff")),
) -> BusinessMembership:
    """Prove business-level tenant isolation is enforced on server."""
    return membership


@router.get(
    "/admin-check",
    response_model=BusinessMembership,
    status_code=status.HTTP_200_OK,
    summary="Verify Admin/Owner Permission",
    description=(
        "Requires authenticated user with admin or owner role in the business passed in X-Business-ID. "
        "Returns 403 for staff members."
    ),
)
async def verify_admin_access(
    membership: BusinessMembership = Depends(require_business_role("admin")),
) -> BusinessMembership:
    """Prove role hierarchy (owner/admin vs staff) is enforced on server."""
    return membership
