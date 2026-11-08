from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Activity


@pytest.fixture
def db():
    """A fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


_next_id = 0


def make_activity(
    start: str, sport: str = "running", minutes: float = 30, km: float | None = 5, garmin_type: str | None = None
) -> Activity:
    """Build an unsaved Activity, e.g. make_activity("2026-11-01 07:00", km=10)."""
    global _next_id
    _next_id += 1
    return Activity(
        garmin_activity_id=f"test-{_next_id}",
        sport=sport,
        garmin_activity_type=garmin_type or sport,
        start_time=datetime.fromisoformat(start),
        duration_seconds=minutes * 60,
        distance_meters=km * 1000 if km is not None else None,
    )
