"""Phase 6 Quality Hardening: Operational data consistency, mutation idempotency, and tenant boundaries."""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from backend.app.api.deps import (
    get_audit_repository,
    get_business_repository,
    get_customer_repository,
    get_inventory_repository,
    get_invoice_repository,
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
from backend.app.repositories.invoice_repository import InMemoryInvoiceRepository
from backend.app.repositories.order_repository import InMemoryOrderRepository
from backend.app.repositories.product_repository import InMemoryProductRepository
from backend.app.tests.test_jwt_verification import TEST_SECRET, create_token

USER_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
USER_STAFF_ID = "00000000-0000-0000-0000-000000000003"
USER_OUTSIDER_ID = "00000000-0000-0000-0000-000000000099"

BUSINESS_ALPHA_ID = "bbbbbbbb-0001-0000-0000-000000000001"
BUSINESS_BETA_ID = "bbbbbbbb-0002-0000-0000-000000000002"


@pytest.fixture
def hardening_client():
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        CORS_ORIGINS=["http://testserver"],
    )

    business_repo = InMemoryBusinessRepository()
    business_repo.add_membership(USER_ADMIN_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "admin")
    business_repo.add_membership(USER_STAFF_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "staff")
    business_repo.add_membership(USER_OUTSIDER_ID, BUSINESS_BETA_ID, "Beta Logistics", "owner")

    audit_repo = InMemoryAuditLogRepository()
    product_repo = InMemoryProductRepository()
    inventory_repo = InMemoryInventoryRepository(product_repo=product_repo, audit_repo=audit_repo)
    customer_repo = InMemoryCustomerRepository()
    order_repo = InMemoryOrderRepository(product_repo=product_repo, audit_repo=audit_repo)
    invoice_repo = InMemoryInvoiceRepository()

    app = create_application(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_business_repository] = lambda: business_repo
    app.dependency_overrides[get_audit_repository] = lambda: audit_repo
    app.dependency_overrides[get_product_repository] = lambda: product_repo
    app.dependency_overrides[get_inventory_repository] = lambda: inventory_repo
    app.dependency_overrides[get_customer_repository] = lambda: customer_repo
    app.dependency_overrides[get_order_repository] = lambda: order_repo
    app.dependency_overrides[get_invoice_repository] = lambda: invoice_repo

    client = TestClient(app)
    return client, {
        "product_repo": product_repo,
        "inventory_repo": inventory_repo,
        "order_repo": order_repo,
        "customer_repo": customer_repo,
        "invoice_repo": invoice_repo,
    }


def auth_headers(user_id: str, business_id: str):
    token = create_token(sub=user_id)
    return {
        "Authorization": f"Bearer {token}",
        "X-Business-ID": business_id,
    }


def test_dashboard_metrics_consistency_and_filtering(hardening_client):
    client, repos = hardening_client

    # 1. Create a product with initial stock = 3, threshold = 5 (low stock)
    prod_payload = {
        "sku": "ITEM-LOW-1",
        "name": "Safety Goggles",
        "unit_price": "25.00",
        "initial_stock": 3,
        "reorder_threshold": 5,
    }
    res = client.post(
        "/api/v1/products",
        json=prod_payload,
        headers=auth_headers(USER_ADMIN_ID, BUSINESS_ALPHA_ID),
    )
    assert res.status_code == 201
    prod_id = res.json()["id"]

    # 2. Query inventory endpoint for dashboard overview
    inv_res = client.get(
        "/api/v1/inventory",
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert inv_data["total"] >= 1
    assert inv_data["total_low_stock"] >= 1

    # 3. Query low_stock_only=true
    low_res = client.get(
        "/api/v1/inventory?low_stock_only=true",
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    assert low_res.status_code == 200
    low_data = low_res.json()
    assert len(low_data["items"]) >= 1
    assert any(i["product_id"] == prod_id for i in low_data["items"])


def test_order_approval_deduction_and_repeated_approval_rejection(hardening_client):
    client, repos = hardening_client

    # 1. Create product with stock = 10
    prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": "VALVE-01",
            "name": "Check Valve",
            "unit_price": "100.00",
            "initial_stock": 10,
            "reorder_threshold": 2,
        },
        headers=auth_headers(USER_ADMIN_ID, BUSINESS_ALPHA_ID),
    )
    prod_id = prod_res.json()["id"]

    # 2. Create customer
    cust_res = client.post(
        "/api/v1/customers",
        json={"name": "Acme Industries", "email": "purchasing@acme.com"},
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    cust_id = cust_res.json()["id"]

    # 3. Create draft order
    order_res = client.post(
        "/api/v1/orders",
        json={
            "customer_id": cust_id,
            "items": [{"product_id": prod_id, "quantity": 4}],
        },
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    assert order_res.status_code == 201
    order_id = order_res.json()["id"]

    # 4. Submit order for review
    sub_res = client.post(
        f"/api/v1/orders/{order_id}/submit",
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] == "pending_approval"

    # 5. Approve order (stock deducted: 10 - 4 = 6)
    app_res = client.post(
        f"/api/v1/orders/{order_id}/approve",
        headers=auth_headers(USER_ADMIN_ID, BUSINESS_ALPHA_ID),
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # 6. Verify inventory stock is authoritative
    inv_res = client.get(
        "/api/v1/inventory",
        headers=auth_headers(USER_STAFF_ID, BUSINESS_ALPHA_ID),
    )
    valve_inv = next(i for i in inv_res.json()["items"] if i["product_id"] == prod_id)
    assert valve_inv["quantity_on_hand"] == 6

    # 7. Repeated approval attempt MUST return 409 Conflict
    dup_app = client.post(
        f"/api/v1/orders/{order_id}/approve",
        headers=auth_headers(USER_ADMIN_ID, BUSINESS_ALPHA_ID),
    )
    assert dup_app.status_code == 409
    assert "already approved" in dup_app.json()["error"]["message"]


def test_cross_tenant_isolation_on_operational_endpoints(hardening_client):
    client, repos = hardening_client

    # Outsider from BUSINESS_BETA attempts to access BUSINESS_ALPHA inventory
    unauth_res = client.get(
        "/api/v1/inventory",
        headers=auth_headers(USER_OUTSIDER_ID, BUSINESS_ALPHA_ID),
    )
    assert unauth_res.status_code == 403
    assert "Access denied" in unauth_res.json()["error"]["message"]

    # Outsider attempts to access BUSINESS_ALPHA orders
    unauth_orders = client.get(
        "/api/v1/orders",
        headers=auth_headers(USER_OUTSIDER_ID, BUSINESS_ALPHA_ID),
    )
    assert unauth_orders.status_code == 403

    # Outsider attempts to access BUSINESS_ALPHA invoices
    unauth_invoices = client.get(
        "/api/v1/invoices",
        headers=auth_headers(USER_OUTSIDER_ID, BUSINESS_ALPHA_ID),
    )
    assert unauth_invoices.status_code == 403
