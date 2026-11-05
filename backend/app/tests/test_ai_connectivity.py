"""Unit and integration tests for AI provider connectivity, Google Gemini integration, and safe fallback."""

from decimal import Decimal
import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.repositories.customer_repository import InMemoryCustomerRepository
from backend.app.repositories.product_repository import InMemoryProductRepository
from backend.app.schemas.ai_intake import OrderIntakeResponse
from backend.app.schemas.products import ProductCreate
from backend.app.services.ai_intake import (
    AIConfigurationError,
    AIExtractionError,
    AIIntakeService,
    check_ai_provider_connectivity,
)
from backend.app.services.health import HealthService


# -----------------------------------------------------------------------------
# 1. Credential & Provider Resolution Tests
# -----------------------------------------------------------------------------

def test_gemini_configuration_defaults():
    """Verify that AI_PROVIDER='gemini' configures the official Google endpoint and model."""
    settings = Settings(AI_PROVIDER="gemini")
    assert settings.effective_ai_provider == "gemini"
    assert settings.effective_ai_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert settings.effective_ai_model == "gemini-1.5-flash"


def test_gemini_custom_model_and_key_override():
    """Verify custom Gemini model and GEMINI_API_KEY environment resolution."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="test-gemini-secret-key",
        AI_MODEL="gemini-2.5-flash",
    )
    assert settings.effective_ai_provider == "gemini"
    assert settings.effective_ai_api_key == "test-gemini-secret-key"
    assert settings.effective_ai_model == "gemini-2.5-flash"
    assert settings.effective_ai_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_gemini_auto_detection_from_gemini_key():
    """Verify that setting GEMINI_API_KEY automatically selects the gemini provider if AI_PROVIDER is unset."""
    settings = Settings(AI_PROVIDER=None, GEMINI_API_KEY="test-key")
    assert settings.effective_ai_provider == "gemini"
    assert settings.effective_ai_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert settings.effective_ai_model == "gemini-1.5-flash"


def test_openai_backward_compatibility():
    """Verify that default settings preserve OpenAI compatibility."""
    settings = Settings(AI_PROVIDER="openai", AI_API_KEY="sk-test-key", AI_MODEL="gpt-4o-mini")
    assert settings.effective_ai_provider == "openai"
    assert settings.effective_ai_api_key == "sk-test-key"
    assert settings.effective_ai_base_url == "https://api.openai.com/v1"
    assert settings.effective_ai_model == "gpt-4o-mini"


def test_custom_ai_base_url_resolution():
    """Verify AI_BASE_URL override is respected for proxies or local mock servers."""
    settings = Settings(AI_PROVIDER="gemini", AI_BASE_URL="https://custom-gateway.local/v1/")
    assert settings.effective_ai_base_url == "https://custom-gateway.local/v1"


# -----------------------------------------------------------------------------
# 2. Connectivity Probe & Health Reporting Tests
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ai_connectivity_missing_credentials():
    """Verify that when AI_API_KEY and GEMINI_API_KEY are missing, connectivity reports not_configured."""
    settings = Settings(AI_API_KEY=None, GEMINI_API_KEY=None, AI_PROVIDER="gemini")
    status = await check_ai_provider_connectivity(settings)
    assert status.status == "not_configured"
    assert "not configured" in status.details
    assert "Google Gemini" in status.details

    # Also with blank whitespace key
    settings_blank = Settings(AI_API_KEY="   ", GEMINI_API_KEY=None, AI_PROVIDER="openai")
    status_blank = await check_ai_provider_connectivity(settings_blank)
    assert status_blank.status == "not_configured"


@pytest.mark.anyio
async def test_ai_connectivity_unsupported_provider():
    """Verify that unsupported providers report error truthfully."""
    settings = Settings(AI_API_KEY="test-key", AI_PROVIDER="unsupported-engine")
    status = await check_ai_provider_connectivity(settings)
    assert status.status == "error"
    assert "Unsupported AI provider" in status.details


@pytest.mark.anyio
async def test_gemini_connectivity_successful_probe():
    """Verify that a successful 200 response from Gemini /models reports connected."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="mock-gemini-key",
        AI_MODEL="gemini-1.5-flash",
        AI_BASE_URL="https://mock.generativelanguage.googleapis.com/v1beta/openai",
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://mock.generativelanguage.googleapis.com/v1beta/openai/models"
        assert request.headers.get("Authorization") == "Bearer mock-gemini-key"
        return httpx.Response(200, json={"data": [{"id": "gemini-1.5-flash"}]})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status = await check_ai_provider_connectivity(settings, client=client)
        assert status.status == "connected"
        assert "Google Gemini" in status.details
        assert "gemini-1.5-flash" in status.details
        # Credentials must NEVER appear in diagnostic details
        assert "mock-gemini-key" not in status.details


@pytest.mark.anyio
async def test_gemini_connectivity_auth_failure():
    """Verify that 401/403 from Gemini reports error without exposing secrets."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="invalid-gemini-key",
        AI_BASE_URL="https://mock.generativelanguage.googleapis.com/v1beta/openai",
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "API key not valid. Please pass a valid API key."}})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status = await check_ai_provider_connectivity(settings, client=client)
        assert status.status == "error"
        assert "authentication failed" in status.details.lower()
        # Credentials must NEVER appear in diagnostic details
        assert "invalid-gemini-key" not in status.details


@pytest.mark.anyio
async def test_gemini_connectivity_rate_limit():
    """Verify that 429 Too Many Requests from Gemini reports unavailable."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="valid-key",
        AI_BASE_URL="https://mock.generativelanguage.googleapis.com/v1beta/openai",
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Resource has been exhausted (e.g. check quota)."}})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status = await check_ai_provider_connectivity(settings, client=client)
        assert status.status == "unavailable"
        assert "rate limit" in status.details.lower()


@pytest.mark.anyio
async def test_gemini_connectivity_provider_down():
    """Verify that 502/503 from Gemini endpoint reports unavailable."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="valid-key",
        AI_BASE_URL="https://mock.generativelanguage.googleapis.com/v1beta/openai",
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status = await check_ai_provider_connectivity(settings, client=client)
        assert status.status == "unavailable"
        assert "503" in status.details


@pytest.mark.anyio
async def test_gemini_connectivity_timeout():
    """Verify that connection timeout reports unavailable."""
    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="valid-key",
        AI_BASE_URL="https://mock.generativelanguage.googleapis.com/v1beta/openai",
    )

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Read timed out")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        status = await check_ai_provider_connectivity(settings, client=client)
        assert status.status == "unavailable"
        assert "timed out" in status.details.lower()


@pytest.mark.anyio
async def test_gemini_health_service_integration():
    """Verify that HealthService truthfully reports not_configured when no key is set."""
    settings = Settings(AI_PROVIDER="gemini", AI_API_KEY=None, GEMINI_API_KEY=None)
    health_svc = HealthService(settings)
    res = await health_svc.get_health_status()
    assert res.components["ai_service"].status == "not_configured"
    assert "Google Gemini" in res.components["ai_service"].details


# -----------------------------------------------------------------------------
# 3. Gemini Order Intake & Human Approval Verification
# -----------------------------------------------------------------------------

@pytest.mark.anyio
async def test_gemini_order_extraction_structured_flow():
    """Verify that Google Gemini structured JSON extraction resolves against active product catalog."""
    prod_repo = InMemoryProductRepository()
    cust_repo = InMemoryCustomerRepository()

    p = await prod_repo.create_product(
        business_id="biz_alpha",
        product=ProductCreate(sku="NOTE-01", name="Spiral Notebook", unit_price=Decimal("4.50")),
        user_id="usr_admin",
    )

    # Mock Google Gemini OpenAI-compatible completions response
    async def mock_gemini_provider(*args, **kwargs) -> str:
        assert kwargs.get("model") == "gemini-1.5-flash"
        return """{
            "customer_name": "Deepak Sharma",
            "delivery_instructions": "Leave at front desk",
            "items": [
                {"candidate_product_name": "Spiral Notebook", "quantity": 10, "variant": null, "raw_text": "10 spiral notebooks"}
            ],
            "notes": "Deliver by 3 PM",
            "ambiguities": []
        }"""

    settings = Settings(
        AI_PROVIDER="gemini",
        GEMINI_API_KEY="mock-gemini-key",
        AI_MODEL="gemini-1.5-flash",
    )

    svc = AIIntakeService(provider_caller=mock_gemini_provider, settings=settings)
    result = await svc.extract_and_match_order(
        raw_message="Hi, I need 10 spiral notebooks delivered by 3 PM to front desk. Deepak Sharma.",
        business_id="biz_alpha",
        product_repo=prod_repo,
        customer_repo=cust_repo,
    )

    assert isinstance(result, OrderIntakeResponse)
    assert result.extracted_customer_name == "Deepak Sharma"
    assert result.delivery_instructions == "Leave at front desk"
    assert len(result.items) == 1

    item = result.items[0]
    assert item.match_status == "matched"
    assert item.matched_product.id == p.id
    assert item.unit_price == Decimal("4.50")
    assert item.line_total == Decimal("45.00")

    assert result.subtotal == Decimal("45.00")
    assert result.tax == Decimal("0.00")
    assert result.total_amount == Decimal("45.00")

    # Critical human-approval check: proposal is ready for review, but NO database records modified
    assert result.can_create_draft is True


@pytest.mark.anyio
async def test_gemini_malformed_response_handled_safely():
    """Verify that non-JSON output from Gemini raises clean AIExtractionError."""
    prod_repo = InMemoryProductRepository()
    cust_repo = InMemoryCustomerRepository()

    async def mock_bad_gemini_provider(*args, **kwargs) -> str:
        return "I am sorry, I cannot process this order."

    settings = Settings(AI_PROVIDER="gemini", GEMINI_API_KEY="mock-gemini-key")
    svc = AIIntakeService(provider_caller=mock_bad_gemini_provider, settings=settings)

    with pytest.raises(AIExtractionError) as exc_info:
        await svc.extract_and_match_order(
            raw_message="Order 5 notebooks please",
            business_id="biz_alpha",
            product_repo=prod_repo,
            customer_repo=cust_repo,
        )
    assert "malformed or invalid" in str(exc_info.value)


@pytest.mark.anyio
async def test_gemini_unconfigured_credentials_rejected():
    """Verify that invoking extraction without credentials raises AIConfigurationError."""
    prod_repo = InMemoryProductRepository()
    cust_repo = InMemoryCustomerRepository()

    settings = Settings(AI_PROVIDER="gemini", AI_API_KEY=None, GEMINI_API_KEY=None)
    svc = AIIntakeService(settings=settings)

    with pytest.raises(AIConfigurationError) as exc_info:
        await svc.extract_and_match_order(
            raw_message="Order 5 notebooks please",
            business_id="biz_alpha",
            product_repo=prod_repo,
            customer_repo=cust_repo,
        )
    assert "not configured" in str(exc_info.value)
