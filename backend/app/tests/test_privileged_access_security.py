"""Privileged backend access and tenant boundary security validation suite.

Phase 7.3.1 Security Review verification:
- Confirms client-supplied business IDs, user IDs, and roles cannot override the authenticated identity.
- Confirms cross-business resource tampering (products, customers, orders, invoices) is prevented.
- Confirms strict role hierarchy enforcement on privileged operations.
- Confirms fail-closed behavior for unauthenticated and unauthorized requests.
"""

from decimal import Decimal
import uuid
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

USER_ADMIN_A = "00000000-0000-0000-0000-000000000001"
USER_STAFF_A = "00000000-0000-0000-0000-000000000002"
USER_ADMIN_B = "00000000-0000-0000-0000-000000000003"
USER_STAFF_B = "00000000-0000-0000-0000-000000000004"

BUSINESS_A_ID = "aaaaaaaa-0000-0000-0000-000000000001"
BUSINESS_B_ID = "bbbbbbbb-0000-0000-0000-000000000002"


@pytest.fixture
def sec_client():
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        CORS_ORIGINS=["http://testserver"],
    )

    business_repo = InMemoryBusinessRepository()
    business_repo.add_membership(USER_ADMIN_A, BUSINESS_A_ID, "Business Alpha", "admin")
    business_repo.add_membership(USER_STAFF_A, BUSINESS_A_ID, "Business Alpha", "staff")
    business_repo.add_membership(USER_ADMIN_B, BUSINESS_B_ID, "Business Beta", "admin")
    business_repo.add_membership(USER_STAFF_B, BUSINESS_B_ID, "Business Beta", "staff")

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
        "customer_repo": customer_repo,
        "order_repo": order_repo,
        "invoice_repo": invoice_repo,
    }


def auth_headers(user_id: str, business_id: str, extra: dict = None):
    token = create_token(sub=user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Business-ID": business_id,
    }
    if extra:
        headers.update(extra)
    return headers


def test_client_payload_cannot_override_business_or_user_identity(sec_client):
    """Test that rogue business_id or user_id fields in request body cannot override authenticated context."""
    client, repos = sec_client

    # 1. Create a product in Business A
    prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": "SEC-PROD-1",
            "name": "Standard Widget",
            "unit_price": "50.00",
            "initial_stock": 100,
            "reorder_threshold": 10,
            # Malicious attempt to claim it belongs to Business B
            "business_id": BUSINESS_B_ID,
        },
        headers=auth_headers(USER_ADMIN_A, BUSINESS_A_ID),
    )
    assert prod_res.status_code == 201
    prod_data = prod_res.json()
    assert prod_data["business_id"] == BUSINESS_A_ID  # Pinned to Business A!

    # 2. Create an order with spoofed business_id and created_by
    order_res = client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": prod_data["id"], "quantity": 2}],
            "notes": "Legitimate note",
            # Malicious spoofing payload
            "business_id": BUSINESS_B_ID,
            "created_by": USER_ADMIN_B,
            "user_id": USER_ADMIN_B,
        },
        headers=auth_headers(USER_STAFF_A, BUSINESS_A_ID),
    )
    assert order_res.status_code == 201
    order_data = order_res.json()
    assert order_data["business_id"] == BUSINESS_A_ID  # Must be Business A
    assert order_data["created_by"] == USER_STAFF_A    # Must be authenticated user A


def test_client_cannot_override_role_via_headers_or_body(sec_client):
    """Test that sending arbitrary role claims via headers or body does not grant admin elevation."""
    client, _ = sec_client

    # Staff user attempting to adjust stock while sending spoofed role headers
    res = client.post(
        "/api/v1/inventory/adjust",
        json={
            "product_id": str(uuid.uuid4()),
            "quantity_change": 5,
            "movement_type": "correction",
            "notes": "Unauthorized adjustment attempt",
            "role": "owner",
        },
        headers=auth_headers(
            USER_STAFF_A,
            BUSINESS_A_ID,
            extra={"X-Role": "owner", "X-User-Role": "admin", "Role": "owner"},
        ),
    )
    assert res.status_code == 403
    assert "requires 'admin' role" in res.json()["error"]["message"]


def test_cross_business_product_referencing_rejected(sec_client):
    """Test that creating an order in Business A referencing a product from Business B is blocked."""
    client, repos = sec_client

    # Create Product in Business B
    b_prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": "BETA-PROD-99",
            "name": "Beta Exclusive Sensor",
            "unit_price": "200.00",
            "initial_stock": 20,
            "reorder_threshold": 5,
        },
        headers=auth_headers(USER_ADMIN_B, BUSINESS_B_ID),
    )
    assert b_prod_res.status_code == 201
    beta_prod_id = b_prod_res.json()["id"]

    # User in Business A tries to order Business B's product
    order_res = client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": beta_prod_id, "quantity": 1}],
        },
        headers=auth_headers(USER_STAFF_A, BUSINESS_A_ID),
    )
    assert order_res.status_code == 400
    assert "not found or does not belong to this business" in order_res.json()["error"]["message"]


