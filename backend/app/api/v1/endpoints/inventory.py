"""Inventory and stock movement endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.api.deps import (
    get_current_user,
    get_inventory_repository,
    require_business_role,
)
from backend.app.repositories.inventory_repository import BaseInventoryRepository
from backend.app.schemas.auth import AuthenticatedUser, BusinessMembership
from backend.app.schemas.inventory import (
    InventoryListResponse,
    StockAdjustmentRequest,
    StockAdjustmentResponse,
    StockMovementListResponse,
)

router = APIRouter()


@router.get(
    "",
    response_model=InventoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Inventory Levels",
    description="Retrieve current real-time stock levels, reorder thresholds, and low-stock indicators.",
)
async def list_inventory(
    search: Optional[str] = Query(None, description="Search by product name or SKU"),
    low_stock_only: bool = Query(False, description="Filter only items at or below reorder threshold"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    inventory_repo: BaseInventoryRepository = Depends(get_inventory_repository),
) -> InventoryListResponse:
    items, total, total_low_stock = await inventory_repo.list_inventory(
        business_id=membership.business_id,
        search=search,
        low_stock_only=low_stock_only,
        page=page,
        page_size=page_size,
    )
    return InventoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_low_stock=total_low_stock,
    )


@router.post(
    "/adjust",
    response_model=StockAdjustmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Adjust Stock Level",
    description="Execute an authorized, atomic manual stock adjustment with mandatory audit reason.",
)
async def adjust_stock(
    adjustment: StockAdjustmentRequest,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    inventory_repo: BaseInventoryRepository = Depends(get_inventory_repository),
) -> StockAdjustmentResponse:
    try:
        result = await inventory_repo.adjust_stock(
            business_id=membership.business_id,
            request=adjustment,
            user_id=current_user.user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/history",
    response_model=StockMovementListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Stock Movements",
    description="Retrieve the immutable audit history of inventory adjustments, initial stocks, and fulfillment deductions.",
)
async def list_stock_movements(
    product_id: Optional[str] = Query(None, description="Filter movements by product ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    inventory_repo: BaseInventoryRepository = Depends(get_inventory_repository),
) -> StockMovementListResponse:
    items, total = await inventory_repo.list_movements(
        business_id=membership.business_id,
        product_id=product_id,
        page=page,
        page_size=page_size,
    )
    return StockMovementListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
