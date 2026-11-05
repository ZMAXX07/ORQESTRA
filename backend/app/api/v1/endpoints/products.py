"""Product management endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.api.deps import (
    get_audit_repository,
    get_current_user,
    get_product_repository,
    require_business_role,
)
from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.repositories.product_repository import BaseProductRepository
from backend.app.schemas.auth import AuthenticatedUser, BusinessMembership
from backend.app.schemas.products import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Products",
    description="Retrieve paginated product catalog for the business with optional search and active status filter.",
)
async def list_products(
    search: Optional[str] = Query(None, description="Search by product name or SKU"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    product_repo: BaseProductRepository = Depends(get_product_repository),
) -> ProductListResponse:
    items, total = await product_repo.list_products(
        business_id=membership.business_id,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Register a new product in the business catalog and establish initial inventory level.",
)
async def create_product(
    product: ProductCreate,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> ProductResponse:
    try:
        created = await product_repo.create_product(
            business_id=membership.business_id,
            product=product,
            user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="product.created",
        entity_type="products",
        entity_id=created.id,
        new_values={"sku": created.sku, "name": created.name, "unit_price": str(created.unit_price)},
    )
    return created


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Product",
    description="Retrieve a single product by ID belonging to the business.",
)
async def get_product(
    product_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    product_repo: BaseProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    prod = await product_repo.get_product(
        business_id=membership.business_id, product_id=product_id
    )
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return prod


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Product",
    description="Update product attributes (name, description, unit price, cost price, active state).",
)
async def update_product(
    product_id: str,
    update: ProductUpdate,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> ProductResponse:
    updated = await product_repo.update_product(
        business_id=membership.business_id,
        product_id=product_id,
        update=update,
        user_id=current_user.user_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="product.updated",
        entity_type="products",
        entity_id=product_id,
        new_values=update.model_dump(exclude_unset=True, mode="json"),
    )
    return updated


@router.patch(
    "/{product_id}/deactivate",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Product",
    description="Soft-deactivates product rather than deleting historical references.",
)
async def deactivate_product(
    product_id: str,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> ProductResponse:
    deactivated = await product_repo.deactivate_product(
        business_id=membership.business_id,
        product_id=product_id,
        user_id=current_user.user_id,
    )
    if not deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    await audit_repo.log_event(
        business_id=membership.business_id,
        user_id=current_user.user_id,
        action="product.deactivated",
        entity_type="products",
        entity_id=product_id,
        new_values={"is_active": False},
    )
    return deactivated
