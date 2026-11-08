"""Invoice repository abstractions and implementations for atomic allocation and querying."""

import asyncio
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.repositories.order_repository import BaseOrderRepository
from backend.app.schemas.invoices import InvoiceResponse


class BaseInvoiceRepository(ABC):
    """Abstract interface defining invoice data persistence and queries."""

    @abstractmethod
    async def allocate_invoice(
        self,
        business_id: str,
        order_id: str,
        user_id: str,
        order_repo: BaseOrderRepository,
        audit_repo: Optional[BaseAuditLogRepository] = None,
        due_date: Optional[date] = None,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> InvoiceResponse:
        """Atomically sequence, allocate, and persist an invoice for an approved order."""
        pass

    @abstractmethod
    async def get_invoice(
        self,
        business_id: str,
        invoice_id: str,
    ) -> Optional[InvoiceResponse]:
        """Retrieve an invoice by ID verifying tenant boundary."""
        pass

    @abstractmethod
    async def get_invoice_by_order(
        self,
        business_id: str,
        order_id: str,
    ) -> Optional[InvoiceResponse]:
        """Retrieve existing invoice associated with an order."""
        pass

    @abstractmethod
    async def list_invoices(
        self,
        business_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InvoiceResponse], int]:
        """List paginated invoices for a business."""
        pass


