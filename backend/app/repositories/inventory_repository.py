"""Inventory repository interface and implementations."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from backend.app.repositories.audit_repository import BaseAuditLogRepository
from backend.app.schemas.inventory import (
    InventoryItemResponse,
    StockAdjustmentRequest,
    StockAdjustmentResponse,
    StockMovementResponse,
)

logger = logging.getLogger("orqestra.inventory")


class BaseInventoryRepository(ABC):
    """Abstract interface for inventory operations."""

    @abstractmethod
    async def list_inventory(
        self,
        business_id: str,
        search: Optional[str] = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InventoryItemResponse], int, int]:
        """Returns (items, total, total_low_stock)."""
        pass

    @abstractmethod
    async def get_inventory_by_product(
        self, business_id: str, product_id: str
    ) -> Optional[InventoryItemResponse]:
        pass

    @abstractmethod
    async def adjust_stock(
        self, business_id: str, request: StockAdjustmentRequest, user_id: str
    ) -> StockAdjustmentResponse:
        pass

    @abstractmethod
    async def list_movements(
        self,
        business_id: str,
        product_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[StockMovementResponse], int]:
        pass


class InMemoryInventoryRepository(BaseInventoryRepository):
    """In-memory inventory repository enforcing atomic adjustment and audit logs."""

    def __init__(
        self,
        product_repo=None,
        audit_repo: Optional[BaseAuditLogRepository] = None,
    ):
        self.product_repo = product_repo
        self.audit_repo = audit_repo
        self._lock = asyncio.Lock()

    async def list_inventory(
        self,
        business_id: str,
        search: Optional[str] = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InventoryItemResponse], int, int]:
        async with self._lock:
            if not self.product_repo:
                return [], 0, 0

            # Access internal state from product_repo safely
            inv_map = getattr(self.product_repo, "_inventory", {})
            prod_map = getattr(self.product_repo, "_products", {})

            items = []
            low_stock_count = 0

            for (b_id, p_id), inv in inv_map.items():
                if b_id != business_id:
                    continue
                prod = prod_map.get(p_id)
                if not prod or not prod.get("is_active", True):
                    continue

                if search:
                    term = search.lower()
                    if term not in prod["name"].lower() and term not in prod["sku"].lower():
                        continue

                qty = inv.get("quantity_on_hand", 0)
                threshold = inv.get("reorder_threshold", 5)
                is_low = qty <= threshold

                if is_low:
                    low_stock_count += 1

                if low_stock_only and not is_low:
                    continue

                items.append(
                    InventoryItemResponse(
                        id=inv["id"],
                        business_id=business_id,
                        product_id=p_id,
                        product_name=prod["name"],
                        product_sku=prod["sku"],
                        unit_price=Decimal(str(prod["unit_price"])),
                        quantity_on_hand=qty,
                        reorder_threshold=threshold,
                        is_low_stock=is_low,
                        updated_at=inv.get("updated_at", datetime.now(timezone.utc)),
                    )
                )

            items.sort(key=lambda x: (not x.is_low_stock, x.product_name))
            total = len(items)
            start = (page - 1) * page_size
            return items[start : start + page_size], total, low_stock_count

    async def get_inventory_by_product(
        self, business_id: str, product_id: str
    ) -> Optional[InventoryItemResponse]:
        async with self._lock:
            if not self.product_repo:
                return None
            inv_map = getattr(self.product_repo, "_inventory", {})
            prod_map = getattr(self.product_repo, "_products", {})

            inv = inv_map.get((business_id, product_id))
            prod = prod_map.get(product_id)
            if not inv or not prod:
                return None

            qty = inv.get("quantity_on_hand", 0)
            threshold = inv.get("reorder_threshold", 5)
            return InventoryItemResponse(
                id=inv["id"],
                business_id=business_id,
                product_id=product_id,
                product_name=prod["name"],
                product_sku=prod["sku"],
                unit_price=Decimal(str(prod["unit_price"])),
                quantity_on_hand=qty,
                reorder_threshold=threshold,
                is_low_stock=qty <= threshold,
                updated_at=inv.get("updated_at", datetime.now(timezone.utc)),
            )

    async def adjust_stock(
        self, business_id: str, request: StockAdjustmentRequest, user_id: str
    ) -> StockAdjustmentResponse:
        async with self._lock:
            if not self.product_repo:
                raise RuntimeError("Product repository not attached")

            inv_map = getattr(self.product_repo, "_inventory", {})
            prod_map = getattr(self.product_repo, "_products", {})
            movements = getattr(self.product_repo, "_movements", [])

            inv = inv_map.get((business_id, request.product_id))
            prod = prod_map.get(request.product_id)

            if not inv or not prod:
                raise ValueError("Product or inventory record not found in this business")

            curr_qty = inv.get("quantity_on_hand", 0)
            new_qty = curr_qty + request.quantity_change

            if new_qty < 0:
                raise ValueError(
                    f"Stock adjustment would result in negative quantity ({new_qty}). Current available: {curr_qty}"
                )

            now = datetime.now(timezone.utc)
            inv["quantity_on_hand"] = new_qty
            inv["updated_at"] = now

            mov_id = str(uuid.uuid4())
            movement_record = {
                "id": mov_id,
                "business_id": business_id,
                "product_id": request.product_id,
                "quantity_change": request.quantity_change,
                "movement_type": request.movement_type,
                "reference_id": None,
                "notes": request.notes,
                "created_by": user_id,
                "created_at": now,
            }
            movements.insert(0, movement_record)

            if self.audit_repo:
                await self.audit_repo.log_event(
                    business_id=business_id,
                    user_id=user_id,
                    action="stock.adjusted",
                    entity_type="inventory",
                    entity_id=inv["id"],
                    old_values={"quantity_on_hand": curr_qty},
                    new_values={
                        "quantity_on_hand": new_qty,
                        "quantity_change": request.quantity_change,
                        "movement_id": mov_id,
                        "reason": request.notes,
                    },
                )

            return StockAdjustmentResponse(
                inventory_id=inv["id"],
                product_id=request.product_id,
                new_quantity=new_qty,
                movement_id=mov_id,
                quantity_change=request.quantity_change,
                notes=request.notes,
            )

    async def list_movements(
        self,
        business_id: str,
        product_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[StockMovementResponse], int]:
        async with self._lock:
            if not self.product_repo:
                return [], 0
            movements = getattr(self.product_repo, "_movements", [])
            prod_map = getattr(self.product_repo, "_products", {})

            filtered = []
            for m in movements:
                if m["business_id"] != business_id:
                    continue
                if product_id and m["product_id"] != product_id:
                    continue
                prod = prod_map.get(m["product_id"], {})
                filtered.append(
                    StockMovementResponse(
                        id=m["id"],
                        business_id=business_id,
                        product_id=m["product_id"],
                        product_name=prod.get("name"),
                        product_sku=prod.get("sku"),
                        quantity_change=m["quantity_change"],
                        movement_type=m["movement_type"],
                        reference_id=m.get("reference_id"),
                        notes=m.get("notes"),
                        created_by=m.get("created_by"),
                        created_at=m["created_at"],
                    )
                )

            filtered.sort(key=lambda x: x.created_at, reverse=True)
            total = len(filtered)
            start = (page - 1) * page_size
            return filtered[start : start + page_size], total


class SupabaseInventoryRepository(BaseInventoryRepository):
    """Database-backed inventory repository connecting via PostgREST and RPC."""

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
    def _extract_product_data(row: Dict[str, Any]) -> Dict[str, Any]:
        """Safely extract nested product dictionary whether PostgREST returns a dict or list."""
        prod_raw = row.pop("products", None)
        if isinstance(prod_raw, list):
            return prod_raw[0] if prod_raw else {}
        if isinstance(prod_raw, dict):
            return prod_raw
        return {}

    async def list_inventory(
        self,
        business_id: str,
        search: Optional[str] = None,
        low_stock_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[InventoryItemResponse], int, int]:
        endpoint = f"{self.supabase_url}/rest/v1/inventory"
        params = {
            "business_id": f"eq.{business_id}",
            "select": "*,products!inner(name,sku,unit_price,is_active)",
            "order": "quantity_on_hand.asc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if search:
            params["products.or"] = f"(name.ilike.*{search}*,sku.ilike.*{search}*)"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to query inventory: {resp.status_code}")
                return [], 0, 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)

            items = []
            low_stock_count = 0
            for row in data:
                prod = self._extract_product_data(row)
                qty = row["quantity_on_hand"]
                threshold = row["reorder_threshold"]
                is_low = qty <= threshold
                if is_low:
                    low_stock_count += 1
                if low_stock_only and not is_low:
                    continue
                items.append(
                    InventoryItemResponse(
                        id=row["id"],
                        business_id=business_id,
                        product_id=row["product_id"],
                        product_name=prod.get("name", "Product"),
                        product_sku=prod.get("sku", "SKU"),
                        unit_price=Decimal(str(prod.get("unit_price", "0.00"))),
                        quantity_on_hand=qty,
                        reorder_threshold=threshold,
                        is_low_stock=is_low,
                        updated_at=row["updated_at"],
                    )
                )
            return items, total, low_stock_count

    async def get_inventory_by_product(
        self, business_id: str, product_id: str
    ) -> Optional[InventoryItemResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/inventory"
        params = {
            "business_id": f"eq.{business_id}",
            "product_id": f"eq.{product_id}",
            "select": "*,products!inner(name,sku,unit_price)",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code != 200 or not resp.json():
                return None
            row = resp.json()[0]
            prod = self._extract_product_data(row)
            qty = row["quantity_on_hand"]
            threshold = row["reorder_threshold"]
            return InventoryItemResponse(
                id=row["id"],
                business_id=business_id,
                product_id=product_id,
                product_name=prod.get("name", "Product"),
                product_sku=prod.get("sku", "SKU"),
                unit_price=Decimal(str(prod.get("unit_price", "0.00"))),
                quantity_on_hand=qty,
                reorder_threshold=threshold,
                is_low_stock=qty <= threshold,
                updated_at=row["updated_at"],
            )

    async def adjust_stock(
        self, business_id: str, request: StockAdjustmentRequest, user_id: str
    ) -> StockAdjustmentResponse:
        endpoint = f"{self.supabase_url}/rest/v1/rpc/adjust_stock_atomic"
        payload = {
            "p_business_id": business_id,
            "p_product_id": request.product_id,
            "p_quantity_change": request.quantity_change,
            "p_movement_type": request.movement_type,
            "p_notes": request.notes,
            "p_user_id": user_id,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code != 200:
                err_text = resp.text
                if "negative quantity" in err_text:
                    raise ValueError("Stock adjustment rejected: would result in negative quantity")
                raise RuntimeError(f"Database error during stock adjustment: {err_text}")
            data = resp.json()[0]
            return StockAdjustmentResponse(
                inventory_id=data["inventory_id"],
                product_id=data["product_id"],
                new_quantity=data["new_quantity"],
                movement_id=data["movement_id"],
                quantity_change=request.quantity_change,
                notes=request.notes,
            )

    async def list_movements(
        self,
        business_id: str,
        product_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[StockMovementResponse], int]:
        endpoint = f"{self.supabase_url}/rest/v1/stock_movements"
        params = {
            "business_id": f"eq.{business_id}",
            "select": "*,products(name,sku)",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if product_id:
            params["product_id"] = f"eq.{product_id}"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                return [], 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)

            items = []
            for row in data:
                prod = self._extract_product_data(row)
                items.append(
                    StockMovementResponse(
                        id=row["id"],
                        business_id=business_id,
                        product_id=row["product_id"],
                        product_name=prod.get("name"),
                        product_sku=prod.get("sku"),
                        quantity_change=row["quantity_change"],
                        movement_type=row["movement_type"],
                        reference_id=row.get("reference_id"),
                        notes=row.get("notes"),
                        created_by=row.get("created_by"),
                        created_at=row["created_at"],
                    )
                )
            return items, total
