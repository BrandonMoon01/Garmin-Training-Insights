"""Database tables.

Only three tables are stored. Everything else (training load, weekly
summaries, streaks) is calculated from `activities` when requested, so it can
never get out of sync with the raw data.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base

SPORTS = ("running", "cycling", "swimming", "strength", "other")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Activity(Base):
    """One workout pulled from Garmin."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    garmin_activity_id = Column(String(64), unique=True, nullable=False, index=True)
    sport = Column(String(20), nullable=False, index=True)  # one of SPORTS
    garmin_activity_type = Column(String(64), nullable=False)  # e.g. "trail_running"
    name = Column(String(200), default="")
    start_time = Column(DateTime, nullable=False, index=True)  # athlete's local time
    duration_seconds = Column(Float, nullable=False)
    distance_meters = Column(Float, nullable=True)  # None for strength sessions
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)


class PersonalRecord(Base):
    """The current best for one sport + record type (e.g. running / longest_distance).

    There is one row per pair, overwritten when the record is beaten. The
    history of beaten records lives in the `achievements` table.
    """

    __tablename__ = "personal_records"
    __table_args__ = (UniqueConstraint("sport", "record_type"),)

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), nullable=False)
    record_type = Column(String(30), nullable=False)  # key of gamification.RECORD_TYPES
    value = Column(Float, nullable=False)
    unit = Column(String(10), nullable=False)
    achieved_on = Column(Date, nullable=False)
    # Set for single-workout records (distance, duration, pace).
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    # Set for volume records (biggest week / month): first day of that period.
    period_start = Column(Date, nullable=True)

    activity = relationship("Activity")


class Achievement(Base):
    """An unlocked badge (append-only log shown on the app's achievements screen)."""

    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    # Unique key such as "streak:7" or "pr:running:longest_distance:<activity id>"
    # so re-running a sync can never award the same badge twice.
    badge_key = Column(String(120), unique=True, nullable=False)
    category = Column(String(20), nullable=False)  # "streak" or "pr"
    title = Column(String(120), nullable=False)
    description = Column(String(300), default="")
    earned_on = Column(Date, nullable=False)
    created_at = Column(DateTime, default=utcnow)
