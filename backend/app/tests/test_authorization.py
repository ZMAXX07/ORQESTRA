"""Automated tests for business multi-tenant isolation and role enforcement."""

import uuid
import pytest
from fastapi.testclient import TestClient
import backend.app.api.deps as deps
from backend.app.api.deps import get_business_repository, get_settings
from backend.app.core.config import Settings
from backend.app.main import create_application
from backend.app.repositories.business_repository import InMemoryBusinessRepository
from backend.app.tests.test_jwt_verification import TEST_SECRET, create_token

USER_OWNER_ID = "00000000-0000-0000-0000-000000000001"
USER_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
USER_STAFF_ID = "00000000-0000-0000-0000-000000000003"
USER_OUTSIDER_ID = "00000000-0000-0000-0000-000000000099"
USER_INACTIVE_ID = "00000000-0000-0000-0000-000000000088"

BUSINESS_ALPHA_ID = "bbbbbbbb-0001-0000-0000-000000000001"
BUSINESS_BETA_ID = "bbbbbbbb-0002-0000-0000-000000000002"


@pytest.fixture
def auth_test_client() -> TestClient:
    """Fixture configuring FastAPI client with test JWT secret and populated in-memory repository."""
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        CORS_ORIGINS=["http://testserver"],
    )

    repo = InMemoryBusinessRepository()
    # Business Alpha memberships
    repo.add_membership(USER_OWNER_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "owner")
    repo.add_membership(USER_ADMIN_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "admin")
    repo.add_membership(USER_STAFF_ID, BUSINESS_ALPHA_ID, "Alpha Corp", "staff")

    # Inactive membership in Alpha
    repo._memberships.append({
        "user_id": USER_INACTIVE_ID,
        "business_id": BUSINESS_ALPHA_ID,
        "business_name": "Alpha Corp",
        "role": "staff",
        "is_active": False,
    })

    # Business Beta memberships (Outsider belongs to Beta only)
    repo.add_membership(USER_OUTSIDER_ID, BUSINESS_BETA_ID, "Beta Logistics", "owner")

    app = create_application(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_business_repository] = lambda: repo

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_auth_me_returns_profile_and_memberships(auth_test_client: TestClient):
    """Test authenticated user fetches their identity and business memberships."""
    token = create_token(sub=USER_OWNER_ID, email="owner@alphacorp.local")
    response = auth_test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["user"]["user_id"] == USER_OWNER_ID
    assert data["user"]["email"] == "owner@alphacorp.local"
    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["business_id"] == BUSINESS_ALPHA_ID
    assert data["memberships"][0]["role"] == "owner"


def test_cross_business_access_denied(auth_test_client: TestClient):
    """Test user from Business Beta cannot access Business Alpha (returns 403)."""
    outsider_token = create_token(sub=USER_OUTSIDER_ID, email="outsider@betalogistics.local")

    # Attempting to access Business Alpha with Business Beta user's token
    response = auth_test_client.get(
        "/api/v1/auth/business-context",
        headers={
            "Authorization": f"Bearer {outsider_token}",
            "X-Business-ID": BUSINESS_ALPHA_ID,
        },
    )

    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_403"
    assert "permission to access this business" in data["error"]["message"]


