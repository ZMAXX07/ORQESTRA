"""Tests for AI intake rate limiting, window behavior, tenant isolation, and fail-safe operation."""

import time
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
    get_rate_limiter,
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
from backend.app.services.rate_limiter import InMemoryRateLimiter
from backend.app.tests.test_jwt_verification import TEST_SECRET, create_token

USER_STAFF_A_ID = "00000000-0000-0000-0000-000000000001"
USER_STAFF_B_ID = "00000000-0000-0000-0000-000000000002"
BUSINESS_1_ID = "11111111-1111-1111-1111-111111111111"
BUSINESS_2_ID = "22222222-2222-2222-2222-222222222222"

TOKEN_STAFF_A = create_token(sub=USER_STAFF_A_ID, email="staff_a@biz1.local")
TOKEN_STAFF_B = create_token(sub=USER_STAFF_B_ID, email="staff_b@biz1.local")


# -----------------------------------------------------------------------------
# 1. Direct Unit Tests for InMemoryRateLimiter
# -----------------------------------------------------------------------------

def test_rate_limiter_unit_allows_within_threshold():
    """Verify rate limiter allows requests up to max_requests."""
    limiter = InMemoryRateLimiter()
    key = "test-business:test-user"

    for _ in range(5):
        allowed, retry_after = limiter.check_rate_limit(key, max_requests=5, window_seconds=60)
        assert allowed is True
        assert retry_after == 0


def test_rate_limiter_unit_blocks_exceeding_threshold():
    """Verify rate limiter returns (False, retry_after) once limit is reached."""
    limiter = InMemoryRateLimiter()
    key = "test-business:test-user"

    for _ in range(3):
        allowed, _ = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
        assert allowed is True

    # 4th request must be rejected
    allowed, retry_after = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
    assert allowed is False
    assert retry_after > 0
    assert retry_after <= 60


def test_rate_limiter_unit_window_sliding_expiration(monkeypatch):
    """Verify that requests become permitted again after window_seconds elapse."""
    limiter = InMemoryRateLimiter()
    key = "test-business:test-user"

    current_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    # Exhaust limit
    for _ in range(2):
        allowed, _ = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
        assert allowed is True

    allowed, retry_after = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
    assert allowed is False
    assert retry_after == 10

    # Advance time past the 10-second window
    current_time = 1011.0
    allowed, retry_after = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
    assert allowed is True
    assert retry_after == 0


def test_rate_limiter_unit_isolation_between_keys():
    """Verify that exhausting rate limit on one key does not affect another key."""
    limiter = InMemoryRateLimiter()
    key_a = "biz-1:user-a"
    key_b = "biz-1:user-b"
    key_c = "biz-2:user-a"

    # Exhaust key_a
    for _ in range(2):
        limiter.check_rate_limit(key_a, max_requests=2, window_seconds=60)

    allowed_a, _ = limiter.check_rate_limit(key_a, max_requests=2, window_seconds=60)
    assert allowed_a is False

    # key_b and key_c should still be allowed
    allowed_b, _ = limiter.check_rate_limit(key_b, max_requests=2, window_seconds=60)
    allowed_c, _ = limiter.check_rate_limit(key_c, max_requests=2, window_seconds=60)
    assert allowed_b is True
    assert allowed_c is True


def test_rate_limiter_unit_fail_safe_on_exception(monkeypatch):
    """Verify limiter fails open (returns True, 0) if unexpected exception occurs."""
    limiter = InMemoryRateLimiter()

    def bad_monotonic():
        raise RuntimeError("Simulated clock malfunction")

    monkeypatch.setattr(time, "monotonic", bad_monotonic)

    allowed, retry_after = limiter.check_rate_limit("any-key", max_requests=5, window_seconds=60)
    assert allowed is True
    assert retry_after == 0


# -----------------------------------------------------------------------------
# 2. Endpoint Integration Tests with TestClient
# -----------------------------------------------------------------------------

@pytest.fixture
def rate_limit_app_env():
    """Builds test client with tight rate limit settings (2 requests per 60s)."""
    settings = Settings(
        ENVIRONMENT="test",
        SUPABASE_JWT_SECRET=TEST_SECRET,
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHM="HS256",
        CORS_ORIGINS=["http://testserver"],
        AI_API_KEY="test-mock-key",
        AI_RATE_LIMIT_REQUESTS=2,
        AI_RATE_LIMIT_WINDOW_SECONDS=60,
    )

    business_repo = InMemoryBusinessRepository()
    business_repo.add_membership(USER_STAFF_A_ID, BUSINESS_1_ID, "Business 1", "staff")
    business_repo.add_membership(USER_STAFF_B_ID, BUSINESS_1_ID, "Business 1", "staff")
    business_repo.add_membership(USER_STAFF_A_ID, BUSINESS_2_ID, "Business 2", "staff")

    audit_repo = InMemoryAuditLogRepository()
    product_repo = InMemoryProductRepository()
    inventory_repo = InMemoryInventoryRepository(product_repo=product_repo, audit_repo=audit_repo)
    customer_repo = InMemoryCustomerRepository()
    order_repo = InMemoryOrderRepository(product_repo=product_repo, audit_repo=audit_repo)
    invoice_repo = InMemoryInvoiceRepository()
    limiter = InMemoryRateLimiter()

    app = create_application(settings=settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_business_repository] = lambda: business_repo
    app.dependency_overrides[get_audit_repository] = lambda: audit_repo
    app.dependency_overrides[get_product_repository] = lambda: product_repo
    app.dependency_overrides[get_inventory_repository] = lambda: inventory_repo
    app.dependency_overrides[get_customer_repository] = lambda: customer_repo
    app.dependency_overrides[get_order_repository] = lambda: order_repo
    app.dependency_overrides[get_invoice_repository] = lambda: invoice_repo
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    with TestClient(app) as client:
        yield {
            "client": client,
            "settings": settings,
            "limiter": limiter,
        }
    app.dependency_overrides.clear()


