"""Central router aggregating all API v1 endpoints."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    ai_intake,
    auth,
    customers,
    health,
    inventory,
    invoices,
    orders,
    products,
)

api_v1_router = APIRouter()

# Include versioned health route: /api/v1/health
api_v1_router.include_router(health.router, tags=["Health"])

# Include versioned auth routes: /api/v1/auth/...
api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth & Access"])

# Include Phase 3 Operations routes
api_v1_router.include_router(products.router, prefix="/products", tags=["Products"])
api_v1_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory & Stock"])
api_v1_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_v1_router.include_router(orders.router, prefix="/orders", tags=["Orders & Transactions"])

# Include Phase 5 AI Intake & Invoices routes
api_v1_router.include_router(ai_intake.router, prefix="/orders", tags=["Orders & Transactions"])
api_v1_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices & Billing"])

