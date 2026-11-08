"""Training analytics calculated from a list of activities.

These are plain functions (activities in, numbers out) with no database or
HTTP code, which keeps them easy to read and to unit test.

Training load here is measured in *minutes of training*. Garmin has fancier
load metrics, but minutes work the same for every sport, including lifting,
where there's no distance or pace.
"""

from collections import defaultdict
from datetime import date, timedelta

from app.models import SPORTS, Activity

ACUTE_DAYS = 7  # "how hard have I trained this week?"
CHRONIC_DAYS = 28  # "what am I used to?"


def week_bounds(day: date) -> tuple[date, date]:
    """(Monday of `day`'s week, the following Monday)."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=7)


def month_bounds(day: date) -> tuple[date, date]:
    """(1st of `day`'s month, 1st of the next month)."""
    first = day.replace(day=1)
    next_first = (first + timedelta(days=32)).replace(day=1)
    return first, next_first


def daily_minutes(activities: list[Activity]) -> dict[date, float]:
    minutes = defaultdict(float)
    for activity in activities:
        minutes[activity.start_time.date()] += activity.duration_seconds / 60
    return minutes


def load_zone(ratio: float | None) -> str:
    """Label an acute:chronic workload ratio (ACWR).

    The ACWR compares the last 7 days of training with the weekly average of
    the last 28. Sports-science research (e.g. Gabbett, 2016) links ratios of
    roughly 0.8-1.3 with the lowest injury risk, and spikes above ~1.5 with
    the highest.
    """
    if ratio is None:
        return "not_enough_data"
    if ratio < 0.8:
        return "undertraining"
    if ratio <= 1.3:
        return "optimal"
    if ratio <= 1.5:
        return "caution"
    return "high_risk"


def training_load_series(activities: list[Activity], today: date, days: int = 42) -> list[dict]:
    """One entry per day for the last `days` days, oldest first."""
    minutes_by_day = daily_minutes(activities)

    def total_minutes(last_day: date, window: int) -> float:
        return sum(minutes_by_day.get(last_day - timedelta(days=i), 0.0) for i in range(window))

    series = []
    for days_ago in range(days - 1, -1, -1):
        day = today - timedelta(days=days_ago)
        acute = total_minutes(day, ACUTE_DAYS)
        chronic_weekly_avg = total_minutes(day, CHRONIC_DAYS) / (CHRONIC_DAYS / ACUTE_DAYS)
        ratio = round(acute / chronic_weekly_avg, 2) if chronic_weekly_avg else None
        series.append({
            "date": day,
            "minutes": round(minutes_by_day.get(day, 0.0), 1),
            "acute_minutes": round(acute, 1),
            "chronic_weekly_avg_minutes": round(chronic_weekly_avg, 1),
            "ratio": ratio,
            "zone": load_zone(ratio),
        })
    return series


def weekly_summary(activities: list[Activity], today: date, weeks: int = 8) -> list[dict]:
    """Per-sport totals for each of the last `weeks` weeks, most recent first."""
    summaries = []
    this_monday, _ = week_bounds(today)
    for weeks_ago in range(weeks):
        start = this_monday - timedelta(weeks=weeks_ago)
        end = start + timedelta(days=7)
        totals = {sport: {"sessions": 0, "minutes": 0.0, "distance_km": 0.0} for sport in SPORTS}
        for activity in activities:
            if start <= activity.start_time.date() < end:
                sport_totals = totals[activity.sport]
                sport_totals["sessions"] += 1
                sport_totals["minutes"] += activity.duration_seconds / 60
                sport_totals["distance_km"] += (activity.distance_meters or 0) / 1000
        for sport_totals in totals.values():
            sport_totals["minutes"] = round(sport_totals["minutes"], 1)
            sport_totals["distance_km"] = round(sport_totals["distance_km"], 2)
        summaries.append({"week_start": start, "sports": totals})
    return summaries


def days_since_last_session(activities: list[Activity], today: date) -> dict[str, int | None]:
    """How many days ago each sport was last trained (None = never)."""
    last_seen: dict[str, date] = {}
    for activity in activities:
        day = activity.start_time.date()
        if activity.sport not in last_seen or day > last_seen[activity.sport]:
            last_seen[activity.sport] = day
    return {sport: (today - last_seen[sport]).days if sport in last_seen else None for sport in SPORTS}
