"""Sync: pull new workouts from Garmin into the database.

Steps:
  1. Work out the time window to fetch (everything new since the last sync).
  2. Fetch raw activities and convert them with `normalize_activity`.
  3. Save the ones we don't already have.
  4. Update PRs, streaks and badges.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Achievement, Activity
from app.services import gamification
from app.services.garmin_client import GarminClient, normalize_activity
from app.services.sample_data import SampleGarminClient

# Re-fetch a little overlap in case a workout was uploaded to Garmin late.
# Duplicates are skipped, so the overlap is harmless.
SYNC_OVERLAP = timedelta(days=2)


class ActivitySource(Protocol):
    def fetch_activities(self, start: date, end: date) -> list[dict]: ...


@dataclass
class SyncResult:
    new_activities: int
    new_achievements: list[Achievement]


def get_client(use_sample_data: bool | None = None) -> ActivitySource:
    if use_sample_data is None:
        use_sample_data = settings.use_sample_data
    return SampleGarminClient() if use_sample_data else GarminClient(settings.garmin_api_key)


def run_sync(db: Session, client: ActivitySource, today: date | None = None) -> SyncResult:
    today = today or date.today()
    latest_start = db.query(func.max(Activity.start_time)).scalar()
    is_first_sync = latest_start is None
    if is_first_sync:
        fetch_from = today - timedelta(days=settings.initial_sync_days)
    else:
        fetch_from = latest_start.date() - SYNC_OVERLAP

    existing_ids = {garmin_id for (garmin_id,) in db.query(Activity.garmin_activity_id)}
    new_activities = []
    for raw in client.fetch_activities(fetch_from, today):
        fields = normalize_activity(raw)
        if fields["garmin_activity_id"] in existing_ids:
            continue
        activity = Activity(**fields)
        db.add(activity)
        new_activities.append(activity)
        existing_ids.add(fields["garmin_activity_id"])
    db.flush()  # gives the new activities their database ids

    achievements = gamification.process_new_activities(db, new_activities, award_pr_badges=not is_first_sync)
    db.commit()
    return SyncResult(new_activities=len(new_activities), new_achievements=achievements)
