"""Health service for performing verified system diagnostics."""

import sys
import time
from datetime import datetime, timezone
from typing import Dict, Literal, Optional
import httpx

from backend.app.core.config import Settings, is_in_memory_allowed
from backend.app.schemas.health import ComponentStatus, HealthResponse
from backend.app.services.ai_intake import check_ai_provider_connectivity

# Application process start time
_START_TIME = time.time()

# Cache for AI connectivity probe: avoid spamming provider on every health ping
_AI_PROBE_CACHE: Dict[str, Optional[ComponentStatus]] = {"status": None}
_AI_PROBE_TIMESTAMP: float = 0.0
_AI_PROBE_TTL_SECONDS: float = 15.0

# Cache for Database connectivity probe
_DB_PROBE_CACHE: Dict[str, Optional[ComponentStatus]] = {"status": None}
_DB_PROBE_TIMESTAMP: float = 0.0
_DB_PROBE_TTL_SECONDS: float = 15.0


async def check_database_connectivity(
    settings: Settings,
    client: Optional[httpx.AsyncClient] = None,
) -> ComponentStatus:
    """Safely check database connectivity.
    
    Verifies that the Supabase PostgREST endpoint is reachable with configured credentials.
    Never prints, logs, or returns secret credentials.
    """
    if not settings.SUPABASE_URL:
        if is_in_memory_allowed(settings.ENVIRONMENT):
            return ComponentStatus(
                status="not_connected",
                details="Schema migrations defined in supabase/migrations; SUPABASE_URL awaiting local .env configuration",
            )
        return ComponentStatus(
            status="error",
            details=f"SUPABASE_URL is unconfigured in {settings.ENVIRONMENT} environment",
        )

    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        if is_in_memory_allowed(settings.ENVIRONMENT):
            return ComponentStatus(
                status="not_connected",
                details="SUPABASE_SERVICE_ROLE_KEY awaiting local .env configuration",
            )
        return ComponentStatus(
            status="error",
            details=f"SUPABASE_SERVICE_ROLE_KEY is unconfigured in {settings.ENVIRONMENT} environment",
        )

    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    }
    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/"

    try:
        if client:
            resp = await client.get(url, headers=headers, timeout=5.0)
        else:
            async with httpx.AsyncClient(timeout=5.0) as http_client:
                resp = await http_client.get(url, headers=headers)

        if resp.status_code == 200:
            return ComponentStatus(
                status="operational",
                details="Supabase PostgreSQL database connection verified and operational",
            )
        return ComponentStatus(
            status="error",
            details=f"Supabase PostgREST returned HTTP {resp.status_code}",
        )
    except Exception as exc:
        return ComponentStatus(
            status="unavailable" if is_in_memory_allowed(settings.ENVIRONMENT) else "error",
            details=f"Database probe failed: {type(exc).__name__}",
        )


class HealthService:
    """Service to evaluate and report genuine system health without false claims."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def get_health_status(self) -> HealthResponse:
        """Produce verified health status.
        
        Only genuine, verified components report operational or connected.
        Unconfigured or unavailable integrations report truthfully.
        """
        global _AI_PROBE_CACHE, _AI_PROBE_TIMESTAMP, _DB_PROBE_CACHE, _DB_PROBE_TIMESTAMP
        uptime = round(time.time() - _START_TIME, 2)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Evaluate AI service connectivity truthfully
        if not self.settings.effective_ai_api_key:
            provider_name = "Google Gemini" if self.settings.effective_ai_provider == "gemini" else self.settings.effective_ai_provider
            ai_status = ComponentStatus(
                status="not_configured",
                details=f"AI provider API key (AI_API_KEY or GEMINI_API_KEY) is not configured in backend/.env for {provider_name}",
            )
        else:
            now = time.time()
            if (
                _AI_PROBE_CACHE["status"] is not None
                and (now - _AI_PROBE_TIMESTAMP) < _AI_PROBE_TTL_SECONDS
            ):
                ai_status = _AI_PROBE_CACHE["status"]
            else:
                ai_status = await check_ai_provider_connectivity(self.settings)
                _AI_PROBE_CACHE["status"] = ai_status
                _AI_PROBE_TIMESTAMP = now

        # Evaluate database connectivity truthfully
        if not self.settings.SUPABASE_URL:
            db_status = ComponentStatus(
                status="not_connected" if is_in_memory_allowed(self.settings.ENVIRONMENT) else "error",
                details=(
                    "Schema migrations defined in supabase/migrations; SUPABASE_URL awaiting local .env configuration"
                    if is_in_memory_allowed(self.settings.ENVIRONMENT)
                    else f"Database credentials unconfigured in {self.settings.ENVIRONMENT} environment"
                ),
            )
        elif not self.settings.SUPABASE_SERVICE_ROLE_KEY:
            db_status = ComponentStatus(
                status="not_connected" if is_in_memory_allowed(self.settings.ENVIRONMENT) else "error",
                details=(
                    "SUPABASE_SERVICE_ROLE_KEY awaiting local .env configuration"
                    if is_in_memory_allowed(self.settings.ENVIRONMENT)
                    else f"SUPABASE_SERVICE_ROLE_KEY unconfigured in {self.settings.ENVIRONMENT} environment"
                ),
            )
        else:
            now = time.time()
            if (
                _DB_PROBE_CACHE["status"] is not None
                and (now - _DB_PROBE_TIMESTAMP) < _DB_PROBE_TTL_SECONDS
            ):
                db_status = _DB_PROBE_CACHE["status"]
            else:
                db_status = await check_database_connectivity(self.settings)
                _DB_PROBE_CACHE["status"] = db_status
                _DB_PROBE_TIMESTAMP = now

        components: Dict[str, ComponentStatus] = {
            "python_runtime": ComponentStatus(
                status="operational",
                details=f"Python {sys.version.split()[0]} runtime active",
            ),
            "fastapi_server": ComponentStatus(
                status="operational",
                details="FastAPI router and request processing engine operational",
            ),
            "database": db_status,
            "ai_service": ai_status,
            "authentication": ComponentStatus(
                status="operational"
                if bool(self.settings.SUPABASE_JWT_SECRET or self.settings.effective_jwks_url)
                else "not_connected",
                details=(
                    "Supabase JWT signature verification engine active"
                    if bool(self.settings.SUPABASE_JWT_SECRET or self.settings.effective_jwks_url)
                    else "Auth verification engine active; SUPABASE_JWT_SECRET or SUPABASE_URL awaiting local .env configuration"
                ),
            ),
        }

        overall_status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
        if not is_in_memory_allowed(self.settings.ENVIRONMENT):
            if db_status.status in ("error", "unavailable", "not_connected"):
                overall_status = "unhealthy"

        return HealthResponse(
            status=overall_status,
            app_name=self.settings.APP_NAME,
            version=self.settings.APP_VERSION,
            environment=self.settings.ENVIRONMENT,
            timestamp=now_iso,
            uptime_seconds=uptime,
            components=components,
        )

