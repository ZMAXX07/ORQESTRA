"""Customer management endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.api.deps import (
    get_audit_repository,
    get_customer_repository,
    get_current_user,
    require_business_role,
)
from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.schemas.auth import AuthenticatedUser, BusinessMembership
from backend.app.schemas.customers import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=CustomerListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Customers",
    description="Retrieve business customer directory with search and active status filters.",
)
async def list_customers(
    search: Optional[str] = Query(None, description="Search by customer name, email, or phone"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> CustomerListResponse:
    items, total = await customer_repo.list_customers(
        business_id=membership.business_id,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer",
    description="Add a new customer to the business directory.",
)
async def create_customer(
    customer: CustomerCreate,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> CustomerResponse:
    created = await customer_repo.create_customer(
        business_id=membership.business_id,
        customer=customer,
        user_id=current_user.user_id,
    )
    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="customer.created",
        entity_type="customers",
        entity_id=created.id,
        new_values={"name": created.name, "email": created.email},
    )
    return created


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Customer",
    description="Retrieve a single customer by ID belonging to the business.",
)
async def get_customer(
    customer_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> CustomerResponse:
    cust = await customer_repo.get_customer(
        business_id=membership.business_id, customer_id=customer_id
    )
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return cust


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Customer",
    description="Update customer details (name, email, phone, address, notes, active status).",
)
async def update_customer(
    customer_id: str,
    update: CustomerUpdate,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> CustomerResponse:
    updated = await customer_repo.update_customer(
        business_id=membership.business_id,
        customer_id=customer_id,
        update=update,
        user_id=current_user.user_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="customer.updated",
        entity_type="customers",
        entity_id=customer_id,
        new_values=update.model_dump(exclude_unset=True, mode="json"),
    )
    return updated


@router.patch(
    "/{customer_id}/deactivate",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Customer",
    description="Soft-deactivates customer rather than deleting historical transaction records.",
)
async def deactivate_customer(
    customer_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> CustomerResponse:
    deactivated = await customer_repo.deactivate_customer(
        business_id=membership.business_id,
        customer_id=customer_id,
        user_id=current_user.user_id,
    )
    if not deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="customer.deactivated",
        entity_type="customers",
        entity_id=customer_id,
        new_values={"is_active": False},
    )
    return deactivated
