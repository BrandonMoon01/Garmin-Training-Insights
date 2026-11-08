from datetime import date

from app.models import Achievement, PersonalRecord
from app.services.gamification import (
    activity_record_values,
    format_record_value,
    is_improvement,
    process_new_activities,
    streak_milestone_dates,
    summarize_streaks,
)
from tests.conftest import make_activity


def days(*day_numbers: int) -> list[date]:
    return [date(2026, 11, n) for n in day_numbers]


# ---------------------------------------------------------------- streaks


def test_streak_alive_when_trained_yesterday():
    summary = summarize_streaks(days(1, 2, 3, 4, 5), today=date(2026, 11, 6))
    assert summary.current_days == 5
    assert summary.current_start == date(2026, 11, 1)


def test_streak_broken_after_a_missed_day():
    summary = summarize_streaks(days(1, 2, 3), today=date(2026, 11, 5))
    assert summary.current_days == 0
    assert summary.longest_days == 3


def test_longest_streak_and_multiple_workouts_per_day():
    activity_days = days(1, 2, 3, 4, 6, 7) + days(7)  # two workouts on the 7th
    summary = summarize_streaks(activity_days, today=date(2026, 11, 7))
    assert summary.current_days == 2
    assert (summary.longest_days, summary.longest_start, summary.longest_end) == (4, date(2026, 11, 1), date(2026, 11, 4))


def test_streak_milestone_dates():
    assert streak_milestone_dates(days(1, 2, 3, 4, 5, 6, 7, 8)) == {3: date(2026, 11, 3), 7: date(2026, 11, 7)}


# ---------------------------------------------------------------- record rules


def test_lower_pace_is_an_improvement():
    assert is_improvement("fastest_pace", 290, 300)
    assert not is_improvement("fastest_pace", 310, 300)
    assert is_improvement("longest_distance", 10_000, 9_000)


def test_short_and_strength_activities_cannot_set_pace_records():
    assert "fastest_pace" not in activity_record_values(make_activity("2026-11-01 07:00", km=0.3))
    assert activity_record_values(make_activity("2026-11-01 07:00", sport="strength", km=None)) == {}


def test_format_record_value():
    assert format_record_value("running", "longest_distance", 21_100) == "21.10 km"
    assert format_record_value("running", "fastest_pace", 312) == "5:12 /km"
    assert format_record_value("swimming", "fastest_pace", 1050) == "1:45 /100m"
    assert format_record_value("cycling", "fastest_pace", 120) == "30.0 km/h"
    assert format_record_value("cycling", "longest_duration", 6303) == "1:45:03"


# ---------------------------------------------------------------- database updates


def sync_in(db, activities, first_sync=False):
    db.add_all(activities)
    db.flush()
    earned = process_new_activities(db, activities, award_pr_badges=not first_sync)
    db.commit()
    return earned


def test_first_sync_sets_records_without_pr_badges(db):
    earned = sync_in(db, [make_activity("2026-11-01 07:00", km=10, minutes=50)], first_sync=True)
    assert not [a for a in earned if a.category == "pr"]
    record = db.query(PersonalRecord).filter_by(sport="running", record_type="longest_distance").one()
    assert record.value == 10_000


def test_beating_a_record_earns_a_badge(db):
    sync_in(db, [make_activity("2026-11-01 07:00", km=10, minutes=50)], first_sync=True)
    earned = sync_in(db, [make_activity("2026-11-10 07:00", km=12, minutes=65)])
    titles = {a.title for a in earned}
    assert "New Running PR: Longest Distance" in titles
    assert "New Running PR: Fastest Pace" not in titles  # 5:25/km is slower than 5:00/km


def test_not_beating_a_record_earns_nothing(db):
    sync_in(db, [make_activity("2026-11-01 07:00", km=10, minutes=50)], first_sync=True)
    assert sync_in(db, [make_activity("2026-11-10 07:00", km=5, minutes=30)]) == []


def test_growing_record_week_only_earns_one_badge(db):
    sync_in(db, [make_activity("2026-10-20 07:00", km=10)], first_sync=True)  # baseline week: 10 km
    first = sync_in(db, [make_activity("2026-11-02 07:00", km=11)])
    second = sync_in(db, [make_activity("2026-11-03 07:00", km=5)])  # same week, now 16 km
    assert "New Running PR: Biggest Week" in {a.title for a in first}
    assert "New Running PR: Biggest Week" not in {a.title for a in second}
    week = db.query(PersonalRecord).filter_by(sport="running", record_type="biggest_week").one()
    assert week.value == 16_000


def test_streak_badges_awarded_once(db):
    sync_in(db, [make_activity(f"2026-11-0{n} 07:00", sport="strength", km=None) for n in range(1, 4)])
    sync_in(db, [make_activity("2026-11-04 07:00", sport="strength", km=None)])
    assert [a.badge_key for a in db.query(Achievement).filter_by(category="streak")] == ["streak:3"]


def test_only_run_ride_swim_and_lift_count_toward_streak(db):
    sync_in(db, [
        make_activity("2026-11-01 07:00", sport="cycling"),
        make_activity("2026-11-02 07:00", sport="strength", km=None),
        make_activity("2026-11-03 07:00", sport="other", km=3, garmin_type="walking"),
        make_activity("2026-11-04 07:00", sport="other", km=None, garmin_type="pilates"),
    ])
    assert db.query(Achievement).filter_by(category="streak").count() == 0
