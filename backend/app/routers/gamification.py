from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Achievement, PersonalRecord
from app.schemas import AchievementOut, RecordOut, StreakOut
from app.services.gamification import RECORD_TYPES, format_record_value, streak_dates, summarize_streaks

router = APIRouter(tags=["gamification"])


@router.get("/records", response_model=list[RecordOut])
def list_records(db: Session = Depends(get_db)):
    """Current personal records for every sport."""
    records = db.query(PersonalRecord).order_by(PersonalRecord.sport, PersonalRecord.record_type).all()
    return [
        {
            "sport": record.sport,
            "record_type": record.record_type,
            "label": RECORD_TYPES[record.record_type].label,
            "value": record.value,
            "unit": record.unit,
            "display_value": format_record_value(record.sport, record.record_type, record.value),
            "achieved_on": record.achieved_on,
            "activity_id": record.activity_id,
            "period_start": record.period_start,
        }
        for record in records
    ]


@router.get("/streaks", response_model=StreakOut)
def get_streaks(db: Session = Depends(get_db)):
    """Current and longest-ever training streak."""
    return summarize_streaks(streak_dates(db), date.today())


@router.get("/achievements", response_model=list[AchievementOut])
def list_achievements(db: Session = Depends(get_db)):
    """Every badge earned, newest first."""
    return db.query(Achievement).order_by(Achievement.earned_on.desc(), Achievement.id.desc()).all()
