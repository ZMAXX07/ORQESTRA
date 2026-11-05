"""Pydantic schemas for health and system status endpoints."""

from typing import Dict, Literal
from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    """Status details for an individual system component."""

    status: Literal[
        "operational",
        "degraded",
        "not_connected",
        "connected",
        "not_configured",
        "unavailable",
        "error",
    ] = Field(
        description="Operational state of the component"
    )
    details: str = Field(description="Honest description of verified status or deferred state")


class HealthResponse(BaseModel):
    """Schema for health probe response reporting verified system state."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        default="healthy", description="Overall application status"
    )
    app_name: str = Field(description="Name of the application service")
    version: str = Field(description="Current version of the application")
    environment: str = Field(description="Runtime environment (development, staging, production)")
    timestamp: str = Field(description="ISO 8601 UTC timestamp of the health check")
    uptime_seconds: float = Field(description="Application uptime in seconds")
    components: Dict[str, ComponentStatus] = Field(
        description="Individual status of verified runtime components and deferred services"
    )
