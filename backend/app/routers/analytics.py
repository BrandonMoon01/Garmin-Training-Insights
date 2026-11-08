from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity
from app.schemas import TrainingLoadOut, WeekSummary
from app.services import analytics

router = APIRouter(tags=["analytics"])


@router.get("/training-load", response_model=TrainingLoadOut)
def training_load(days: int = Query(42, ge=1, le=365), db: Session = Depends(get_db)):
    """Daily training load and acute:chronic ratio for the last `days` days."""
    activities = db.query(Activity).all()
    today = date.today()
    series = analytics.training_load_series(activities, today, days)
    return {
        "current_ratio": series[-1]["ratio"],
        "current_zone": series[-1]["zone"],
        "days_since_last_session": analytics.days_since_last_session(activities, today),
        "days": series,
    }


@router.get("/summary/weekly", response_model=list[WeekSummary])
def weekly_summary(weeks: int = Query(8, ge=1, le=104), db: Session = Depends(get_db)):
    """Per-sport sessions / minutes / distance for recent weeks, newest first."""
    return analytics.weekly_summary(db.query(Activity).all(), date.today(), weeks)