class InMemoryInvoiceRepository(BaseInvoiceRepository):
    """Thread-safe in-memory invoice repository for development and isolated testing."""

    def __init__(self) -> None:
        self._invoices: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def allocate_invoice(
        self,
        business_id: str,
        order_id: str,
        user_id: str,
        order_repo: BaseOrderRepository,
        audit_repo: Optional[BaseAuditLogRepository] = None,
        due_date: Optional[date] = None,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> InvoiceResponse:
        async with self._lock:
            # 1. Check idempotency: if invoice already exists for this order, return it
            for inv in self._invoices.values():
                if inv["business_id"] == business_id and inv["order_id"] == order_id:
                    return self._to_schema(inv)

            # 2. Retrieve order and verify tenancy and status
            order = await order_repo.get_order(business_id=business_id, order_id=order_id)
            if not order:
                raise ValueError(f"Order {order_id} does not exist in business {business_id}")

            if order.status not in ("approved", "fulfilled"):
                raise ValueError(
                    f"Invoices can only be issued for approved or fulfilled orders (current status: {order.status})"
                )

            if not order.customer_id:
                raise ValueError(f"Order {order_id} has no customer reference; required for invoice issuance")

            now = datetime.now(timezone.utc)
            year_month = now.strftime("%Y%m")
            prefix = f"INV-{year_month}-"

            # 3. Calculate sequence number for this business & prefix under lock
            existing_seqs = [
                int(inv["invoice_number"].replace(prefix, ""))
                for inv in self._invoices.values()
                if inv["business_id"] == business_id and inv["invoice_number"].startswith(prefix)
            ]
            next_seq = max(existing_seqs, default=0) + 1
            invoice_number = f"{prefix}{next_seq:04d}"

            final_due_date = due_date or date.fromtimestamp(now.timestamp() + 30 * 86400)
            inv_id = f"inv-{len(self._invoices) + 1:04d}-{now.strftime('%H%M%S')}"

            # Capture immutable line items snapshot
            line_items_snapshot = [
                {
                    "product_id": it.product_id,
                    "product_name": it.product_name,
                    "product_sku": it.product_sku,
                    "quantity": it.quantity,
                    "unit_price": str(it.unit_price),
                    "line_total": str(it.total_price),
                    "total_price": str(it.total_price),
                }
                for it in order.items
            ]

            # Capture immutable customer contact snapshot
            cust_dict = {"id": order.customer_id, "name": order.customer_name}
            if customer_repo and order.customer_id:
                cust_record = await customer_repo.get_customer(business_id, order.customer_id)
                if cust_record:
                    cust_dict = {
                        "id": cust_record.id,
                        "name": cust_record.name,
                        "email": cust_record.email,
                        "phone": cust_record.phone,
                        "address": cust_record.address,
                    }

            invoice_record: Dict[str, Any] = {
                "id": inv_id,
                "business_id": business_id,
                "order_id": order_id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "customer_name": order.customer_name,
                "invoice_number": invoice_number,
                "status": "issued",
                "amount_due": order.total_amount,
                "due_date": final_due_date,
                "pdf_storage_path": None,
                "line_items_snapshot": line_items_snapshot,
                "customer_snapshot": cust_dict,
                "created_at": now,
                "updated_at": now,
            }

            self._invoices[inv_id] = invoice_record

            if audit_repo:
                await audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="invoice.issued",
                    entity_type="invoice",
                    entity_id=inv_id,
                    new_values={
                        "invoice_number": invoice_number,
                        "order_id": order_id,
                        "amount_due": str(order.total_amount),
                    },
                )

            return self._to_schema(invoice_record)

    async def get_invoice(
        self,
        business_id: str,
        invoice_id: str,
    ) -> Optional[InvoiceResponse]:
        async with self._lock:
            record = self._invoices.get(invoice_id)
            if not record or record["business_id"] != business_id:
                return None
            return self._to_schema(record)

    async def get_invoice_by_order(
        self,
        business_id: str,
        order_id: str,
    ) -> Optional[InvoiceResponse]:
        async with self._lock:
            for inv in self._invoices.values():
                if inv["business_id"] == business_id and inv["order_id"] == order_id:
                    return self._to_schema(inv)
            return None

    async def list_invoices(
        self,
        business_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InvoiceResponse], int]:
        async with self._lock:
            matching = [
                inv for inv in self._invoices.values()
                if inv["business_id"] == business_id
            ]
            matching.sort(key=lambda x: x["created_at"], reverse=True)
            total = len(matching)
            start = (page - 1) * page_size
            end = start + page_size
            page_items = matching[start:end]
            return [self._to_schema(i) for i in page_items], total

    def _to_schema(self, r: Dict[str, Any]) -> InvoiceResponse:
        return InvoiceResponse(
            id=r["id"],
            business_id=r["business_id"],
            order_id=r.get("order_id"),
            order_number=r.get("order_number"),
            customer_id=r["customer_id"],
            customer_name=r.get("customer_name"),
            invoice_number=r["invoice_number"],
            status=r["status"],
            amount_due=Decimal(str(r["amount_due"])).quantize(Decimal("0.01")),
            due_date=r["due_date"] if isinstance(r["due_date"], date) else date.fromisoformat(str(r["due_date"])),
            pdf_storage_path=r.get("pdf_storage_path"),
            line_items_snapshot=r.get("line_items_snapshot"),
            customer_snapshot=r.get("customer_snapshot"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )


class SupabaseInvoiceRepository(BaseInvoiceRepository):
    """Database-backed invoice repository executing atomic stored procedures on Supabase."""

    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    async def allocate_invoice(
        self,
        business_id: str,
        order_id: str,
        user_id: str,
        order_repo: BaseOrderRepository,
        audit_repo: Optional[BaseAuditLogRepository] = None,
        due_date: Optional[date] = None,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> InvoiceResponse:
        rpc_url = f"{self.supabase_url}/rest/v1/rpc/allocate_invoice_atomic"
        payload = {
            "p_business_id": business_id,
            "p_order_id": order_id,
            "p_user_id": user_id,
            "p_due_date": due_date.isoformat() if due_date else None,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(rpc_url, headers=self.headers, json=payload)
            if resp.status_code != 200:
                err_detail = resp.text
                if "Order" in err_detail and "does not exist" in err_detail:
                    raise ValueError(f"Order {order_id} does not exist in business {business_id}")
                if "Invoices can only be issued" in err_detail:
                    raise ValueError("Invoices can only be issued for approved or fulfilled orders")
                raise RuntimeError(f"Database invoice allocation failed: {err_detail}")

            data = resp.json()
            # Fetch additional order and customer details if needed
            order = await order_repo.get_order(business_id=business_id, order_id=order_id)
            return InvoiceResponse(
                id=data["id"],
                business_id=data["business_id"],
                order_id=data.get("order_id"),
                order_number=order.order_number if order else None,
                customer_id=data["customer_id"],
                customer_name=order.customer_name if order else None,
                invoice_number=data["invoice_number"],
                status=data["status"],
                amount_due=Decimal(str(data["amount_due"])).quantize(Decimal("0.01")),
                due_date=date.fromisoformat(str(data["due_date"])),
                pdf_storage_path=data.get("pdf_storage_path"),
                line_items_snapshot=data.get("line_items_snapshot"),
                customer_snapshot=data.get("customer_snapshot"),
                created_at=datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(str(data["updated_at"]).replace("Z", "+00:00")),
            )

    async def get_invoice(
        self,
        business_id: str,
        invoice_id: str,
    ) -> Optional[InvoiceResponse]:
        query_url = (
            f"{self.supabase_url}/rest/v1/invoices?"
            f"id=eq.{invoice_id}&business_id=eq.{business_id}&select=*"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(query_url, headers=self.headers)
            if resp.status_code != 200:
                return None
            records = resp.json()
            if not records:
                return None
            r = records[0]
            return InvoiceResponse(
                id=r["id"],
                business_id=r["business_id"],
                order_id=r.get("order_id"),
                customer_id=r["customer_id"],
                invoice_number=r["invoice_number"],
                status=r["status"],
                amount_due=Decimal(str(r["amount_due"])).quantize(Decimal("0.01")),
                due_date=date.fromisoformat(str(r["due_date"])),
                pdf_storage_path=r.get("pdf_storage_path"),
                line_items_snapshot=r.get("line_items_snapshot"),
                customer_snapshot=r.get("customer_snapshot"),
                created_at=datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(str(r["updated_at"]).replace("Z", "+00:00")),
            )

    async def get_invoice_by_order(
        self,
        business_id: str,
        order_id: str,
    ) -> Optional[InvoiceResponse]:
        query_url = (
            f"{self.supabase_url}/rest/v1/invoices?"
            f"order_id=eq.{order_id}&business_id=eq.{business_id}&select=*"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(query_url, headers=self.headers)
            if resp.status_code != 200:
                return None
            records = resp.json()
            if not records:
                return None
            r = records[0]
            return InvoiceResponse(
                id=r["id"],
                business_id=r["business_id"],
                order_id=r.get("order_id"),
                customer_id=r["customer_id"],
                invoice_number=r["invoice_number"],
                status=r["status"],
                amount_due=Decimal(str(r["amount_due"])).quantize(Decimal("0.01")),
                due_date=date.fromisoformat(str(r["due_date"])),
                pdf_storage_path=r.get("pdf_storage_path"),
                line_items_snapshot=r.get("line_items_snapshot"),
                customer_snapshot=r.get("customer_snapshot"),
                created_at=datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(str(r["updated_at"]).replace("Z", "+00:00")),
            )

    async def list_invoices(
        self,
        business_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InvoiceResponse], int]:
        offset = (page - 1) * page_size
        query_url = (
            f"{self.supabase_url}/rest/v1/invoices?"
            f"business_id=eq.{business_id}&order=created_at.desc&limit={page_size}&offset={offset}"
        )
        headers = {**self.headers, "Prefer": "count=exact"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(query_url, headers=headers)
            if resp.status_code not in (200, 206):
                return [], 0
            records = resp.json()
            content_range = resp.headers.get("Content-Range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(records)
            items = [
                InvoiceResponse(
                    id=r["id"],
                    business_id=r["business_id"],
                    order_id=r.get("order_id"),
                    customer_id=r["customer_id"],
                    invoice_number=r["invoice_number"],
                    status=r["status"],
                    amount_due=Decimal(str(r["amount_due"])).quantize(Decimal("0.01")),
                    due_date=date.fromisoformat(str(r["due_date"])),
                    pdf_storage_path=r.get("pdf_storage_path"),
                    line_items_snapshot=r.get("line_items_snapshot"),
                    customer_snapshot=r.get("customer_snapshot"),
                    created_at=datetime.fromisoformat(str(r["created_at"]).replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(str(r["updated_at"]).replace("Z", "+00:00")),
                )
                for r in records
            ]
            return items, total
