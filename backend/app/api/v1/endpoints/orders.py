"""Order lifecycle and transaction management endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from backend.app.api.deps import (
    get_customer_repository,
    get_order_repository,
    get_product_repository,
    get_current_user,
    require_business_role,
)
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.repositories.order_repository import BaseOrderRepository
from backend.app.repositories.product_repository import BaseProductRepository
from backend.app.schemas.auth import AuthenticatedUser, BusinessMembership
from backend.app.schemas.orders import (
    OrderActionRequest,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=OrderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Orders",
    description="Retrieve paginated orders for the business with status and customer filters.",
)
async def list_orders(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by order status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderListResponse:
    items, total = await order_repo.list_orders(
        business_id=membership.business_id,
        status=status_filter,
        customer_id=customer_id,
        page=page,
        page_size=page_size,
    )
    return OrderListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Order",
    description="Create a new draft order with validated line items and exact server-calculated decimal totals.",
)
async def create_order(
    order: OrderCreate,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> OrderResponse:
    try:
        created = await order_repo.create_order(
            business_id=membership.business_id,
            order=order,
            user_id=current_user.user_id,
            product_repo=product_repo,
            customer_repo=customer_repo,
        )
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Order Details",
    description="Retrieve order record with all associated line items and status.",
)
async def get_order(
    order_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    order = await order_repo.get_order(business_id=membership.business_id, order_id=order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.put(
    "/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Draft Order",
    description="Modify items, customer, or notes on an order currently in draft status.",
)
async def update_order(
    order_id: str,
    update: OrderUpdate,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
    product_repo: BaseProductRepository = Depends(get_product_repository),
) -> OrderResponse:
    try:
        updated = await order_repo.update_order(
            business_id=membership.business_id,
            order_id=order_id,
            update=update,
            user_id=current_user.user_id,
            product_repo=product_repo,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{order_id}/submit",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Order for Review",
    description="Transitions order status from draft to pending_approval.",
)
async def submit_order_for_review(
    order_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    try:
        submitted = await order_repo.submit_order_for_review(
            business_id=membership.business_id,
            order_id=order_id,
            user_id=current_user.user_id,
        )
        return submitted
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{order_id}/approve",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Order & Deduct Inventory",
    description="Atomically validates inventory stock for each line item and deducts stock. Requires admin or owner role.",
)
async def approve_order(
    order_id: str,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    try:
        approved = await order_repo.approve_order(
            business_id=membership.business_id,
            order_id=order_id,
            user_id=current_user.user_id,
        )
        return approved
    except ValueError as e:
        # Check if insufficient stock or invalid transition
        err_msg = str(e)
        if "already approved" in err_msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg) from e
        if "Insufficient stock" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval rejected: {err_msg}",
            ) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post(
    "/{order_id}/reject",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Order",
    description="Rejects an order pending approval with an optional reason. Requires admin or owner role.",
)
async def reject_order(
    order_id: str,
    action: Optional[OrderActionRequest] = None,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    reason = action.reason if action else None
    try:
        rejected = await order_repo.reject_order(
            business_id=membership.business_id,
            order_id=order_id,
            user_id=current_user.user_id,
            reason=reason,
        )
        return rejected
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Order",
    description="Cancels an order. If previously approved, restores inventory atomically with stock movement return record.",
)
async def cancel_order(
    order_id: str,
    action: Optional[OrderActionRequest] = None,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
) -> OrderResponse:
    reason = action.reason if action else None
    try:
        cancelled = await order_repo.cancel_order(
            business_id=membership.business_id,
            order_id=order_id,
            user_id=current_user.user_id,
            reason=reason,
        )
        return cancelled
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
