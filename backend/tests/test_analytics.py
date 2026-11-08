from datetime import date, timedelta

from app.services.analytics import (
    days_since_last_session,
    load_zone,
    month_bounds,
    training_load_series,
    week_bounds,
    weekly_summary,
)
from tests.conftest import make_activity

TODAY = date(2026, 11, 6)  # a Friday


def test_week_and_month_bounds():
    assert week_bounds(TODAY) == (date(2026, 11, 2), date(2026, 11, 9))
    assert month_bounds(date(2026, 12, 15)) == (date(2026, 12, 1), date(2027, 1, 1))


def test_steady_training_gives_ratio_of_one():
    # 30 minutes every day for 6 weeks: this week looks exactly like the average.
    activities = [make_activity(f"{TODAY - timedelta(days=i)} 07:00", minutes=30) for i in range(42)]
    today = training_load_series(activities, TODAY)[-1]
    assert today["acute_minutes"] == 210
    assert today["ratio"] == 1.0
    assert today["zone"] == "optimal"


def test_sudden_spike_is_high_risk():
    # Nothing for three weeks, then a big week: acute load far above chronic.
    activities = [make_activity(f"{TODAY - timedelta(days=i)} 07:00", minutes=90) for i in range(7)]
    assert training_load_series(activities, TODAY)[-1]["zone"] == "high_risk"


def test_load_zone_without_history():
    assert load_zone(None) == "not_enough_data"


def test_weekly_summary_groups_by_week_and_sport():
    activities = [
        make_activity("2026-11-03 07:00", sport="running", minutes=40, km=8),
        make_activity("2026-11-05 07:00", sport="running", minutes=30, km=6),
        make_activity("2026-11-04 18:00", sport="strength", minutes=60, km=None),
        make_activity("2026-10-28 07:00", sport="swimming", minutes=45, km=2),
    ]
    this_week, last_week = weekly_summary(activities, TODAY, weeks=2)
    assert this_week["week_start"] == date(2026, 11, 2)
    assert this_week["sports"]["running"] == {"sessions": 2, "minutes": 70.0, "distance_km": 14.0}
    assert this_week["sports"]["strength"]["sessions"] == 1
    assert last_week["sports"]["swimming"]["distance_km"] == 2.0


def test_days_since_last_session():
    activities = [make_activity("2026-11-04 07:00", sport="cycling")]
    result = days_since_last_session(activities, TODAY)
    assert result["cycling"] == 2
    assert result["swimming"] is None