def test_endpoint_rate_limit_enforced_returns_429(rate_limit_app_env, monkeypatch):
    """Verify endpoint allows up to AI_RATE_LIMIT_REQUESTS, then returns HTTP 429."""
    client = rate_limit_app_env["client"]

    # Mock extract_and_match_order to return dummy proposal without hitting external API
    from backend.app.services.ai_intake import AIIntakeService
    from backend.app.schemas.ai_intake import OrderIntakeResponse

    dummy_response = OrderIntakeResponse(
        raw_message="mock message",
        items=[],
        ambiguities=[],
        validation_errors=[],
        can_create_draft=False,
    )
    async def mock_extract(*a, **k):
        return dummy_response

    monkeypatch.setattr(AIIntakeService, "extract_and_match_order", mock_extract)

    headers = {
        "Authorization": f"Bearer {TOKEN_STAFF_A}",
        "X-Business-ID": BUSINESS_1_ID,
    }
    payload = {"message": "Please send 3 pens"}

    # Request 1: Allowed (1/2)
    resp1 = client.post("/api/v1/orders/ai-intake", headers=headers, json=payload)
    assert resp1.status_code == 200

    # Request 2: Allowed (2/2)
    resp2 = client.post("/api/v1/orders/ai-intake", headers=headers, json=payload)
    assert resp2.status_code == 200

    # Request 3: Blocked by rate limiter (HTTP 429)
    resp3 = client.post("/api/v1/orders/ai-intake", headers=headers, json=payload)
    assert resp3.status_code == 429
    body = resp3.json()

    assert "error" in body
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Rate limit exceeded" in body["error"]["message"]
    assert "retry_after" in body["error"]["details"]
    assert body["error"]["details"]["retry_after"] > 0
    assert "Retry-After" in resp3.headers


def test_endpoint_rate_limit_user_and_tenant_isolation(rate_limit_app_env, monkeypatch):
    """Verify that User A hitting the rate limit does not block User B or User A in Business 2."""
    client = rate_limit_app_env["client"]

    from backend.app.services.ai_intake import AIIntakeService
    from backend.app.schemas.ai_intake import OrderIntakeResponse

    dummy_response = OrderIntakeResponse(
        raw_message="mock message",
        items=[],
        ambiguities=[],
        validation_errors=[],
        can_create_draft=False,
    )
    async def mock_extract(*a, **k):
        return dummy_response

    monkeypatch.setattr(AIIntakeService, "extract_and_match_order", mock_extract)

    # Exhaust limit for User A in Business 1 (limit = 2)
    headers_a_biz1 = {"Authorization": f"Bearer {TOKEN_STAFF_A}", "X-Business-ID": BUSINESS_1_ID}
    client.post("/api/v1/orders/ai-intake", headers=headers_a_biz1, json={"message": "Please send 5 pens"})
    client.post("/api/v1/orders/ai-intake", headers=headers_a_biz1, json={"message": "Please send 5 pencils"})

    # 3rd request for User A in Biz 1 is blocked
    resp_a_blocked = client.post("/api/v1/orders/ai-intake", headers=headers_a_biz1, json={"message": "Please send 5 erasers"})
    assert resp_a_blocked.status_code == 429

    # User B in Business 1 must NOT be blocked
    headers_b_biz1 = {"Authorization": f"Bearer {TOKEN_STAFF_B}", "X-Business-ID": BUSINESS_1_ID}
    resp_b = client.post("/api/v1/orders/ai-intake", headers=headers_b_biz1, json={"message": "Order from user B"})
    assert resp_b.status_code == 200

    # User A in Business 2 must NOT be blocked (different business context)
    headers_a_biz2 = {"Authorization": f"Bearer {TOKEN_STAFF_A}", "X-Business-ID": BUSINESS_2_ID}
    resp_a_biz2 = client.post("/api/v1/orders/ai-intake", headers=headers_a_biz2, json={"message": "Order from user A in biz 2"})
    assert resp_a_biz2.status_code == 200


def test_unauthenticated_request_rejected_without_consuming_rate_limit(rate_limit_app_env):
    """Verify unauthenticated requests fail with 401 and do not affect the rate limiter."""
    client = rate_limit_app_env["client"]
    limiter = rate_limit_app_env["limiter"]

    # Request with no Authorization header
    resp = client.post(
        "/api/v1/orders/ai-intake",
        headers={"X-Business-ID": BUSINESS_1_ID},
        json={"message": "unauthenticated message"},
    )
    assert resp.status_code == 401
    # Limiter history should remain completely empty
    assert len(limiter._history) == 0
