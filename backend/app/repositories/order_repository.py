"""Order repository interface and implementations with transaction-safe stock operations."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.repositories.customer_repository import BaseCustomerRepository
from backend.app.repositories.product_repository import BaseProductRepository
from backend.app.schemas.orders import (
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
    OrderStatus,
    OrderUpdate,
)

logger = logging.getLogger("orqestra.orders")


class BaseOrderRepository(ABC):
    """Abstract interface for order operations."""

    @abstractmethod
    async def list_orders(
        self,
        business_id: str,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[OrderResponse], int]:
        pass

    @abstractmethod
    async def get_order(self, business_id: str, order_id: str) -> Optional[OrderResponse]:
        pass

    @abstractmethod
    async def create_order(
        self,
        business_id: str,
        order: OrderCreate,
        user_id: str,
        product_repo: BaseProductRepository,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> OrderResponse:
        pass

    @abstractmethod
    async def update_order(
        self,
        business_id: str,
        order_id: str,
        update: OrderUpdate,
        user_id: str,
        product_repo: BaseProductRepository,
    ) -> Optional[OrderResponse]:
        pass

    @abstractmethod
    async def submit_order_for_review(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        pass

    @abstractmethod
    async def approve_order(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        pass

    @abstractmethod
    async def reject_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        pass

    @abstractmethod
    async def cancel_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        pass

    @abstractmethod
    async def product_has_orders(self, business_id: str, product_id: str) -> bool:
        """Check if a product is referenced by any order items in the business."""
        pass


class InMemoryOrderRepository(BaseOrderRepository):
    """In-memory order repository with atomic transaction locks, stock deduction, and rollback."""

    def __init__(
        self,
        product_repo: Optional[BaseProductRepository] = None,
        audit_repo: Optional[BaseAuditLogRepository] = None,
    ):
        self.product_repo = product_repo
        self.audit_repo = audit_repo
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._order_items: Dict[str, List[Dict[str, Any]]] = {}  # keyed by order_id
        self._order_seq = 1000
        self._lock = asyncio.Lock()

    def _to_response(
        self,
        o: Dict[str, Any],
        customer_name: Optional[str] = None,
    ) -> OrderResponse:
        items_raw = self._order_items.get(o["id"], [])
        items = [
            OrderItemResponse(
                id=it["id"],
                order_id=o["id"],
                product_id=it["product_id"],
                product_name=it["product_name"],
                product_sku=it["product_sku"],
                quantity=it["quantity"],
                unit_price=Decimal(str(it["unit_price"])),
                total_price=Decimal(str(it["total_price"])),
            )
            for it in items_raw
        ]
        return OrderResponse(
            id=o["id"],
            business_id=o["business_id"],
            customer_id=o.get("customer_id"),
            customer_name=customer_name or o.get("customer_name"),
            order_number=o["order_number"],
            status=o["status"],
            subtotal=Decimal(str(o["subtotal"])),
            tax=Decimal(str(o["tax"])),
            total_amount=Decimal(str(o["total_amount"])),
            notes=o.get("notes"),
            created_by=o.get("created_by"),
            approved_by=o.get("approved_by"),
            approved_at=o.get("approved_at"),
            created_at=o["created_at"],
            updated_at=o["updated_at"],
            items=items,
        )

    async def list_orders(
        self,
        business_id: str,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[OrderResponse], int]:
        async with self._lock:
            results = []
            for o in self._orders.values():
                if o["business_id"] != business_id:
                    continue
                if status and o["status"] != status:
                    continue
                if customer_id and o.get("customer_id") != customer_id:
                    continue
                results.append(self._to_response(o))

            results.sort(key=lambda x: x.created_at, reverse=True)
            total = len(results)
            start = (page - 1) * page_size
            return results[start : start + page_size], total

    async def get_order(self, business_id: str, order_id: str) -> Optional[OrderResponse]:
        async with self._lock:
            o = self._orders.get(order_id)
            if o and o["business_id"] == business_id:
                return self._to_response(o)
            return None

    async def create_order(
        self,
        business_id: str,
        order: OrderCreate,
        user_id: str,
        product_repo: BaseProductRepository,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> OrderResponse:
        async with self._lock:
            # 1. Validate customer if provided
            cust_name = None
            if order.customer_id and customer_repo:
                cust = await customer_repo.get_customer(business_id, order.customer_id)
                if not cust:
                    raise ValueError(f"Customer {order.customer_id} does not exist in this business")
                cust_name = cust.name

            # 2. Validate line items and calculate totals with exact decimal arithmetic
            subtotal = Decimal("0.00")
            validated_items = []

            for it in order.items:
                product = await product_repo.get_product(business_id, it.product_id)
                if not product or product.business_id != business_id:
                    raise ValueError(
                        f"Product {it.product_id} not found or does not belong to this business"
                    )
                if not product.is_active:
                    raise ValueError(f"Product '{product.name}' is inactive and cannot be ordered")

                unit_price = it.unit_price if it.unit_price is not None else product.unit_price
                unit_price = Decimal(str(unit_price)).quantize(Decimal("0.01"))
                line_total = (Decimal(it.quantity) * unit_price).quantize(Decimal("0.01"))
                subtotal += line_total

                validated_items.append({
                    "id": str(uuid.uuid4()),
                    "product_id": it.product_id,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "quantity": it.quantity,
                    "unit_price": unit_price,
                    "total_price": line_total,
                })

            tax = Decimal("0.00")
            total_amount = subtotal + tax

            self._order_seq += 1
            now = datetime.now(timezone.utc)
            order_id = str(uuid.uuid4())
            order_number = f"ORD-{now.strftime('%Y%m')}-{self._order_seq}"

            order_record = {
                "id": order_id,
                "business_id": business_id,
                "customer_id": order.customer_id,
                "customer_name": cust_name,
                "order_number": order_number,
                "status": "draft",
                "subtotal": subtotal,
                "tax": tax,
                "total_amount": total_amount,
                "notes": order.notes,
                "created_by": user_id,
                "approved_by": None,
                "approved_at": None,
                "created_at": now,
                "updated_at": now,
            }

            self._orders[order_id] = order_record
            self._order_items[order_id] = validated_items

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="order.created",
                    entity_type="orders",
                    entity_id=order_id,
                    new_values={
                        "order_number": order_number,
                        "status": "draft",
                        "total_amount": str(total_amount),
                        "items_count": len(validated_items),
                    },
                )

            return self._to_response(order_record, customer_name=cust_name)

    async def update_order(
        self,
        business_id: str,
        order_id: str,
        update: OrderUpdate,
        user_id: str,
        product_repo: BaseProductRepository,
    ) -> Optional[OrderResponse]:
        async with self._lock:
            o = self._orders.get(order_id)
            if not o or o["business_id"] != business_id:
                return None

            if o["status"] != "draft":
                raise ValueError(
                    f"Only draft orders can be edited. Current order status is '{o['status']}'."
                )

            if update.customer_id is not None:
                o["customer_id"] = update.customer_id
            if update.notes is not None:
                o["notes"] = update.notes

            if update.items is not None:
                subtotal = Decimal("0.00")
                validated_items = []
                for it in update.items:
                    product = await product_repo.get_product(business_id, it.product_id)
                    if not product or product.business_id != business_id:
                        raise ValueError(f"Product {it.product_id} not found in this business")
                    unit_price = it.unit_price if it.unit_price is not None else product.unit_price
                    unit_price = Decimal(str(unit_price)).quantize(Decimal("0.01"))
                    line_total = (Decimal(it.quantity) * unit_price).quantize(Decimal("0.01"))
                    subtotal += line_total
                    validated_items.append({
                        "id": str(uuid.uuid4()),
                        "product_id": it.product_id,
                        "product_name": product.name,
                        "product_sku": product.sku,
                        "quantity": it.quantity,
                        "unit_price": unit_price,
                        "total_price": line_total,
                    })

                o["subtotal"] = subtotal
                o["total_amount"] = subtotal + o["tax"]
                self._order_items[order_id] = validated_items

            o["updated_at"] = datetime.now(timezone.utc)
            return self._to_response(o)

    async def submit_order_for_review(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        async with self._lock:
            o = self._orders.get(order_id)
            if not o or o["business_id"] != business_id:
                raise ValueError("Order not found")

            if o["status"] != "draft":
                raise ValueError(
                    f"Order cannot be submitted for review from status '{o['status']}'. Must be 'draft'."
                )

            o["status"] = "pending_approval"
            o["updated_at"] = datetime.now(timezone.utc)

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="order.submitted",
                    entity_type="orders",
                    entity_id=order_id,
                    old_values={"status": "draft"},
                    new_values={"status": "pending_approval"},
                )

            return self._to_response(o)

    async def approve_order(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        """Atomic order approval and stock deduction.
        
        Guarantees zero overselling and rollback on failure.
        """
        async with self._lock:
            o = self._orders.get(order_id)
            if not o or o["business_id"] != business_id:
                raise ValueError("Order not found")

            if o["status"] == "approved":
                raise ValueError("Order is already approved. Cannot approve twice.")

            if o["status"] not in ("draft", "pending_approval"):
                raise ValueError(
                    f"Order cannot be approved from status '{o['status']}'. Must be 'draft' or 'pending_approval'."
                )

            if not self.product_repo:
                raise RuntimeError("Product repository required for inventory verification")

            inv_map = getattr(self.product_repo, "_inventory", {})
            prod_map = getattr(self.product_repo, "_products", {})
            movements = getattr(self.product_repo, "_movements", [])
            items = self._order_items.get(order_id, [])

            if not items:
                raise ValueError("Cannot approve order with no line items")

            # 1. ATOMIC VALIDATION: Check all items have sufficient stock BEFORE making any changes
            for it in items:
                prod_id = it["product_id"]
                inv = inv_map.get((business_id, prod_id))
                prod = prod_map.get(prod_id, {})
                prod_name = prod.get("name", "Product")

                if not inv:
                    raise ValueError(f"Inventory record missing for product '{prod_name}'")

                avail = inv.get("quantity_on_hand", 0)
                req = it["quantity"]
                if avail < req:
                    raise ValueError(
                        f"Insufficient stock for product '{prod_name}' (SKU: {prod.get('sku')}): requested {req}, available {avail}"
                    )

            # 2. ATOMIC EXECUTION: Deduct inventory and record stock movements
            now = datetime.now(timezone.utc)
            for it in items:
                prod_id = it["product_id"]
                inv = inv_map.get((business_id, prod_id))
                inv["quantity_on_hand"] -= it["quantity"]
                inv["updated_at"] = now

                movements.insert(0, {
                    "id": str(uuid.uuid4()),
                    "business_id": business_id,
                    "product_id": prod_id,
                    "quantity_change": -it["quantity"],
                    "movement_type": "order_fulfillment",
                    "reference_id": order_id,
                    "notes": f"Order {o['order_number']} approved",
                    "created_by": user_id,
                    "created_at": now,
                })

            old_status = o["status"]
            o["status"] = "approved"
            o["approved_by"] = user_id
            o["approved_at"] = now
            o["updated_at"] = now

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="order.approved",
                    entity_type="orders",
                    entity_id=order_id,
                    old_values={"status": old_status},
                    new_values={
                        "status": "approved",
                        "approved_by": user_id,
                        "items_deducted": len(items),
                    },
                )

            return self._to_response(o)

    async def reject_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        async with self._lock:
            o = self._orders.get(order_id)
            if not o or o["business_id"] != business_id:
                raise ValueError("Order not found")

            if o["status"] in ("approved", "fulfilled", "cancelled", "rejected"):
                raise ValueError(f"Cannot reject order with current status '{o['status']}'")

            old_status = o["status"]
            o["status"] = "rejected"
            o["updated_at"] = datetime.now(timezone.utc)

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="order.rejected",
                    entity_type="orders",
                    entity_id=order_id,
                    old_values={"status": old_status},
                    new_values={"status": "rejected", "reason": reason},
                )

            return self._to_response(o)

    async def cancel_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        async with self._lock:
            o = self._orders.get(order_id)
            if not o or o["business_id"] != business_id:
                raise ValueError("Order not found")

            if o["status"] in ("cancelled", "fulfilled"):
                raise ValueError(f"Order cannot be cancelled: current status is '{o['status']}'")

            was_approved = o["status"] == "approved"
            now = datetime.now(timezone.utc)

            # If order was approved, restore inventory
            if was_approved and self.product_repo:
                inv_map = getattr(self.product_repo, "_inventory", {})
                movements = getattr(self.product_repo, "_movements", [])
                items = self._order_items.get(order_id, [])

                for it in items:
                    prod_id = it["product_id"]
                    inv = inv_map.get((business_id, prod_id))
                    if inv:
                        inv["quantity_on_hand"] += it["quantity"]
                        inv["updated_at"] = now
                        movements.insert(0, {
                            "id": str(uuid.uuid4()),
                            "business_id": business_id,
                            "product_id": prod_id,
                            "quantity_change": it["quantity"],
                            "movement_type": "return",
                            "reference_id": order_id,
                            "notes": f"Order {o['order_number']} cancelled: {reason or 'Stock restored'}",
                            "created_by": user_id,
                            "created_at": now,
                        })

            old_status = o["status"]
            o["status"] = "cancelled"
            o["updated_at"] = now

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="order.cancelled",
                    entity_type="orders",
                    entity_id=order_id,
                    old_values={"status": old_status},
                    new_values={
                        "status": "cancelled",
                        "stock_restored": was_approved,
                        "reason": reason,
                    },
                )

            return self._to_response(o)

    async def product_has_orders(self, business_id: str, product_id: str) -> bool:
        async with self._lock:
            for order_id, items in self._order_items.items():
                order = self._orders.get(order_id)
                if order and order.get("business_id") == business_id:
                    for item in items:
                        if item.get("product_id") == product_id:
                            return True
            return False


class SupabaseOrderRepository(BaseOrderRepository):
    """Database-backed order repository using PostgREST and atomic RPC functions."""

    def __init__(self, supabase_url: str, service_role_key: str, timeout: float = 5.0):
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key
        self.timeout = timeout

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @staticmethod
    def _extract_dict(data: Any) -> Dict[str, Any]:
        """Safely extract nested dictionary whether PostgREST returns a dict or list."""
        if isinstance(data, list):
            return data[0] if data else {}
        if isinstance(data, dict):
            return data
        return {}

    async def list_orders(
        self,
        business_id: str,
        status: Optional[str] = None,
        customer_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[OrderResponse], int]:
        endpoint = f"{self.supabase_url}/rest/v1/orders"
        params = {
            "business_id": f"eq.{business_id}",
            "select": "*,customers(name),order_items(*,products(name,sku))",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if status:
            params["status"] = f"eq.{status}"
        if customer_id:
            params["customer_id"] = f"eq.{customer_id}"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to query orders: {resp.status_code}")
                return [], 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)

            items = []
            for row in data:
                cust = self._extract_dict(row.pop("customers", None))
                raw_items = row.pop("order_items", []) or []
                order_items = []
                for it in raw_items:
                    prod = self._extract_dict(it.pop("products", None))
                    order_items.append(
                        OrderItemResponse(
                            id=it["id"],
                            order_id=row["id"],
                            product_id=it["product_id"],
                            product_name=prod.get("name", "Product"),
                            product_sku=prod.get("sku", "SKU"),
                            quantity=it["quantity"],
                            unit_price=Decimal(str(it["unit_price"])),
                            total_price=Decimal(str(it["total_price"])),
                        )
                    )
                row["subtotal"] = Decimal(str(row["subtotal"]))
                row["tax"] = Decimal(str(row["tax"]))
                row["total_amount"] = Decimal(str(row["total_amount"]))
                row["customer_name"] = cust.get("name")
                row["items"] = order_items
                items.append(OrderResponse(**row))

            return items, total

    async def get_order(self, business_id: str, order_id: str) -> Optional[OrderResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/orders"
        params = {
            "business_id": f"eq.{business_id}",
            "id": f"eq.{order_id}",
            "select": "*,customers(name),order_items(*,products(name,sku))",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code != 200 or not resp.json():
                return None
            row = resp.json()[0]
            cust = self._extract_dict(row.pop("customers", None))
            raw_items = row.pop("order_items", []) or []
            order_items = []
            for it in raw_items:
                prod = self._extract_dict(it.pop("products", None))
                order_items.append(
                    OrderItemResponse(
                        id=it["id"],
                        order_id=row["id"],
                        product_id=it["product_id"],
                        product_name=prod.get("name", "Product"),
                        product_sku=prod.get("sku", "SKU"),
                        quantity=it["quantity"],
                        unit_price=Decimal(str(it["unit_price"])),
                        total_price=Decimal(str(it["total_price"])),
                    )
                )
            row["subtotal"] = Decimal(str(row["subtotal"]))
            row["tax"] = Decimal(str(row["tax"]))
            row["total_amount"] = Decimal(str(row["total_amount"]))
            row["customer_name"] = cust.get("name")
            row["items"] = order_items
            return OrderResponse(**row)

    async def create_order(
        self,
        business_id: str,
        order: OrderCreate,
        user_id: str,
        product_repo: BaseProductRepository,
        customer_repo: Optional[BaseCustomerRepository] = None,
    ) -> OrderResponse:
        # Validate customer if provided
        if order.customer_id and customer_repo:
            cust = await customer_repo.get_customer(business_id, order.customer_id)
            if not cust:
                raise ValueError(f"Customer {order.customer_id} does not exist in this business")

        # Validate items with exact decimal arithmetic
        subtotal = Decimal("0.00")
        line_items_data = []

        for it in order.items:
            product = await product_repo.get_product(business_id, it.product_id)
            if not product or product.business_id != business_id:
                raise ValueError(f"Product {it.product_id} not found in this business")
            if not product.is_active:
                raise ValueError(f"Product '{product.name}' is inactive and cannot be ordered")

            unit_price = it.unit_price if it.unit_price is not None else product.unit_price
            unit_price = Decimal(str(unit_price)).quantize(Decimal("0.01"))
            line_total = (Decimal(it.quantity) * unit_price).quantize(Decimal("0.01"))
            subtotal += line_total

            line_items_data.append({
                "product_id": it.product_id,
                "quantity": it.quantity,
                "unit_price": str(unit_price),
                "total_price": str(line_total),
            })

        tax = Decimal("0.00")
        total_amount = subtotal + tax
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        order_number = f"ORD-{now_str}-{uuid.uuid4().hex[:4].upper()}"

        endpoint = f"{self.supabase_url}/rest/v1/orders"
        order_payload = {
            "business_id": business_id,
            "customer_id": order.customer_id,
            "order_number": order_number,
            "status": "draft",
            "subtotal": str(subtotal),
            "tax": str(tax),
            "total_amount": str(total_amount),
            "notes": order.notes,
            "created_by": user_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=order_payload, headers=self._headers)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Failed to create order: {resp.text}")
            created_order = resp.json()[0]
            new_order_id = created_order["id"]

            # Insert line items
            items_endpoint = f"{self.supabase_url}/rest/v1/order_items"
            for item_data in line_items_data:
                item_data["business_id"] = business_id
                item_data["order_id"] = new_order_id

            await client.post(items_endpoint, json=line_items_data, headers=self._headers)

        return await self.get_order(business_id, new_order_id)

    async def update_order(
        self,
        business_id: str,
        order_id: str,
        update: OrderUpdate,
        user_id: str,
        product_repo: BaseProductRepository,
    ) -> Optional[OrderResponse]:
        existing = await self.get_order(business_id, order_id)
        if not existing:
            return None
        if existing.status != "draft":
            raise ValueError(f"Only draft orders can be updated. Current status: '{existing.status}'")

        endpoint = f"{self.supabase_url}/rest/v1/orders"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{order_id}"}
        payload = {}
        if update.customer_id is not None:
            payload["customer_id"] = update.customer_id
        if update.notes is not None:
            payload["notes"] = update.notes

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if payload:
                await client.patch(endpoint, params=params, json=payload, headers=self._headers)

            if update.items is not None:
                # Replace items
                del_endpoint = f"{self.supabase_url}/rest/v1/order_items"
                del_params = {"business_id": f"eq.{business_id}", "order_id": f"eq.{order_id}"}
                await client.delete(del_endpoint, params=del_params, headers=self._headers)

                subtotal = Decimal("0.00")
                line_items_data = []
                for it in update.items:
                    product = await product_repo.get_product(business_id, it.product_id)
                    if not product:
                        raise ValueError(f"Product {it.product_id} not found")
                    unit_price = it.unit_price if it.unit_price is not None else product.unit_price
                    unit_price = Decimal(str(unit_price)).quantize(Decimal("0.01"))
                    line_total = (Decimal(it.quantity) * unit_price).quantize(Decimal("0.01"))
                    subtotal += line_total
                    line_items_data.append({
                        "business_id": business_id,
                        "order_id": order_id,
                        "product_id": it.product_id,
                        "quantity": it.quantity,
                        "unit_price": str(unit_price),
                        "total_price": str(line_total),
                    })

                items_endpoint = f"{self.supabase_url}/rest/v1/order_items"
                await client.post(items_endpoint, json=line_items_data, headers=self._headers)

                totals_payload = {
                    "subtotal": str(subtotal),
                    "total_amount": str(subtotal + existing.tax),
                }
                await client.patch(endpoint, params=params, json=totals_payload, headers=self._headers)

        return await self.get_order(business_id, order_id)

    async def submit_order_for_review(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        existing = await self.get_order(business_id, order_id)
        if not existing:
            raise ValueError("Order not found")
        if existing.status != "draft":
            raise ValueError(f"Cannot submit order from status '{existing.status}'")

        endpoint = f"{self.supabase_url}/rest/v1/orders"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{order_id}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(
                endpoint, params=params, json={"status": "pending_approval"}, headers=self._headers
            )
            if resp.status_code not in (200, 204):
                raise RuntimeError(f"Failed to submit order: {resp.text}")
        return await self.get_order(business_id, order_id)

    async def approve_order(
        self, business_id: str, order_id: str, user_id: str
    ) -> OrderResponse:
        endpoint = f"{self.supabase_url}/rest/v1/rpc/approve_order_atomic"
        payload = {
            "p_order_id": order_id,
            "p_user_id": user_id,
            "p_business_id": business_id,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code != 200:
                err_text = resp.text
                if "Insufficient stock" in err_text:
                    raise ValueError(err_text)
                if "cannot be approved" in err_text:
                    raise ValueError(err_text)
                raise RuntimeError(f"Approval failed: {err_text}")
        return await self.get_order(business_id, order_id)

    async def reject_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        existing = await self.get_order(business_id, order_id)
        if not existing:
            raise ValueError("Order not found")
        if existing.status in ("approved", "fulfilled", "cancelled", "rejected"):
            raise ValueError(f"Cannot reject order with status '{existing.status}'")

        endpoint = f"{self.supabase_url}/rest/v1/orders"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{order_id}"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.patch(
                endpoint, params=params, json={"status": "rejected"}, headers=self._headers
            )
        return await self.get_order(business_id, order_id)

    async def cancel_order(
        self, business_id: str, order_id: str, user_id: str, reason: Optional[str] = None
    ) -> OrderResponse:
        endpoint = f"{self.supabase_url}/rest/v1/rpc/cancel_order_atomic"
        payload = {
            "p_order_id": order_id,
            "p_user_id": user_id,
            "p_business_id": business_id,
            "p_reason": reason or "Cancelled by operator",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code != 200:
                raise RuntimeError(f"Cancel failed: {resp.text}")
        return await self.get_order(business_id, order_id)

    async def product_has_orders(self, business_id: str, product_id: str) -> bool:
        endpoint = f"{self.supabase_url}/rest/v1/order_items"
        params = {
            "business_id": f"eq.{business_id}",
            "product_id": f"eq.{product_id}",
            "select": "id",
            "limit": "1",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code == 200:
                data = resp.json()
                return len(data) > 0
            return False
