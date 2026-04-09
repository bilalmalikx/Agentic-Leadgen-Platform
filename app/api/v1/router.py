"""
API v1 Router
Aggregates all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import leads, campaigns, analytics, webhooks, health

# Main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    leads.router,
    prefix="/leads",
    tags=["Leads"]
)

api_router.include_router(
    campaigns.router,
    prefix="/campaigns",
    tags=["Campaigns"]
)

# api_router.include_router(
#     analytics.router,
#     prefix="/analytics",
#     tags=["Analytics"]
# )

# api_router.include_router(
#     webhooks.router,
#     prefix="/webhooks",
#     tags=["Webhooks"]
# )

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)