from fastapi import APIRouter

from app.api.routes.contracts import router as contracts_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(contracts_router, tags=["contracts"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
