"""Main application entry point for Orqestra backend."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.deps import get_health_service
from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import register_error_handlers
from backend.app.core.logging import setup_logging
from backend.app.schemas.health import HealthResponse
from backend.app.services.health import HealthService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events for startup and shutdown."""
    settings = get_settings()
    logger = setup_logging(settings.LOG_LEVEL)
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]"
    )
    # Fail startup immediately if repositories cannot initialize in staging or production
    from backend.app.api.deps import validate_repository_configuration
    validate_repository_configuration(settings)
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


def create_application(settings: Settings | None = None) -> FastAPI:
    """Application factory for Orqestra backend."""
    current_settings = settings or get_settings()

    @asynccontextmanager
    async def app_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan events bound to configured settings."""
        logger = setup_logging(current_settings.LOG_LEVEL)
        logger.info(
            f"Starting {current_settings.APP_NAME} v{current_settings.APP_VERSION} [{current_settings.ENVIRONMENT}]"
        )
        # Fail startup immediately if repositories cannot initialize in staging or production
        from backend.app.api.deps import validate_repository_configuration
        validate_repository_configuration(current_settings)
        yield
        logger.info(f"Shutting down {current_settings.APP_NAME}")

    app = FastAPI(
        title=current_settings.APP_NAME,
        version=current_settings.APP_VERSION,
        description=(
            "Orqestra backend foundation API. Coordinates small business operations "
            "with verified business logic and reliable human-in-the-loop workflows."

        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=app_lifespan,
    )

    # Register explicit CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register safe, structured error handlers
    register_error_handlers(app)

    # Root health probe endpoint: GET /health
    @app.get(
        "/health",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
        tags=["Health"],
        summary="Root Health Probe",
        description="Root health check for load balancers and system monitoring.",
    )
    async def root_health(
        health_service: HealthService = Depends(get_health_service),
    ) -> HealthResponse:
        return await health_service.get_health_status()

    # Mount API v1 router: /api/v1/...
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_application()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
