"""Shapes of the JSON returned by the API (what the iPhone app will consume)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sport: str
    garmin_activity_type: str
    name: str
    start_time: datetime
    duration_seconds: float
    distance_meters: float | None
    avg_heart_rate: int | None
    max_heart_rate: int | None
    calories: int | None


class TrainingLoadDay(BaseModel):
    date: date
    minutes: float
    acute_minutes: float
    chronic_weekly_avg_minutes: float
    ratio: float | None
    zone: str


class TrainingLoadOut(BaseModel):
    current_ratio: float | None
    current_zone: str
    days_since_last_session: dict[str, int | None]
    days: list[TrainingLoadDay]


class SportTotals(BaseModel):
    sessions: int
    minutes: float
    distance_km: float


class WeekSummary(BaseModel):
    week_start: date
    sports: dict[str, SportTotals]


class RecordOut(BaseModel):
    sport: str
    record_type: str
    label: str
    value: float
    unit: str
    display_value: str
    achieved_on: date
    activity_id: int | None
    period_start: date | None


class StreakOut(BaseModel):
    current_days: int
    current_start: date | None
    longest_days: int
    longest_start: date | None
    longest_end: date | None


class AchievementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    description: str
    earned_on: date


class SyncOut(BaseModel):
    new_activities: int
    new_achievements: list[AchievementOut]
