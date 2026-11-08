"""Streaks, personal records (PRs) and achievement badges.

The rules:
  * Streak - consecutive days with at least one run, ride, swim or lifting
    session (walks, yoga, etc. don't count).
    Badges unlock once at 3, 7, 14, 30, 60, 100 and 365 days.
  * PRs - for running, cycling and swimming only (lifting isn't logged with
    sets/weights, so there's nothing to compare):
      - per workout: longest distance, longest duration, fastest pace
      - per period: biggest week and biggest month by distance
    Every new PR earns a badge.

`process_new_activities` runs at the end of every sync, so records and
badges are always up to date with the activities table.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Achievement, Activity, PersonalRecord
from app.services.analytics import month_bounds, week_bounds

ENDURANCE_SPORTS = ("running", "cycling", "swimming")

STREAK_SPORTS = ("running", "cycling", "swimming", "strength")
STREAK_MILESTONES = (3, 7, 14, 30, 60, 100, 365)

# A 300 m jog to the mailbox shouldn't become your "fastest run", so pace
# PRs only count workouts of at least this distance.
MIN_DISTANCE_FOR_PACE_M = {"running": 1000, "cycling": 5000, "swimming": 200}


@dataclass(frozen=True)
class RecordType:
    label: str
    unit: str
    higher_is_better: bool


RECORD_TYPES = {
    "longest_distance": RecordType("Longest Distance", "m", True),
    "longest_duration": RecordType("Longest Duration", "s", True),
    "fastest_pace": RecordType("Fastest Pace", "s/km", False),
    "biggest_week": RecordType("Biggest Week", "m", True),
    "biggest_month": RecordType("Biggest Month", "m", True),
}

PERIOD_RECORDS = {"biggest_week": week_bounds, "biggest_month": month_bounds}


# ---------------------------------------------------------------- streaks


def streak_dates(db: Session) -> list[date]:
    """Days with at least one workout in a sport that counts toward the streak."""
    rows = db.query(Activity.start_time).filter(Activity.sport.in_(STREAK_SPORTS))
    return [start.date() for (start,) in rows]


@dataclass
class StreakSummary:
    current_days: int
    current_start: date | None
    longest_days: int
    longest_start: date | None
    longest_end: date | None


def find_streak_runs(activity_dates: list[date]) -> list[tuple[date, date]]:
    """Group dates into runs of consecutive days: [(first_day, last_day), ...]."""
    runs: list[tuple[date, date]] = []
    for day in sorted(set(activity_dates)):
        if runs and day == runs[-1][1] + timedelta(days=1):
            runs[-1] = (runs[-1][0], day)
        else:
            runs.append((day, day))
    return runs


def run_length(run: tuple[date, date]) -> int:
    return (run[1] - run[0]).days + 1


def summarize_streaks(activity_dates: list[date], today: date) -> StreakSummary:
    runs = find_streak_runs(activity_dates)
    if not runs:
        return StreakSummary(0, None, 0, None, None)

    longest = max(runs, key=run_length)
    latest = runs[-1]
    # The streak is still alive if you trained yesterday; it isn't "broken"
    # just because you haven't worked out yet today.
    is_alive = latest[1] >= today - timedelta(days=1)
    return StreakSummary(
        current_days=run_length(latest) if is_alive else 0,
        current_start=latest[0] if is_alive else None,
        longest_days=run_length(longest),
        longest_start=longest[0],
        longest_end=longest[1],
    )


def streak_milestone_dates(activity_dates: list[date]) -> dict[int, date]:
    """The first date each milestone was reached, e.g. {3: date(...), 7: date(...)}."""
    reached: dict[int, date] = {}
    for run in find_streak_runs(activity_dates):
        for milestone in STREAK_MILESTONES:
            if milestone not in reached and run_length(run) >= milestone:
                reached[milestone] = run[0] + timedelta(days=milestone - 1)
    return reached


# ---------------------------------------------------------------- records


def is_improvement(record_type: str, new_value: float, current_value: float | None) -> bool:
    if current_value is None:
        return True
    if RECORD_TYPES[record_type].higher_is_better:
        return new_value > current_value
    return new_value < current_value


def activity_record_values(activity: Activity) -> dict[str, float]:
    """The single-workout record values this activity could set."""
    if activity.sport not in ENDURANCE_SPORTS or not activity.distance_meters:
        return {}
    values = {
        "longest_distance": activity.distance_meters,
        "longest_duration": activity.duration_seconds,
    }
    if activity.distance_meters >= MIN_DISTANCE_FOR_PACE_M[activity.sport]:
        values["fastest_pace"] = activity.duration_seconds / (activity.distance_meters / 1000)
    return values


def format_record_value(sport: str, record_type: str, value: float) -> str:
    """Human-friendly record value, e.g. '21.10 km', '1:45:03', '5:12 /km'."""
    unit = RECORD_TYPES[record_type].unit
    if unit == "s":
        hours, remainder = divmod(round(value), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    if unit == "s/km":
        if sport == "cycling":
            return f"{3600 / value:.1f} km/h"
        per_unit, label = (value / 10, "/100m") if sport == "swimming" else (value, "/km")
        minutes, seconds = divmod(round(per_unit), 60)
        return f"{minutes}:{seconds:02d} {label}"
    if sport == "swimming":
        return f"{value:,.0f} m"
    return f"{value / 1000:.2f} km"


# ---------------------------------------------------------------- database updates


def process_new_activities(db: Session, new_activities: list[Activity], award_pr_badges: bool) -> list[Achievement]:
    """Update PRs and streak badges after a sync. Returns newly earned badges.

    `award_pr_badges` is False on the very first sync: importing a year of
    history would otherwise produce hundreds of "new PR" badges at once, so
    the first sync just sets the baseline records quietly.
    """
    earned = []
    earned += _update_workout_records(db, new_activities, award_pr_badges)
    earned += _update_period_records(db, new_activities, award_pr_badges)
    earned += _award_streak_badges(db)
    return earned


def _get_record(db: Session, sport: str, record_type: str) -> PersonalRecord | None:
    return db.query(PersonalRecord).filter_by(sport=sport, record_type=record_type).one_or_none()


def _set_record(db: Session, sport: str, record_type: str, value: float, achieved_on: date) -> PersonalRecord:
    record = _get_record(db, sport, record_type)
    if record is None:
        record = PersonalRecord(sport=sport, record_type=record_type, unit=RECORD_TYPES[record_type].unit)
        db.add(record)
    record.value = value
    record.achieved_on = achieved_on
    return record


def _award(db: Session, badge_key: str, category: str, title: str, description: str, earned_on: date) -> Achievement | None:
    if db.query(Achievement).filter_by(badge_key=badge_key).first():
        return None
    achievement = Achievement(badge_key=badge_key, category=category, title=title, description=description, earned_on=earned_on)
    db.add(achievement)
    return achievement


def _award_pr(db: Session, badge_key: str, sport: str, record_type: str, value: float, earned_on: date) -> Achievement | None:
    return _award(
        db,
        badge_key=badge_key,
        category="pr",
        title=f"New {sport.title()} PR: {RECORD_TYPES[record_type].label}",
        description=format_record_value(sport, record_type, value),
        earned_on=earned_on,
    )


def _update_workout_records(db: Session, new_activities: list[Activity], award_badges: bool) -> list[Achievement]:
    earned = []
    for activity in sorted(new_activities, key=lambda a: a.start_time):
        for record_type, value in activity_record_values(activity).items():
            current = _get_record(db, activity.sport, record_type)
            if not is_improvement(record_type, value, current.value if current else None):
                continue
            record = _set_record(db, activity.sport, record_type, value, activity.start_time.date())
            record.activity_id = activity.id
            if award_badges:
                badge_key = f"pr:{activity.sport}:{record_type}:{activity.garmin_activity_id}"
                earned.append(_award_pr(db, badge_key, activity.sport, record_type, value, record.achieved_on))
    return [badge for badge in earned if badge]


def _update_period_records(db: Session, new_activities: list[Activity], award_badges: bool) -> list[Achievement]:
    """Biggest week / biggest month, measured by total distance."""
    earned = []
    for sport in ENDURANCE_SPORTS:
        sport_activity_days = [a.start_time.date() for a in new_activities if a.sport == sport]
        for record_type, bounds_of in PERIOD_RECORDS.items():
            for start, end in sorted({bounds_of(day) for day in sport_activity_days}):
                total = _total_distance(db, sport, start, end)
                current = _get_record(db, sport, record_type)
                if not is_improvement(record_type, total, current.value if current else None):
                    continue
                # If the record already belongs to this same week/month (and it
                # just grew), update it without awarding a second badge.
                already_held = current is not None and current.period_start == start
                last_day = max(day for day in sport_activity_days if start <= day < end)
                record = _set_record(db, sport, record_type, total, last_day)
                record.period_start = start
                if award_badges and not already_held:
                    badge_key = f"pr:{sport}:{record_type}:{start.isoformat()}"
                    earned.append(_award_pr(db, badge_key, sport, record_type, total, last_day))
    return [badge for badge in earned if badge]


def _total_distance(db: Session, sport: str, start: date, end: date) -> float:
    start_dt, end_dt = datetime.combine(start, time.min), datetime.combine(end, time.min)
    total = (
        db.query(func.sum(Activity.distance_meters))
        .filter(Activity.sport == sport, Activity.start_time >= start_dt, Activity.start_time < end_dt)
        .scalar()
    )
    return total or 0.0


def _award_streak_badges(db: Session) -> list[Achievement]:
    earned = []
    for milestone, reached_on in streak_milestone_dates(streak_dates(db)).items():
        badge = _award(
            db,
            badge_key=f"streak:{milestone}",
            category="streak",
            title=f"{milestone}-Day Streak",
            description=f"Trained {milestone} days in a row",
            earned_on=reached_on,
        )
        if badge:
            earned.append(badge)
    return earned