def test_forged_random_business_id_denied(auth_test_client: TestClient):
    """Test user providing forged random business ID is denied with 403."""
    staff_token = create_token(sub=USER_STAFF_ID, email="staff@alphacorp.local")
    forged_business_id = str(uuid.uuid4())

    response = auth_test_client.get(
        "/api/v1/auth/business-context",
        headers={
            "Authorization": f"Bearer {staff_token}",
            "X-Business-ID": forged_business_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "HTTP_403"


def test_inactive_membership_denied(auth_test_client: TestClient):
    """Test deactivated user cannot access business context."""
    inactive_token = create_token(sub=USER_INACTIVE_ID, email="inactive@alphacorp.local")

    response = auth_test_client.get(
        "/api/v1/auth/business-context",
        headers={
            "Authorization": f"Bearer {inactive_token}",
            "X-Business-ID": BUSINESS_ALPHA_ID,
        },
    )

    assert response.status_code == 403
    assert "permission to access this business" in response.json()["error"]["message"]


def test_authorized_business_access(auth_test_client: TestClient):
    """Test verified member can access their own business context."""
    staff_token = create_token(sub=USER_STAFF_ID, email="staff@alphacorp.local")

    response = auth_test_client.get(
        "/api/v1/auth/business-context",
        headers={
            "Authorization": f"Bearer {staff_token}",
            "X-Business-ID": BUSINESS_ALPHA_ID,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["business_id"] == BUSINESS_ALPHA_ID
    assert data["role"] == "staff"


def test_role_enforcement_admin_endpoint(auth_test_client: TestClient):
    """Test role hierarchy: staff is rejected on admin endpoint; admin and owner are allowed."""
    staff_token = create_token(sub=USER_STAFF_ID)
    admin_token = create_token(sub=USER_ADMIN_ID)
    owner_token = create_token(sub=USER_OWNER_ID)

    # 1. Staff -> Admin endpoint should fail with 403
    staff_res = auth_test_client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {staff_token}", "X-Business-ID": BUSINESS_ALPHA_ID},
    )
    assert staff_res.status_code == 403
    assert "requires 'admin' role" in staff_res.json()["error"]["message"]

    # 2. Admin -> Admin endpoint should succeed with 200
    admin_res = auth_test_client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {admin_token}", "X-Business-ID": BUSINESS_ALPHA_ID},
    )
    assert admin_res.status_code == 200
    assert admin_res.json()["role"] == "admin"

    # 3. Owner -> Admin endpoint should succeed with 200 (Owner exceeds Admin)
    owner_res = auth_test_client.get(
        "/api/v1/auth/admin-check",
        headers={"Authorization": f"Bearer {owner_token}", "X-Business-ID": BUSINESS_ALPHA_ID},
    )
    assert owner_res.status_code == 200
    assert owner_res.json()["role"] == "owner"


def test_missing_business_id_header(auth_test_client: TestClient):
    """Test omission of X-Business-ID returns 400."""
    owner_token = create_token(sub=USER_OWNER_ID)
    response = auth_test_client.get(
        "/api/v1/auth/business-context",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 400


def test_production_environment_blocks_in_memory_repository():
    """Verify production environment strictly forbids all InMemory repositories."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
    )

    # 1. Business Repository
    deps._business_repository_instance = None
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_business_repository(settings=prod_settings)
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)

    deps._business_repository_instance = InMemoryBusinessRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_business_repository(settings=prod_settings)
    assert "InMemoryBusinessRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._business_repository_instance = None

    # 2. Audit Repository
    deps._audit_repository_instance = deps.InMemoryAuditLogRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_audit_repository(settings=prod_settings)
    assert "InMemoryAuditLogRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._audit_repository_instance = None

    # 3. Product Repository
    deps._product_repository_instance = deps.InMemoryProductRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_product_repository(settings=prod_settings)
    assert "InMemoryProductRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._product_repository_instance = None

    # 4. Inventory Repository
    deps._inventory_repository_instance = deps.InMemoryInventoryRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_inventory_repository(settings=prod_settings)
    assert "InMemoryInventoryRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._inventory_repository_instance = None

    # 5. Customer Repository
    deps._customer_repository_instance = deps.InMemoryCustomerRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_customer_repository(settings=prod_settings)
    assert "InMemoryCustomerRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._customer_repository_instance = None

    # 6. Order Repository
    deps._order_repository_instance = deps.InMemoryOrderRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_order_repository(settings=prod_settings)
    assert "InMemoryOrderRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._order_repository_instance = None

    # 7. Invoice Repository
    deps._invoice_repository_instance = deps.InMemoryInvoiceRepository()
    with pytest.raises(RuntimeError) as exc_info:
        deps.get_invoice_repository(settings=prod_settings)
    assert "InMemoryInvoiceRepository cannot be selected or used in a production environment" in str(exc_info.value)
    deps._invoice_repository_instance = None

