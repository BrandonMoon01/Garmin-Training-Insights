from app.routers.activities import router as activities_router
from app.routers.analytics import router as analytics_router
from app.routers.gamification import router as gamification_router
from app.routers.sync import router as sync_router

__all__ = ["activities_router", "analytics_router", "gamification_router", "sync_router"]
