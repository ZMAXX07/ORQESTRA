"""Invoice management and PDF document generation endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import Response

from backend.app.api.deps import (
    get_audit_repository,
    get_business_repository,
    get_current_user,
    get_customer_repository,
    get_invoice_repository,
    get_order_repository,
    require_business_role,
)
from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.repositories.business_repository import BaseBusinessRepository
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.repositories.invoice_repository import BaseInvoiceRepository
from backend.app.repositories.order_repository import BaseOrderRepository
from backend.app.schemas.auth import AuthenticatedUser, BusinessMembership
from backend.app.schemas.invoices import (
    InvoiceCreateRequest,
    InvoiceListResponse,
    InvoiceResponse,
)
from backend.app.services.invoice_pdf import generate_invoice_pdf_bytes

router = APIRouter()


@router.get(
    "",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Invoices",
    description="Retrieve paginated list of issued and draft invoices for the business.",
)
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    invoice_repo: BaseInvoiceRepository = Depends(get_invoice_repository),
) -> InvoiceListResponse:
    items, total = await invoice_repo.list_invoices(
        business_id=membership.business_id,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Invoice Details",
    description="Retrieve invoice record verifying business tenant boundary.",
)
async def get_invoice(
    invoice_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    invoice_repo: BaseInvoiceRepository = Depends(get_invoice_repository),
) -> InvoiceResponse:
    inv = await invoice_repo.get_invoice(
        business_id=membership.business_id,
        invoice_id=invoice_id,
    )
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return inv


@router.post(
    "/orders/{order_id}/allocate",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate Invoice for Order",
    description="Atomically sequence, allocate, and persist an invoice for an approved order. Requires admin role.",
)
async def allocate_order_invoice(
    order_id: str,
    request: Optional[InvoiceCreateRequest] = None,
    membership: BusinessMembership = Depends(require_business_role("admin")),
    current_user: AuthenticatedUser = Depends(get_current_user),
    invoice_repo: BaseInvoiceRepository = Depends(get_invoice_repository),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> InvoiceResponse:
    due_date = request.due_date if request else None
    try:
        inv = await invoice_repo.allocate_invoice(
            business_id=membership.business_id,
            order_id=order_id,
            user_id=current_user.user_id,
            order_repo=order_repo,
            audit_repo=audit_repo,
            due_date=due_date,
            customer_repo=customer_repo,
        )
        return inv
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/{invoice_id}/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download Invoice PDF",
    description="Generate and download a verifiable invoice PDF from authoritative persisted records.",
)
async def download_invoice_pdf(
    invoice_id: str,
    membership: BusinessMembership = Depends(require_business_role("staff")),
    invoice_repo: BaseInvoiceRepository = Depends(get_invoice_repository),
    order_repo: BaseOrderRepository = Depends(get_order_repository),
    business_repo: BaseBusinessRepository = Depends(get_business_repository),
    customer_repo: BaseCustomerRepository = Depends(get_customer_repository),
) -> Response:
    # 1. Retrieve invoice verifying tenant boundary
    inv = await invoice_repo.get_invoice(
        business_id=membership.business_id,
        invoice_id=invoice_id,
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if not inv.order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice has no associated order record")

    # 2. Retrieve authoritative order record
    order = await order_repo.get_order(
        business_id=membership.business_id,
        order_id=inv.order_id,
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated order record not found")

    # 3. Retrieve customer details
    customer_dict = None
    if inv.customer_id:
        cust = await customer_repo.get_customer(
            business_id=membership.business_id,
            customer_id=inv.customer_id,
        )
        if cust:
            customer_dict = {
                "name": cust.name,
                "email": cust.email,
                "phone": cust.phone,
                "address": cust.address,
            }

    # 4. Generate in-memory PDF bytes
    pdf_bytes = generate_invoice_pdf_bytes(
        invoice=inv,
        order=order,
        business_name=membership.business_name,
        business_details={"currency": getattr(membership, "currency", "USD") or "USD"},
        customer_details=customer_dict,
    )

    filename = f"invoice-{inv.invoice_number}.pdf"

    # 5. Safe download headers protecting file paths and sensitive caches
    headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(pdf_bytes)),
        "Cache-Control": "private, no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )
