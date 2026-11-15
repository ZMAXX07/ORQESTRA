"""API dependency injection providers for authentication, authorization, and services."""

from typing import Callable, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from backend.app.core.config import (
    IN_MEMORY_ALLOWED_ENVIRONMENTS,
    Settings,
    get_settings,
    is_in_memory_allowed,
)
from backend.app.repositories.audit_repository import (
    BaseAuditLogRepository,
    InMemoryAuditLogRepository,
    SupabaseAuditLogRepository,
)
from backend.app.repositories.business_repository import (
    BaseBusinessRepository,
    InMemoryBusinessRepository,
    SupabaseBusinessRepository,
)
from backend.app.repositories.customer_repository import (
    BaseCustomerRepository,
    InMemoryCustomerRepository,
    SupabaseCustomerRepository,
)
from backend.app.repositories.inventory_repository import (
    BaseInventoryRepository,
    InMemoryInventoryRepository,
    SupabaseInventoryRepository,
)
from backend.app.repositories.order_repository import (
    BaseOrderRepository,
    InMemoryOrderRepository,
    SupabaseOrderRepository,
)
from backend.app.repositories.product_repository import (
    BaseProductRepository,
    InMemoryProductRepository,
    SupabaseProductRepository,
)
from backend.app.repositories.invoice_repository import (
    BaseInvoiceRepository,
    InMemoryInvoiceRepository,
    SupabaseInvoiceRepository,
)
from backend.app.schemas.auth import AppRole, AuthenticatedUser, BusinessMembership
from backend.app.services.ai_intake import AIIntakeService
from backend.app.services.auth import AuthenticationError, TokenVerificationService
from backend.app.services.authorization import AuthorizationError, AuthorizationService
from backend.app.services.health import HealthService
from backend.app.services.rate_limiter import InMemoryRateLimiter

# Reusable HTTP Bearer scheme with automatic 401 handling
bearer_scheme = HTTPBearer(auto_error=False)

# Shared repository instances
_business_repository_instance: Optional[BaseBusinessRepository] = None
_audit_repository_instance: Optional[BaseAuditLogRepository] = None
_product_repository_instance: Optional[BaseProductRepository] = None
_inventory_repository_instance: Optional[BaseInventoryRepository] = None
_customer_repository_instance: Optional[BaseCustomerRepository] = None
_order_repository_instance: Optional[BaseOrderRepository] = None
_invoice_repository_instance: Optional[BaseInvoiceRepository] = None
_rate_limiter_instance: Optional[InMemoryRateLimiter] = None


def _assert_repository_safety(
    repo_instance: Optional[object],
    repo_name: str,
    settings: Settings,
    in_memory_class: type,
) -> None:
    """Enforce that staging and production strictly forbid in-memory repositories and require Supabase credentials."""
    if not is_in_memory_allowed(settings.ENVIRONMENT):
        env_label = "a production" if settings.ENVIRONMENT == "production" else f"a {settings.ENVIRONMENT}"
        if repo_instance is not None and isinstance(repo_instance, in_memory_class):
            raise RuntimeError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: {in_memory_class.__name__} "
                f"cannot be selected or used in {env_label} environment."
            )
        if repo_instance is None and (not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY):
            env_title = "Production" if settings.ENVIRONMENT == "production" else settings.ENVIRONMENT.capitalize()
            raise RuntimeError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: Production requires database credentials for {repo_name.lower()}. "
                f"{env_title} environment requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to initialize "
                f"database-backed Supabase{repo_name}."
            )


def reset_repository_instances() -> None:
    """Reset all cached repository instances (primarily for test isolation)."""
    global _business_repository_instance, _audit_repository_instance
    global _product_repository_instance, _inventory_repository_instance
    global _customer_repository_instance, _order_repository_instance
    global _invoice_repository_instance
    _business_repository_instance = None
    _audit_repository_instance = None
    _product_repository_instance = None
    _inventory_repository_instance = None
    _customer_repository_instance = None
    _order_repository_instance = None
    _invoice_repository_instance = None


def validate_repository_configuration(settings: Optional[Settings] = None) -> None:
    """Validate repository requirements during application startup.
    
    Ensures staging and production fail fast on startup if database-backed
    repositories cannot be initialized. In-memory repositories are strictly
    forbidden outside of development and test environments.
    """
    if settings is None:
        settings = get_settings()

    if not is_in_memory_allowed(settings.ENVIRONMENT):
        get_business_repository(settings=settings)
        a_repo = get_audit_repository(settings=settings)
        p_repo = get_product_repository(settings=settings)
        get_inventory_repository(settings=settings, product_repo=p_repo, audit_repo=a_repo)
        get_customer_repository(settings=settings)
        get_order_repository(settings=settings, product_repo=p_repo, audit_repo=a_repo)
        get_invoice_repository(settings=settings)


def get_business_repository(
    settings: Settings = Depends(get_settings),
) -> BaseBusinessRepository:
    """Dependency provider for business repository."""
    global _business_repository_instance
    _assert_repository_safety(
        _business_repository_instance,
        "BusinessRepository",
        settings,
        InMemoryBusinessRepository,
    )
    if _business_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _business_repository_instance = SupabaseBusinessRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _business_repository_instance = InMemoryBusinessRepository()
    return _business_repository_instance


def get_audit_repository(
    settings: Settings = Depends(get_settings),
) -> BaseAuditLogRepository:
    """Dependency provider for audit log repository."""
    global _audit_repository_instance
    _assert_repository_safety(
        _audit_repository_instance,
        "AuditLogRepository",
        settings,
        InMemoryAuditLogRepository,
    )
    if _audit_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _audit_repository_instance = SupabaseAuditLogRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _audit_repository_instance = InMemoryAuditLogRepository()
    return _audit_repository_instance


def get_product_repository(
    settings: Settings = Depends(get_settings),
) -> BaseProductRepository:
    """Dependency provider for product repository."""
    global _product_repository_instance
    _assert_repository_safety(
        _product_repository_instance,
        "ProductRepository",
        settings,
        InMemoryProductRepository,
    )
    if _product_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _product_repository_instance = SupabaseProductRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _product_repository_instance = InMemoryProductRepository()
    return _product_repository_instance


def get_inventory_repository(
    settings: Settings = Depends(get_settings),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> BaseInventoryRepository:
    """Dependency provider for inventory repository."""
    global _inventory_repository_instance
    _assert_repository_safety(
        _inventory_repository_instance,
        "InventoryRepository",
        settings,
        InMemoryInventoryRepository,
    )
    if _inventory_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _inventory_repository_instance = SupabaseInventoryRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _inventory_repository_instance = InMemoryInventoryRepository(
                product_repo=product_repo,
                audit_repo=audit_repo,
            )
    return _inventory_repository_instance


def get_customer_repository(
    settings: Settings = Depends(get_settings),
) -> BaseCustomerRepository:
    """Dependency provider for customer repository."""
    global _customer_repository_instance
    _assert_repository_safety(
        _customer_repository_instance,
        "CustomerRepository",
        settings,
        InMemoryCustomerRepository,
    )
    if _customer_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _customer_repository_instance = SupabaseCustomerRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _customer_repository_instance = InMemoryCustomerRepository()
    return _customer_repository_instance


def get_order_repository(
    settings: Settings = Depends(get_settings),
    product_repo: BaseProductRepository = Depends(get_product_repository),
    audit_repo: BaseAuditLogRepository = Depends(get_audit_repository),
) -> BaseOrderRepository:
    """Dependency provider for order repository."""
    global _order_repository_instance
    _assert_repository_safety(
        _order_repository_instance,
        "OrderRepository",
        settings,
        InMemoryOrderRepository,
    )
    if _order_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _order_repository_instance = SupabaseOrderRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _order_repository_instance = InMemoryOrderRepository(
                product_repo=product_repo,
                audit_repo=audit_repo,
            )
    return _order_repository_instance


def get_invoice_repository(
    settings: Settings = Depends(get_settings),
) -> BaseInvoiceRepository:
    """Dependency provider for invoice repository."""
    global _invoice_repository_instance
    _assert_repository_safety(
        _invoice_repository_instance,
        "InvoiceRepository",
        settings,
        InMemoryInvoiceRepository,
    )
    if _invoice_repository_instance is None:
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            _invoice_repository_instance = SupabaseInvoiceRepository(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            )
        else:
            _invoice_repository_instance = InMemoryInvoiceRepository()
    return _invoice_repository_instance


def get_ai_intake_service(settings: Settings = Depends(get_settings)) -> AIIntakeService:
    """Dependency provider for AIIntakeService."""
    return AIIntakeService(settings=settings)


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    """Dependency provider for HealthService."""
    return HealthService(settings=settings)


def get_token_verification_service(
    settings: Settings = Depends(get_settings),
) -> TokenVerificationService:
    """Dependency provider for TokenVerificationService."""
    return TokenVerificationService(settings=settings)


def get_authorization_service(
    repository: BaseBusinessRepository = Depends(get_business_repository),
) -> AuthorizationService:
    """Dependency provider for AuthorizationService."""
    return AuthorizationService(repository=repository)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    token_service: TokenVerificationService = Depends(get_token_verification_service),
) -> AuthenticatedUser:
    """Extract and verify Supabase JWT bearer token from request header."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = token_service.verify_token(credentials.credentials)
        return user
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_business_role(
    required_role: AppRole = "staff",
) -> Callable:
    """Factory creating a FastAPI dependency that verifies membership and role for a business."""
    async def dependency(
        business_id: Optional[str] = Header(None, alias="X-Business-ID"),
        current_user: AuthenticatedUser = Depends(get_current_user),
        auth_service: AuthorizationService = Depends(get_authorization_service),
    ) -> BusinessMembership:
        if not business_id or not business_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Business-ID header is required for business-scoped operations",
            )

        try:
            membership = await auth_service.check_membership(
                user=current_user, business_id=business_id
            )
            auth_service.enforce_role(membership=membership, required_role=required_role)
            return membership
        except AuthorizationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=exc.message,
            ) from exc

    return dependency


def get_rate_limiter() -> InMemoryRateLimiter:
    """Dependency provider for shared InMemoryRateLimiter instance."""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = InMemoryRateLimiter()
    return _rate_limiter_instance


async def check_ai_rate_limit(
    current_user: AuthenticatedUser = Depends(get_current_user),
    membership: BusinessMembership = Depends(require_business_role("staff")),
    limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> BusinessMembership:
    """Enforces rate limiting on authenticated AI intake requests scoped to user and business."""
    # Never trust client-supplied ID; use verified membership from JWT & database
    bucket_key = f"{membership.business_id}:{current_user.user_id}"

    is_allowed, retry_after = limiter.check_rate_limit(
        key=bucket_key,
        max_requests=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "RATE_LIMIT_EXCEEDED",
                "message": (
                    f"Rate limit exceeded: maximum {settings.AI_RATE_LIMIT_REQUESTS} "
                    f"AI intake requests allowed per {settings.AI_RATE_LIMIT_WINDOW_SECONDS} seconds."
                ),
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    return membership

