from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import activities_router, analytics_router, gamification_router, sync_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Garmin Training Insights API",
    description="Training analytics, streaks and PRs from Garmin data.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(activities_router)
app.include_router(analytics_router)
app.include_router(gamification_router)
app.include_router(sync_router)


@app.get("/health")
def health():
    return {"status": "ok"}
