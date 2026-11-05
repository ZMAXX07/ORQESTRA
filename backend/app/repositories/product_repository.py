"""Product repository interface and implementations."""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from backend.app.schemas.products import ProductCreate, ProductResponse, ProductUpdate

logger = logging.getLogger("orqestra.products")


class BaseProductRepository(ABC):
    """Abstract interface for product operations."""

    @abstractmethod
    async def list_products(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ProductResponse], int]:
        pass

    @abstractmethod
    async def get_product(self, business_id: str, product_id: str) -> Optional[ProductResponse]:
        pass

    @abstractmethod
    async def get_product_by_sku(self, business_id: str, sku: str) -> Optional[ProductResponse]:
        pass

    @abstractmethod
    async def create_product(
        self, business_id: str, product: ProductCreate, user_id: str
    ) -> ProductResponse:
        pass

    @abstractmethod
    async def update_product(
        self, business_id: str, product_id: str, update: ProductUpdate, user_id: str
    ) -> Optional[ProductResponse]:
        pass

    @abstractmethod
    async def deactivate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        pass

    @abstractmethod
    async def activate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        pass

    @abstractmethod
    async def delete_product(
        self, business_id: str, product_id: str
    ) -> bool:
        """Permanently delete a product and its associated inventory/movements."""
        pass


