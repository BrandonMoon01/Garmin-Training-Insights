from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity
from app.schemas import ActivityOut

router = APIRouter(tags=["activities"])


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    sport: str | None = None,
    start: date | None = None,
    end: date | None = Query(None, description="Inclusive"),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    """Workouts, newest first, optionally filtered by sport and date range."""
    query = db.query(Activity)
    if sport:
        query = query.filter(Activity.sport == sport)
    if start:
        query = query.filter(Activity.start_time >= datetime.combine(start, time.min))
    if end:
        query = query.filter(Activity.start_time < datetime.combine(end + timedelta(days=1), time.min))
    return query.order_by(Activity.start_time.desc()).limit(limit).all()
