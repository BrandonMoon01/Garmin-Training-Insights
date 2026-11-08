"""Realistic fake Garmin activities, for demos and for developing the app
without calling Garmin.

Activities are returned in the same raw shape Garmin uses, so they go through
the exact same `normalize_activity` -> sync path as real data.
"""

import random
from datetime import date, datetime, time, timedelta

# Weekday (0 = Monday) -> the session usually done that day.
WEEKLY_PLAN = {
    0: "strength",
    1: "easy_run",
    2: "swim",
    3: "strength",
    4: "easy_ride",
    5: "long_ride",
    6: "long_run",
}


def _session(kind: str, rng: random.Random, fitness: float) -> dict:
    """Type/duration/distance/HR for one session. `fitness` slowly grows over
    time so PRs keep happening in the sample data."""
    if kind == "strength":
        return {"activityType": {"typeKey": "strength_training"}, "activityName": "Strength",
                "duration": rng.uniform(45, 65) * 60, "averageHR": rng.randint(105, 125)}
    if kind == "swim":
        meters = round(rng.uniform(1500, 2500) * fitness, -1)
        pace_per_100m = rng.uniform(110, 130) / fitness
        return {"activityType": {"typeKey": "lap_swimming"}, "activityName": "Pool Swim",
                "distance": meters, "duration": meters / 100 * pace_per_100m, "averageHR": rng.randint(125, 145)}
    if kind in ("easy_run", "long_run"):
        km = (rng.uniform(5, 9) if kind == "easy_run" else rng.uniform(12, 20)) * fitness
        pace_per_km = rng.uniform(315, 350) / fitness
        return {"activityType": {"typeKey": "running"}, "activityName": "Long Run" if kind == "long_run" else "Easy Run",
                "distance": km * 1000, "duration": km * pace_per_km, "averageHR": rng.randint(138, 158)}
    km = (rng.uniform(20, 30) if kind == "easy_ride" else rng.uniform(40, 80)) * fitness
    kmh = rng.uniform(25, 30) * fitness
    return {"activityType": {"typeKey": "road_biking"}, "activityName": "Long Ride" if kind == "long_ride" else "Easy Ride",
            "distance": km * 1000, "duration": km / kmh * 3600, "averageHR": rng.randint(125, 150)}


def generate_sample_activities(today: date, days: int = 120) -> list[dict]:
    activities = []
    for days_ago in range(days, -1, -1):
        day = today - timedelta(days=days_ago)
        # Seeding by date keeps each day's workout identical across runs, so
        # re-syncing sample data behaves like re-syncing real data.
        rng = random.Random(day.toordinal())
        if rng.random() < 0.1:  # occasional rest day
            continue
        kind = WEEKLY_PLAN[day.weekday()]
        fitness = 1 + (days - days_ago) / 600
        activity = _session(kind, rng, fitness)
        activity.update({
            "activityId": f"sample-{day.isoformat()}-{kind}",
            "startTimeLocal": datetime.combine(day, time(7, 0)).isoformat(sep=" "),
            "calories": int(activity["duration"] / 60 * rng.uniform(8, 12)),
        })
        activities.append(activity)
    return activities


class SampleGarminClient:
    """Drop-in replacement for `GarminClient` that serves generated activities."""

    def fetch_activities(self, start: date, end: date) -> list[dict]:
        return [
            activity
            for activity in generate_sample_activities(end)
            if start <= date.fromisoformat(activity["startTimeLocal"][:10]) <= end
        ]
