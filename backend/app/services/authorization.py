"""Business authorization and role-based access control service."""

import logging
from typing import Dict, List, Optional
from backend.app.repositories.business_repository import BaseBusinessRepository
from backend.app.schemas.auth import AppRole, AuthenticatedUser, BusinessMembership

logger = logging.getLogger("orqestra.authorization")

ROLE_HIERARCHY: Dict[AppRole, int] = {
    "owner": 3,
    "admin": 2,
    "staff": 1,
}


class AuthorizationError(Exception):
    """Exception raised when authorization or role permission check fails."""

    def __init__(self, message: str, code: str = "FORBIDDEN"):
        super().__init__(message)
        self.message = message
        self.code = code


class AuthorizationService:
    """Enforces business tenancy isolation and role permissions."""

    def __init__(self, repository: BaseBusinessRepository):
        self.repository = repository

    async def get_user_memberships(self, user: AuthenticatedUser) -> List[BusinessMembership]:
        """Retrieve all active business memberships for authenticated user."""
        return await self.repository.get_user_memberships(user.user_id)

    async def check_membership(
        self, user: AuthenticatedUser, business_id: str
    ) -> BusinessMembership:
        """Verify user is an active member of specified business.
        
        Prevents cross-tenant access. Never trusts client-provided business ID without verification.
        """
        if not business_id or not business_id.strip():
            raise AuthorizationError("Business ID is required", code="INVALID_BUSINESS_ID")

        membership = await self.repository.get_user_membership_for_business(
            user_id=user.user_id, business_id=business_id
        )

        if not membership or not membership.is_active:
            logger.warning(
                f"Access denied: User {user.user_id} is not an active member of business {business_id}"
            )
            raise AuthorizationError(
                "Access denied: you do not have permission to access this business",
                code="FORBIDDEN_BUSINESS_ACCESS",
            )

        return membership

    def enforce_role(
        self, membership: BusinessMembership, required_role: AppRole
    ) -> None:
        """Verify membership role meets or exceeds required permission level.
        
        Hierarchy: owner (3) > admin (2) > staff (1)
        """
        user_level = ROLE_HIERARCHY.get(membership.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)

        if user_level < required_level:
            logger.warning(
                f"Role escalation prevented: User has role '{membership.role}', required '{required_role}'"
            )
            raise AuthorizationError(
                f"Insufficient permissions: operation requires '{required_role}' role",
                code="INSUFFICIENT_ROLE_PERMISSIONS",
            )
