from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SyncOut
from app.services.sync import ActivitySource, get_client, run_sync

router = APIRouter(tags=["sync"])


def activity_source() -> ActivitySource:
    try:
        return get_client()
    except RuntimeError as error:  # Garmin settings missing from .env
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/sync", response_model=SyncOut)
def sync(db: Session = Depends(get_db), client: ActivitySource = Depends(activity_source)):
    """Pull new workouts from Garmin. The app calls this on pull-to-refresh and
    shows any `new_achievements` as a celebration banner."""
    result = run_sync(db, client)
    return {"new_activities": result.new_activities, "new_achievements": result.new_achievements}
