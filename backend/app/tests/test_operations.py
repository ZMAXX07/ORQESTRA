"""Comprehensive integration and security tests for Phase 3 Core Business Operations."""

from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app.api.deps import (
    get_audit_repository,
    get_business_repository,
    get_customer_repository,
    get_inventory_repository,
    get_order_repository,
    get_product_repository,
    get_settings,
)
from backend.app.core.config import Settings
from backend.app.main import create_application
from backend.app.repositories.audit_repository import InMemoryAuditLogRepository
from backend.app.repositories.business_repository import InMemoryBusinessRepository
from backend.app.repositories.customer_repository import InMemoryCustomerRepository
from backend.app.repositories.inventory_repository import InMemoryInventoryRepository
from backend.app.repositories.order_repository import InMemoryOrderRepository
from backend.app.repositories.product_repository import InMemoryProductRepository
from backend.app.tests.test_jwt_verification import TEST_SECRET, create_token

USER_OWNER_ID = "00000000-0000-0000-0000-000000000001"
USER_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
USER_STAFF_ID = "00000000-0000-0000-0000-000000000003"
USER_OUTSIDER_ID = "00000000-0000-0000-0000-000000000099"

BUSINESS_ALPHA_ID = "bbbbbbbb-0001-0000-0000-000000000001"
BUSINESS_BETA_ID = "bbbbbbbb-0002-0000-0000-000000000002"


@pytest.fixture
def ops_test_client():
    """Configures application with in-memory repositories shared across domains."""
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        CORS_ORIGINS=["http://testserver"],
    )

    business_repo = InMemoryBusinessRepository()
    business_repo.add_membership(USER_OWNER_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "owner")
    business_repo.add_membership(USER_ADMIN_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "admin")
    business_repo.add_membership(USER_STAFF_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "staff")
    business_repo.add_membership(USER_OUTSIDER_ID, BUSINESS_BETA_ID, "Beta Logistics", "owner")

    audit_repo = InMemoryAuditLogRepository()
    product_repo = InMemoryProductRepository()
    inventory_repo = InMemoryInventoryRepository(product_repo=product_repo, audit_repo=audit_repo)
    customer_repo = InMemoryCustomerRepository()
    order_repo = InMemoryOrderRepository(product_repo=product_repo, audit_repo=audit_repo)

    app = create_application(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_business_repository] = lambda: business_repo
    app.dependency_overrides[get_audit_repository] = lambda: audit_repo
    app.dependency_overrides[get_product_repository] = lambda: product_repo
    app.dependency_overrides[get_inventory_repository] = lambda: inventory_repo
    app.dependency_overrides[get_customer_repository] = lambda: customer_repo
    app.dependency_overrides[get_order_repository] = lambda: order_repo

    with TestClient(app) as client:
        yield {
            "client": client,
            "product_repo": product_repo,
            "inventory_repo": inventory_repo,
            "customer_repo": customer_repo,
            "order_repo": order_repo,
            "audit_repo": audit_repo,
        }
    app.dependency_overrides.clear()


def auth_header(user_id: str, business_id: str):
    token = create_token(sub=user_id)
    return {"Authorization": f"Bearer {token}", "X-Business-ID": business_id}


# ==============================================================================
# Product Management Tests
# ==============================================================================