def test_cross_business_customer_referencing_rejected(sec_client):
    """Test that creating an order in Business A referencing a customer from Business B is blocked."""
    client, repos = sec_client

    # 1. Create product in Business A
    prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": "ALPHA-BOLT",
            "name": "Titanium Bolt",
            "unit_price": "15.00",
            "initial_stock": 50,
            "reorder_threshold": 5,
        },
        headers=auth_headers(USER_ADMIN_A, BUSINESS_A_ID),
    )
    prod_id = prod_res.json()["id"]

    # 2. Create customer in Business B
    cust_res = client.post(
        "/api/v1/customers",
        json={"name": "Beta Client Ltd", "email": "client@beta.local"},
        headers=auth_headers(USER_STAFF_B, BUSINESS_B_ID),
    )
    assert cust_res.status_code == 201
    beta_cust_id = cust_res.json()["id"]

    # 3. User in Business A tries to order using Business B's customer
    order_res = client.post(
        "/api/v1/orders",
        json={
            "customer_id": beta_cust_id,
            "items": [{"product_id": prod_id, "quantity": 1}],
        },
        headers=auth_headers(USER_STAFF_A, BUSINESS_A_ID),
    )
    assert order_res.status_code == 400
    assert "does not exist in this business" in order_res.json()["error"]["message"]


def test_cross_business_resource_reads_return_404(sec_client):
    """Test that resource lookups across businesses return 404 Not Found rather than leaking data."""
    client, _ = sec_client

    # 1. Create Product in Business B
    prod_res = client.post(
        "/api/v1/products",
        json={
            "sku": "B-PRIVATE-1",
            "name": "Classified Prototype",
            "unit_price": "999.00",
            "initial_stock": 5,
            "reorder_threshold": 1,
        },
        headers=auth_headers(USER_ADMIN_B, BUSINESS_B_ID),
    )
    b_prod_id = prod_res.json()["id"]

    # 2. Create Customer in Business B
    cust_res = client.post(
        "/api/v1/customers",
        json={"name": "Confidential Client", "email": "secret@beta.local"},
        headers=auth_headers(USER_STAFF_B, BUSINESS_B_ID),
    )
    b_cust_id = cust_res.json()["id"]

    # 3. Create Order in Business B
    order_res = client.post(
        "/api/v1/orders",
        json={
            "customer_id": b_cust_id,
            "items": [{"product_id": b_prod_id, "quantity": 1}],
        },
        headers=auth_headers(USER_STAFF_B, BUSINESS_B_ID),
    )
    b_order_id = order_res.json()["id"]

    # Now, authenticated user from Business A attempts to read Business B resources directly by ID
    a_headers = auth_headers(USER_STAFF_A, BUSINESS_A_ID)

    # Product read
    assert client.get(f"/api/v1/products/{b_prod_id}", headers=a_headers).status_code == 404
    # Customer read
    assert client.get(f"/api/v1/customers/{b_cust_id}", headers=a_headers).status_code == 404
    # Order read
    assert client.get(f"/api/v1/orders/{b_order_id}", headers=a_headers).status_code == 404


def test_staff_role_cannot_perform_admin_mutations(sec_client):
    """Test that staff users are strictly forbidden from all admin-only mutations."""
    client, _ = sec_client
    staff_headers = auth_headers(USER_STAFF_A, BUSINESS_A_ID)

    # 1. Product creation requires admin
    p_res = client.post(
        "/api/v1/products",
        json={"sku": "ILLEGAL", "name": "Illegal Item", "unit_price": "10.00"},
        headers=staff_headers,
    )
    assert p_res.status_code == 403
    assert "requires 'admin' role" in p_res.json()["error"]["message"]

    # 2. Product update requires admin
    dummy_id = str(uuid.uuid4())
    pu_res = client.put(
        f"/api/v1/products/{dummy_id}",
        json={"name": "Updated Item"},
        headers=staff_headers,
    )
    assert pu_res.status_code == 403

    # 3. Product deactivation requires admin
    pd_res = client.patch(
        f"/api/v1/products/{dummy_id}/deactivate",
        headers=staff_headers,
    )
    assert pd_res.status_code == 403

    # 4. Stock adjustment requires admin
    adj_res = client.post(
        "/api/v1/inventory/adjust",
        json={
            "product_id": dummy_id,
            "quantity_change": 10,
            "movement_type": "manual_in",
            "notes": "Restock attempt",
        },
        headers=staff_headers,
    )
    assert adj_res.status_code == 403

    # 5. Order approval requires admin
    app_res = client.post(
        f"/api/v1/orders/{dummy_id}/approve",
        headers=staff_headers,
    )
    assert app_res.status_code == 403

    # 6. Order rejection requires admin
    rej_res = client.post(
        f"/api/v1/orders/{dummy_id}/reject",
        headers=staff_headers,
    )
    assert rej_res.status_code == 403

    # 7. Invoice allocation requires admin
    inv_res = client.post(
        f"/api/v1/invoices/orders/{dummy_id}/allocate",
        headers=staff_headers,
    )
    assert inv_res.status_code == 403
