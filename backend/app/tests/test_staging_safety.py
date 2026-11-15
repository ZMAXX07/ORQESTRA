"""Automated test suite verifying staging repository safety, startup interlocks, and health check truthfulness.

Validates:
1. Staging and production fail startup if Supabase repositories cannot initialize.
2. In-memory repositories are only allowed in explicitly configured development or test environments.
3. Staging cannot silently operate with temporary in-memory data.
4. Health check truthfully evaluates and reports expected database connectivity.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.api import deps
from backend.app.core.config import Settings, is_in_memory_allowed
from backend.app.main import create_application
from backend.app.repositories.business_repository import InMemoryBusinessRepository
from backend.app.repositories.audit_repository import InMemoryAuditLogRepository
from backend.app.repositories.product_repository import InMemoryProductRepository
from backend.app.repositories.inventory_repository import InMemoryInventoryRepository
from backend.app.repositories.customer_repository import InMemoryCustomerRepository
from backend.app.repositories.order_repository import InMemoryOrderRepository
from backend.app.repositories.invoice_repository import InMemoryInvoiceRepository
from backend.app.services.health import HealthService, check_database_connectivity, _DB_PROBE_CACHE
from backend.app.tests.test_jwt_verification import TEST_SECRET


@pytest.fixture(autouse=True)
def clean_repo_state():
    """Reset repository singletons and probe caches before and after every test."""
    deps.reset_repository_instances()
    _DB_PROBE_CACHE["status"] = None
    yield
    deps.reset_repository_instances()
    _DB_PROBE_CACHE["status"] = None


def test_is_in_memory_allowed_truth_table():
    """Verify in-memory repositories are strictly restricted to local development or test environments."""
    assert is_in_memory_allowed("development") is True
    assert is_in_memory_allowed("test") is True
    assert is_in_memory_allowed("testing") is True
    assert is_in_memory_allowed("local") is True

    # Staging, production, and unknown environments must NEVER allow in-memory fallback
    assert is_in_memory_allowed("staging") is False
    assert is_in_memory_allowed("production") is False
    assert is_in_memory_allowed("sandbox") is False
    assert is_in_memory_allowed("preview") is False
    assert is_in_memory_allowed("") is False
    assert is_in_memory_allowed(None) is False


def test_staging_fails_startup_when_database_unconfigured():
    """Verify staging environment fails fast on startup if database credentials are missing."""
    staging_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
        SUPABASE_JWT_SECRET=TEST_SECRET,
    )

    app = create_application(settings=staging_settings)
    with pytest.raises(RuntimeError) as exc_info:
        with TestClient(app):
            pass

    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
    assert "Staging environment requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY" in str(exc_info.value)


def test_production_fails_startup_when_database_unconfigured():
    """Verify production environment fails fast on startup if database credentials are missing."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
        SUPABASE_JWT_SECRET=TEST_SECRET,
    )

    app = create_application(settings=prod_settings)
    with pytest.raises(RuntimeError) as exc_info:
        with TestClient(app):
            pass

    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
    assert "Production environment requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY" in str(exc_info.value)


def test_staging_strictly_blocks_in_memory_repositories():
    """Verify staging strictly rejects all InMemory repository instances."""
    staging_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
        SUPABASE_JWT_SECRET=TEST_SECRET,
    )

    # 1. Business Repository
    deps._business_repository_instance = InMemoryBusinessRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_business_repository(settings=staging_settings)
    assert "InMemoryBusinessRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 2. Audit Repository
    deps._audit_repository_instance = InMemoryAuditLogRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_audit_repository(settings=staging_settings)
    assert "InMemoryAuditLogRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 3. Product Repository
    deps._product_repository_instance = InMemoryProductRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_product_repository(settings=staging_settings)
    assert "InMemoryProductRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 4. Inventory Repository
    deps._inventory_repository_instance = InMemoryInventoryRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_inventory_repository(settings=staging_settings)
    assert "InMemoryInventoryRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 5. Customer Repository
    deps._customer_repository_instance = InMemoryCustomerRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_customer_repository(settings=staging_settings)
    assert "InMemoryCustomerRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 6. Order Repository
    deps._order_repository_instance = InMemoryOrderRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_order_repository(settings=staging_settings)
    assert "InMemoryOrderRepository cannot be selected or used in a staging environment" in str(exc.value)

    # 7. Invoice Repository
    deps._invoice_repository_instance = InMemoryInvoiceRepository()
    with pytest.raises(RuntimeError) as exc:
        deps.get_invoice_repository(settings=staging_settings)
    assert "InMemoryInvoiceRepository cannot be selected or used in a staging environment" in str(exc.value)


def test_development_and_test_allow_in_memory_repositories():
    """Verify local development and test environments gracefully instantiate in-memory repositories."""
    dev_settings = Settings(
        ENVIRONMENT="development",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
    )
    b_repo = deps.get_business_repository(settings=dev_settings)
    assert isinstance(b_repo, InMemoryBusinessRepository)

    test_settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
    )
    deps.reset_repository_instances()
    t_repo = deps.get_business_repository(settings=test_settings)
    assert isinstance(t_repo, InMemoryBusinessRepository)


def test_staging_fails_startup_when_service_role_key_missing():
    """Verify staging environment fails fast on startup if service role key is missing."""
    staging_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY=None,
        SUPABASE_JWT_SECRET=TEST_SECRET,
    )

    app = create_application(settings=staging_settings)
    with pytest.raises(RuntimeError) as exc_info:
        with TestClient(app):
            pass

    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
    assert "Staging environment requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY" in str(exc_info.value)


def test_staging_valid_configuration_initializes_supabase_repository():
    """Verify valid staging Supabase configuration instantiates Supabase-backed repositories."""
    valid_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="valid-secret-token",
        SUPABASE_JWT_SECRET=TEST_SECRET,
    )
    deps.reset_repository_instances()
    b_repo = deps.get_business_repository(settings=valid_settings)
    assert "Supabase" in type(b_repo).__name__


@pytest.mark.anyio
async def test_health_check_database_temporarily_unavailable():
    """Verify health check reports 'error' and 'unhealthy' when the database endpoint is unreachable."""
    s5_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL="https://127.0.0.1:59999",  # closed port
        SUPABASE_SERVICE_ROLE_KEY="some-key",
    )
    health_service = HealthService(settings=s5_settings)
    result = await health_service.get_health_status()

    assert result.status == "unhealthy"
    assert result.components["database"].status == "error"
    assert "Database probe failed" in result.components["database"].details


@pytest.mark.anyio
async def test_health_check_database_unconfigured_in_staging():
    """Verify health check reports 'error' and 'unhealthy' if database is unconfigured in staging."""
    staging_settings = Settings(
        ENVIRONMENT="staging",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
    )
    health_service = HealthService(settings=staging_settings)
    result = await health_service.get_health_status()

    assert result.status == "unhealthy"
    assert result.components["database"].status == "error"
    assert "credentials unconfigured in staging" in result.components["database"].details


@pytest.mark.anyio
async def test_health_check_database_not_connected_in_test():
    """Verify health check reports 'not_connected' and 'healthy' in test environment without credentials."""
    test_settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_URL=None,
        SUPABASE_SERVICE_ROLE_KEY=None,
    )
    health_service = HealthService(settings=test_settings)
    result = await health_service.get_health_status()

    assert result.status == "healthy"
    assert result.components["database"].status == "not_connected"