class InMemoryProductRepository(BaseProductRepository):
    """In-memory product and linked inventory repository for testing."""

    def __init__(self, initial_products: Optional[List[Dict[str, Any]]] = None):
        self._products: Dict[str, Dict[str, Any]] = {}
        self._inventory: Dict[str, Dict[str, Any]] = {}  # keyed by (business_id, product_id)
        self._movements: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

        if initial_products:
            for p in initial_products:
                self._products[p["id"]] = dict(p)
                self._inventory[(p["business_id"], p["id"])] = {
                    "id": str(uuid.uuid4()),
                    "business_id": p["business_id"],
                    "product_id": p["id"],
                    "quantity_on_hand": p.get("quantity_on_hand", 0),
                    "reorder_threshold": p.get("reorder_threshold", 5),
                    "updated_at": datetime.now(timezone.utc),
                }

    def _to_response(self, p: Dict[str, Any]) -> ProductResponse:
        inv = self._inventory.get((p["business_id"], p["id"]), {})
        qty = inv.get("quantity_on_hand", 0)
        threshold = inv.get("reorder_threshold", 5)
        return ProductResponse(
            id=p["id"],
            business_id=p["business_id"],
            sku=p["sku"],
            name=p["name"],
            description=p.get("description"),
            unit_price=Decimal(str(p["unit_price"])),
            cost_price=Decimal(str(p["cost_price"])) if p.get("cost_price") is not None else None,
            is_active=p.get("is_active", True),
            created_at=p["created_at"],
            updated_at=p["updated_at"],
            quantity_on_hand=qty,
            reorder_threshold=threshold,
            is_low_stock=qty <= threshold,
        )

    async def list_products(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ProductResponse], int]:
        async with self._lock:
            results = []
            for p in self._products.values():
                if p["business_id"] != business_id:
                    continue
                if is_active is not None and p["is_active"] != is_active:
                    continue
                if search:
                    term = search.lower()
                    if term not in p["name"].lower() and term not in p["sku"].lower():
                        continue
                results.append(self._to_response(p))

            results.sort(key=lambda x: x.created_at, reverse=True)
            total = len(results)
            start = (page - 1) * page_size
            return results[start : start + page_size], total

    async def get_product(self, business_id: str, product_id: str) -> Optional[ProductResponse]:
        async with self._lock:
            p = self._products.get(product_id)
            if p and p["business_id"] == business_id:
                return self._to_response(p)
            return None

    async def get_product_by_sku(self, business_id: str, sku: str) -> Optional[ProductResponse]:
        async with self._lock:
            clean_sku = sku.strip().upper()
            for p in self._products.values():
                if p["business_id"] == business_id and p["sku"].upper() == clean_sku:
                    return self._to_response(p)
            return None

    async def create_product(
        self, business_id: str, product: ProductCreate, user_id: str
    ) -> ProductResponse:
        async with self._lock:
            # Check unique SKU in business
            for p in self._products.values():
                if p["business_id"] == business_id and p["sku"].upper() == product.sku.upper():
                    raise ValueError(f"A product with SKU '{product.sku}' already exists in this business")

            prod_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            record = {
                "id": prod_id,
                "business_id": business_id,
                "sku": product.sku,
                "name": product.name,
                "description": product.description,
                "unit_price": product.unit_price,
                "cost_price": product.cost_price,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            self._products[prod_id] = record

            # Initialize inventory
            inv_id = str(uuid.uuid4())
            self._inventory[(business_id, prod_id)] = {
                "id": inv_id,
                "business_id": business_id,
                "product_id": prod_id,
                "quantity_on_hand": product.initial_stock,
                "reorder_threshold": product.reorder_threshold,
                "updated_at": now,
            }

            # If initial stock > 0, log stock movement
            if product.initial_stock > 0:
                self._movements.append({
                    "id": str(uuid.uuid4()),
                    "business_id": business_id,
                    "product_id": prod_id,
                    "quantity_change": product.initial_stock,
                    "movement_type": "initial",
                    "notes": "Initial stock on product creation",
                    "created_by": user_id,
                    "created_at": now,
                })

            return self._to_response(record)

    async def update_product(
        self, business_id: str, product_id: str, update: ProductUpdate, user_id: str
    ) -> Optional[ProductResponse]:
        async with self._lock:
            p = self._products.get(product_id)
            if not p or p["business_id"] != business_id:
                return None

            if update.name is not None:
                p["name"] = update.name
            if update.description is not None:
                p["description"] = update.description
            if update.unit_price is not None:
                p["unit_price"] = update.unit_price
            if update.cost_price is not None:
                p["cost_price"] = update.cost_price
            if update.is_active is not None:
                p["is_active"] = update.is_active

            p["updated_at"] = datetime.now(timezone.utc)
            return self._to_response(p)

    async def deactivate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        async with self._lock:
            p = self._products.get(product_id)
            if not p or p["business_id"] != business_id:
                return None
            p["is_active"] = False
            p["updated_at"] = datetime.now(timezone.utc)
            return self._to_response(p)

    async def activate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        async with self._lock:
            p = self._products.get(product_id)
            if not p or p["business_id"] != business_id:
                return None
            p["is_active"] = True
            p["updated_at"] = datetime.now(timezone.utc)
            return self._to_response(p)

    async def delete_product(self, business_id: str, product_id: str) -> bool:
        async with self._lock:
            p = self._products.get(product_id)
            if not p or p["business_id"] != business_id:
                return False
            del self._products[product_id]
            self._inventory.pop((business_id, product_id), None)
            self._movements = [
                m
                for m in self._movements
                if not (m["business_id"] == business_id and m["product_id"] == product_id)
            ]
            return True


class SupabaseProductRepository(BaseProductRepository):
    """Database-backed product repository connecting via PostgREST."""

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
    def _extract_inventory_data(row: Dict[str, Any]) -> Dict[str, Any]:
        """Safely extract nested inventory dictionary whether PostgREST returns a dict or list."""
        inv_raw = row.pop("inventory", None)
        if isinstance(inv_raw, list):
            return inv_raw[0] if inv_raw else {}
        if isinstance(inv_raw, dict):
            return inv_raw
        return {}

    async def list_products(
        self,
        business_id: str,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ProductResponse], int]:
        endpoint = f"{self.supabase_url}/rest/v1/products"
        params = {
            "business_id": f"eq.{business_id}",
            "select": "*,inventory(quantity_on_hand,reorder_threshold)",
            "order": "created_at.desc",
            "limit": str(page_size),
            "offset": str((page - 1) * page_size),
        }
        if is_active is not None:
            params["is_active"] = f"eq.{str(is_active).lower()}"
        if search:
            params["or"] = f"(name.ilike.*{search}*,sku.ilike.*{search}*)"

        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to list products: {resp.status_code} {resp.text}")
                return [], 0
            data = resp.json()
            content_range = resp.headers.get("content-range", "")
            total = int(content_range.split("/")[-1]) if "/" in content_range else len(data)

            items = []
            for row in data:
                inv = self._extract_inventory_data(row)
                qty = inv.get("quantity_on_hand", 0)
                threshold = inv.get("reorder_threshold", 5)
                row["unit_price"] = Decimal(str(row["unit_price"]))
                if row.get("cost_price") is not None:
                    row["cost_price"] = Decimal(str(row["cost_price"]))
                row["quantity_on_hand"] = qty
                row["reorder_threshold"] = threshold
                row["is_low_stock"] = qty <= threshold
                items.append(ProductResponse(**row))

            return items, total

    async def get_product(self, business_id: str, product_id: str) -> Optional[ProductResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/products"
        params = {
            "business_id": f"eq.{business_id}",
            "id": f"eq.{product_id}",
            "select": "*,inventory(quantity_on_hand,reorder_threshold)",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code != 200 or not resp.json():
                return None
            row = resp.json()[0]
            inv = self._extract_inventory_data(row)
            qty = inv.get("quantity_on_hand", 0)
            threshold = inv.get("reorder_threshold", 5)
            row["unit_price"] = Decimal(str(row["unit_price"]))
            if row.get("cost_price") is not None:
                row["cost_price"] = Decimal(str(row["cost_price"]))
            row["quantity_on_hand"] = qty
            row["reorder_threshold"] = threshold
            row["is_low_stock"] = qty <= threshold
            return ProductResponse(**row)

    async def get_product_by_sku(self, business_id: str, sku: str) -> Optional[ProductResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/products"
        params = {
            "business_id": f"eq.{business_id}",
            "sku": f"eq.{sku.strip().upper()}",
            "select": "*,inventory(quantity_on_hand,reorder_threshold)",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(endpoint, params=params, headers=self._headers)
            if resp.status_code != 200 or not resp.json():
                return None
            row = resp.json()[0]
            inv = self._extract_inventory_data(row)
            qty = inv.get("quantity_on_hand", 0)
            threshold = inv.get("reorder_threshold", 5)
            row["unit_price"] = Decimal(str(row["unit_price"]))
            if row.get("cost_price") is not None:
                row["cost_price"] = Decimal(str(row["cost_price"]))
            row["quantity_on_hand"] = qty
            row["reorder_threshold"] = threshold
            row["is_low_stock"] = qty <= threshold
            return ProductResponse(**row)

    async def create_product(
        self, business_id: str, product: ProductCreate, user_id: str
    ) -> ProductResponse:
        endpoint = f"{self.supabase_url}/rest/v1/products"
        payload = {
            "business_id": business_id,
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "unit_price": str(product.unit_price),
            "cost_price": str(product.cost_price) if product.cost_price is not None else None,
            "is_active": True,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers)
            if resp.status_code not in (200, 201):
                if "duplicate key value" in resp.text or "uq_products_business_sku" in resp.text:
                    raise ValueError(f"A product with SKU '{product.sku}' already exists in this business")
                raise RuntimeError(f"Failed to create product: {resp.status_code} {resp.text}")
            data = resp.json()[0]
            prod_id = data["id"]

            # Create inventory record
            inv_endpoint = f"{self.supabase_url}/rest/v1/inventory"
            inv_payload = {
                "business_id": business_id,
                "product_id": prod_id,
                "quantity_on_hand": product.initial_stock,
                "reorder_threshold": product.reorder_threshold,
            }
            await client.post(inv_endpoint, json=inv_payload, headers=self._headers)

            if product.initial_stock > 0:
                mov_endpoint = f"{self.supabase_url}/rest/v1/stock_movements"
                mov_payload = {
                    "business_id": business_id,
                    "product_id": prod_id,
                    "quantity_change": product.initial_stock,
                    "movement_type": "initial",
                    "notes": "Initial stock on product creation",
                    "created_by": user_id,
                }
                await client.post(mov_endpoint, json=mov_payload, headers=self._headers)

            data["unit_price"] = Decimal(str(data["unit_price"]))
            if data.get("cost_price") is not None:
                data["cost_price"] = Decimal(str(data["cost_price"]))
            data["quantity_on_hand"] = product.initial_stock
            data["reorder_threshold"] = product.reorder_threshold
            data["is_low_stock"] = product.initial_stock <= product.reorder_threshold
            return ProductResponse(**data)

    async def update_product(
        self, business_id: str, product_id: str, update: ProductUpdate, user_id: str
    ) -> Optional[ProductResponse]:
        endpoint = f"{self.supabase_url}/rest/v1/products"
        params = {"business_id": f"eq.{business_id}", "id": f"eq.{product_id}"}
        payload = {}
        if update.name is not None:
            payload["name"] = update.name
        if update.description is not None:
            payload["description"] = update.description
        if update.unit_price is not None:
            payload["unit_price"] = str(update.unit_price)
        if update.cost_price is not None:
            payload["cost_price"] = str(update.cost_price)
        if update.is_active is not None:
            payload["is_active"] = update.is_active

        if not payload:
            return await self.get_product(business_id, product_id)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(endpoint, params=params, json=payload, headers=self._headers)
            if resp.status_code not in (200, 204) or not resp.json():
                return None
            return await self.get_product(business_id, product_id)

    async def deactivate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        return await self.update_product(business_id, product_id, ProductUpdate(is_active=False), user_id)

    async def activate_product(
        self, business_id: str, product_id: str, user_id: str
    ) -> Optional[ProductResponse]:
        return await self.update_product(business_id, product_id, ProductUpdate(is_active=True), user_id)

    async def delete_product(self, business_id: str, product_id: str) -> bool:
        existing = await self.get_product(business_id, product_id)
        if not existing:
            return False

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            mov_endpoint = f"{self.supabase_url}/rest/v1/stock_movements"
            mov_params = {"business_id": f"eq.{business_id}", "product_id": f"eq.{product_id}"}
            await client.delete(mov_endpoint, params=mov_params, headers=self._headers)

            inv_endpoint = f"{self.supabase_url}/rest/v1/inventory"
            inv_params = {"business_id": f"eq.{business_id}", "product_id": f"eq.{product_id}"}
            await client.delete(inv_endpoint, params=inv_params, headers=self._headers)

            endpoint = f"{self.supabase_url}/rest/v1/products"
            params = {"business_id": f"eq.{business_id}", "id": f"eq.{product_id}"}
            resp = await client.delete(endpoint, params=params, headers=self._headers)
            if resp.status_code in (200, 204):
                return True
            if "violates foreign key constraint" in resp.text or resp.status_code == 409:
                raise ValueError("Cannot delete product because it is referenced by existing orders.")
            raise RuntimeError(f"Failed to delete product: {resp.status_code} {resp.text}")