def test_product_lifecycle(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # 1. Staff cannot create product -> 403
    staff_create = client.post(
        "/api/v1/products",
        json={"sku": "WIDGET-01", "name": "Widget Alpha", "unit_price": "19.99", "initial_stock": 50},
        headers=staff_hdr,
    )
    assert staff_create.status_code == 403

    # 2. Admin creates product -> 201
    create_res = client.post(
        "/api/v1/products",
        json={
            "sku": "WIDGET-01",
            "name": "Widget Alpha",
            "description": "Standard operational widget",
            "unit_price": "19.99",
            "cost_price": "10.00",
            "initial_stock": 50,
            "reorder_threshold": 10,
        },
        headers=admin_hdr,
    )
    assert create_res.status_code == 201
    data = create_res.json()
    prod_id = data["id"]
    assert data["sku"] == "WIDGET-01"
    assert data["unit_price"] == "19.99"
    assert data["quantity_on_hand"] == 50
    assert not data["is_low_stock"]

    # 3. Duplicate SKU in same business -> 409
    dup_res = client.post(
        "/api/v1/products",
        json={"sku": "WIDGET-01", "name": "Duplicate Widget", "unit_price": "29.99"},
        headers=admin_hdr,
    )
    assert dup_res.status_code == 409

    # 4. Staff can list and get product -> 200
    list_res = client.get("/api/v1/products", headers=staff_hdr)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1

    get_res = client.get(f"/api/v1/products/{prod_id}", headers=staff_hdr)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Widget Alpha"

    # 5. Cross-business product read returns 404
    outsider_hdr = auth_header(USER_OUTSIDER_ID, BUSINESS_BETA_ID)
    cross_res = client.get(f"/api/v1/products/{prod_id}", headers=outsider_hdr)
    assert cross_res.status_code == 404

    # 6. Admin updates product -> 200
    upd_res = client.put(
        f"/api/v1/products/{prod_id}",
        json={"name": "Widget Alpha Premium", "unit_price": "24.50"},
        headers=admin_hdr,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["name"] == "Widget Alpha Premium"
    assert upd_res.json()["unit_price"] == "24.50"

    # 7. Admin deactivates product -> 200
    deact_res = client.patch(f"/api/v1/products/{prod_id}/deactivate", headers=admin_hdr)
    assert deact_res.status_code == 200
    assert not deact_res.json()["is_active"]

    # 8. Staff cannot activate or delete product -> 403
    staff_act_res = client.patch(f"/api/v1/products/{prod_id}/activate", headers=staff_hdr)
    assert staff_act_res.status_code == 403
    staff_del_res = client.delete(f"/api/v1/products/{prod_id}", headers=staff_hdr)
    assert staff_del_res.status_code == 403

    # 9. Admin activates product -> 200, is_active is True
    act_res = client.patch(f"/api/v1/products/{prod_id}/activate", headers=admin_hdr)
    assert act_res.status_code == 200
    assert act_res.json()["is_active"] is True

    # 10. Admin deletes product without orders -> 204
    del_res = client.delete(f"/api/v1/products/{prod_id}", headers=admin_hdr)
    assert del_res.status_code == 204

    # 11. Fetching deleted product returns 404
    get_del_res = client.get(f"/api/v1/products/{prod_id}", headers=admin_hdr)
    assert get_del_res.status_code == 404


def test_product_with_orders_cannot_be_deleted(ops_test_client):
    """Verify that a product referenced by orders cannot be deleted (returns 409)."""
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)

    # 1. Create product
    prod_res = client.post(
        "/api/v1/products",
        json={"sku": "PROD-ORDERED-01", "name": "Protected Product", "unit_price": "50.00", "initial_stock": 10},
        headers=admin_hdr,
    )
    assert prod_res.status_code == 201
    prod_id = prod_res.json()["id"]

    # 2. Create customer
    cust_res = client.post(
        "/api/v1/customers",
        json={"name": "Protected Order Client", "email": "client@example.com"},
        headers=admin_hdr,
    )
    assert cust_res.status_code == 201
    cust_id = cust_res.json()["id"]

    # 3. Create order containing the product
    ord_res = client.post(
        "/api/v1/orders",
        json={
            "customer_id": cust_id,
            "items": [{"product_id": prod_id, "quantity": 2, "unit_price": "50.00"}],
        },
        headers=admin_hdr,
    )
    assert ord_res.status_code == 201

    # 4. Attempt to delete product -> 409 Conflict
    del_res = client.delete(f"/api/v1/products/{prod_id}", headers=admin_hdr)
    assert del_res.status_code == 409
    assert "Cannot delete product with existing order history" in del_res.json()["error"]["message"]


# ==============================================================================
# Inventory & Stock Adjustment Tests
# ==============================================================================

def test_inventory_and_stock_adjustments(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # Setup product with 10 units (threshold 10 -> is_low_stock = True)
    prod = client.post(
        "/api/v1/products",
        json={"sku": "BOLT-01", "name": "Heavy Bolt", "unit_price": "5.00", "initial_stock": 10, "reorder_threshold": 10},
        headers=admin_hdr,
    ).json()
    prod_id = prod["id"]

    # 1. List inventory shows low stock
    inv_res = client.get("/api/v1/inventory", headers=staff_hdr)
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert inv_data["total"] == 1
    assert inv_data["total_low_stock"] == 1
    assert inv_data["items"][0]["is_low_stock"] is True

    # 2. Staff cannot adjust stock -> 403
    staff_adj = client.post(
        "/api/v1/inventory/adjust",
        json={"product_id": prod_id, "quantity_change": 5, "notes": "Received extra shipment"},
        headers=staff_hdr,
    )
    assert staff_adj.status_code == 403

    # 3. Missing or empty reason in adjustment is rejected -> 422
    empty_notes = client.post(
        "/api/v1/inventory/adjust",
        json={"product_id": prod_id, "quantity_change": 5, "notes": "  "},
        headers=admin_hdr,
    )
    assert empty_notes.status_code == 422

    # 4. Valid positive adjustment -> 200
    adj_res = client.post(
        "/api/v1/inventory/adjust",
        json={"product_id": prod_id, "quantity_change": 15, "notes": "Supplier restock shipment PO-991"},
        headers=admin_hdr,
    )
    assert adj_res.status_code == 200
    assert adj_res.json()["new_quantity"] == 25

    # 5. Over-deduction causing negative stock is rejected -> 400
    neg_res = client.post(
        "/api/v1/inventory/adjust",
        json={"product_id": prod_id, "quantity_change": -30, "notes": "Warehouse damage"},
        headers=admin_hdr,
    )
    assert neg_res.status_code == 400
    assert "negative quantity" in neg_res.json()["error"]["message"]

    # 6. Verify movement history contains initial + adjustment
    hist_res = client.get(f"/api/v1/inventory/history?product_id={prod_id}", headers=staff_hdr)
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] == 2


# ==============================================================================
# Customer Directory Tests
# ==============================================================================

def test_customer_lifecycle(ops_test_client):
    client = ops_test_client["client"]
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # 1. Staff creates customer -> 201
    create_res = client.post(
        "/api/v1/customers",
        json={
            "name": "Acme Industrial",
            "email": "orders@acmeindustrial.local",
            "phone": "+1-555-0199",
            "address": "100 Manufacturing Way",
        },
        headers=staff_hdr,
    )
    assert create_res.status_code == 201
    cust_id = create_res.json()["id"]

    # 2. Get and update customer -> 200
    get_res = client.get(f"/api/v1/customers/{cust_id}", headers=staff_hdr)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Acme Industrial"

    upd_res = client.put(
        f"/api/v1/customers/{cust_id}",
        json={"phone": "+1-555-0200", "notes": "Preferred Net-30 customer"},
        headers=staff_hdr,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["phone"] == "+1-555-0200"

    # 3. Deactivate customer -> 200
    deact_res = client.patch(f"/api/v1/customers/{cust_id}/deactivate", headers=staff_hdr)
    assert deact_res.status_code == 200
    assert not deact_res.json()["is_active"]


# ==============================================================================
# Order Lifecycle & Concurrency-Safe Stock Deduction Tests
# ==============================================================================

def test_order_creation_exact_decimal_totals(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # Create 2 products
    p1 = client.post(
        "/api/v1/products",
        json={"sku": "ITEM-A", "name": "Item A", "unit_price": "10.33", "initial_stock": 20},
        headers=admin_hdr,
    ).json()
    p2 = client.post(
        "/api/v1/products",
        json={"sku": "ITEM-B", "name": "Item B", "unit_price": "2.50", "initial_stock": 50},
        headers=admin_hdr,
    ).json()

    # Create draft order with exact quantities: 3 * 10.33 + 4 * 2.50 = 30.99 + 10.00 = 40.99
    order_res = client.post(
        "/api/v1/orders",
        json={
            "items": [
                {"product_id": p1["id"], "quantity": 3},
                {"product_id": p2["id"], "quantity": 4},
            ]
        },
        headers=staff_hdr,
    )
    assert order_res.status_code == 201
    order = order_res.json()
    assert order["status"] == "draft"
    assert order["subtotal"] == "40.99"
    assert order["total_amount"] == "40.99"
    assert len(order["items"]) == 2


def test_order_approval_deducts_stock_atomically(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # Setup product with 10 units in stock
    prod = client.post(
        "/api/v1/products",
        json={"sku": "LAPTOP-01", "name": "Business Laptop", "unit_price": "999.99", "initial_stock": 10},
        headers=admin_hdr,
    ).json()
    prod_id = prod["id"]

    # Staff creates draft order for 4 units
    order = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": prod_id, "quantity": 4}]},
        headers=staff_hdr,
    ).json()
    order_id = order["id"]

    # Staff submits order for review -> pending_approval
    sub_res = client.post(f"/api/v1/orders/{order_id}/submit", headers=staff_hdr)
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "pending_approval"

    # Staff cannot approve order -> 403
    staff_app = client.post(f"/api/v1/orders/{order_id}/approve", headers=staff_hdr)
    assert staff_app.status_code == 403

    # Admin approves order -> 200, inventory drops from 10 to 6
    app_res = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_hdr)
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"
    assert app_res.json()["approved_by"] == USER_ADMIN_ID

    # Check inventory
    inv = client.get(f"/api/v1/inventory", headers=staff_hdr).json()["items"][0]
    assert inv["quantity_on_hand"] == 6

    # Attempting to approve AGAIN is rejected (idempotent / no duplicate deduction) -> 409
    dup_app = client.post(f"/api/v1/orders/{order_id}/approve", headers=admin_hdr)
    assert dup_app.status_code == 409
    assert "already approved" in dup_app.json()["error"]["message"]

    # Inventory remains unchanged at 6
    inv2 = client.get(f"/api/v1/inventory", headers=staff_hdr).json()["items"][0]
    assert inv2["quantity_on_hand"] == 6


def test_insufficient_stock_prevents_order_approval_and_rolls_back(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # Product A has 5 units, Product B has 2 units
    pa = client.post(
        "/api/v1/products",
        json={"sku": "PA-01", "name": "Part A", "unit_price": "10.00", "initial_stock": 5},
        headers=admin_hdr,
    ).json()
    pb = client.post(
        "/api/v1/products",
        json={"sku": "PB-01", "name": "Part B", "unit_price": "20.00", "initial_stock": 2},
        headers=admin_hdr,
    ).json()

    # Order requests 3 Part A (sufficient) and 4 Part B (INSUFFICIENT)
    order = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": pa["id"], "quantity": 3}, {"product_id": pb["id"], "quantity": 4}]},
        headers=staff_hdr,
    ).json()

    # Admin approves -> Must fail with 409 Insufficient Stock
    app_res = client.post(f"/api/v1/orders/{order['id']}/approve", headers=admin_hdr)
    assert app_res.status_code == 409
    assert "Insufficient stock for product 'Part B'" in app_res.json()["error"]["message"]

    # ATOMIC ROLLBACK VERIFICATION: Part A must STILL have 5 units (no partial deduction!)
    inv_res = client.get("/api/v1/inventory", headers=staff_hdr).json()["items"]
    stock_map = {item["product_id"]: item["quantity_on_hand"] for item in inv_res}
    assert stock_map[pa["id"]] == 5
    assert stock_map[pb["id"]] == 2


def test_cross_business_product_in_order_rejected(ops_test_client):
    client = ops_test_client["client"]
    admin_alpha_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    admin_beta_hdr = auth_header(USER_OUTSIDER_ID, BUSINESS_BETA_ID)
    staff_alpha_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # Create product in Business Beta
    prod_beta = client.post(
        "/api/v1/products",
        json={"sku": "BETA-PROD", "name": "Beta Exclusive", "unit_price": "100.00", "initial_stock": 10},
        headers=admin_beta_hdr,
    ).json()

    # Business Alpha user attempts to order Business Beta product -> 400
    forged_order = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": prod_beta["id"], "quantity": 1}]},
        headers=staff_alpha_hdr,
    )
    assert forged_order.status_code == 400
    assert "not found or does not belong to this business" in forged_order.json()["error"]["message"]


def test_order_cancellation_restores_approved_stock(ops_test_client):
    client = ops_test_client["client"]
    admin_hdr = auth_header(USER_ADMIN_ID, BUSINESS_ALPHA_ID)
    staff_hdr = auth_header(USER_STAFF_ID, BUSINESS_ALPHA_ID)

    # 1. Product with 10 units
    prod = client.post(
        "/api/v1/products",
        json={"sku": "CAN-01", "name": "Cancellable Item", "unit_price": "15.00", "initial_stock": 10},
        headers=admin_hdr,
    ).json()

    # 2. Create and approve order for 4 units -> stock becomes 6
    order = client.post(
        "/api/v1/orders",
        json={"items": [{"product_id": prod["id"], "quantity": 4}]},
        headers=staff_hdr,
    ).json()
    client.post(f"/api/v1/orders/{order['id']}/approve", headers=admin_hdr)

    inv = client.get("/api/v1/inventory", headers=staff_hdr).json()["items"][0]
    assert inv["quantity_on_hand"] == 6

    # 3. Cancel approved order -> stock restored to 10
    cancel_res = client.post(
        f"/api/v1/orders/{order['id']}/cancel",
        json={"reason": "Customer cancelled before dispatch"},
        headers=staff_hdr,
    )
    restored_inv = client.get("/api/v1/inventory", headers=staff_hdr).json()["items"][0]
    assert restored_inv["quantity_on_hand"] == 10


def test_supabase_product_repository_extract_inventory_robustness():
    """Verify SupabaseProductRepository safely extracts inventory whether dict, list, or None."""
    from backend.app.repositories.product_repository import SupabaseProductRepository

    # Case 1: Dict (1-to-1 relationship returned by PostgREST)
    row_dict = {"id": "p1", "name": "Item 1", "inventory": {"quantity_on_hand": 100, "reorder_threshold": 10}}
    inv = SupabaseProductRepository._extract_inventory_data(row_dict)
    assert inv == {"quantity_on_hand": 100, "reorder_threshold": 10}
    assert "inventory" not in row_dict

    # Case 2: List (1-to-many fallback returned by PostgREST)
    row_list = {"id": "p2", "name": "Item 2", "inventory": [{"quantity_on_hand": 50, "reorder_threshold": 5}]}
    inv = SupabaseProductRepository._extract_inventory_data(row_list)
    assert inv == {"quantity_on_hand": 50, "reorder_threshold": 5}
    assert "inventory" not in row_list

    # Case 3: Empty list / None / missing
    row_empty = {"id": "p3", "name": "Item 3", "inventory": []}
    assert SupabaseProductRepository._extract_inventory_data(row_empty) == {}

    row_none = {"id": "p4", "name": "Item 4", "inventory": None}
    assert SupabaseProductRepository._extract_inventory_data(row_none) == {}


def test_cors_headers_propagated_on_error(ops_test_client):
    """Verify error responses propagate Access-Control-Allow-Origin so browsers receive error details."""
    client = ops_test_client["client"]
    res = client.get(
        "/api/v1/products",
        headers={"Origin": "http://testserver"},  # Unauthenticated
    )
    assert res.status_code == 401
    assert res.headers.get("access-control-allow-origin") == "http://testserver"
    assert res.headers.get("access-control-allow-credentials") == "true"
