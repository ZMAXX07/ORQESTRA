"""Health check endpoint for API v1."""

from fastapi import APIRouter, Depends, status
from backend.app.api.deps import get_health_service
from backend.app.schemas.health import HealthResponse
from backend.app.services.health import HealthService

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="API v1 Health Probe",
    description="Returns verified runtime status of the API and accurately reports deferred services.",
)
async def get_health(
    health_service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    """Execute health probe and return structured system status."""
    return await health_service.get_health_status()
