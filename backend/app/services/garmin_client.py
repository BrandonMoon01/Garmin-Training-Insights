"""Fetching workouts from the Garmin Connect Personal API.

Two pieces live here:
  * `GarminClient` - the HTTP calls: personal API key -> access token -> activities.
  * `normalize_activity` - turns one raw Garmin activity dict into the fields
    of our `Activity` table.

Endpoints and auth follow Garmin's official sample client:
https://github.com/garmin/connect-personal-api-python
"""

from datetime import date, datetime

import httpx

BASE_URL = "https://personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
ACTIVITIES_PATH = "/activitylist-service/activities/search/activities"
PAGE_SIZE = 100


def sport_for(garmin_activity_type: str) -> str:
    """Collapse Garmin's many activity types into our five sports."""
    activity_type = garmin_activity_type.lower()
    if "swim" in activity_type:
        return "swimming"
    if "run" in activity_type:
        return "running"
    if "cycl" in activity_type or "bik" in activity_type or "ride" in activity_type:
        return "cycling"
    if "strength" in activity_type or "weight" in activity_type:
        return "strength"
    return "other"


def normalize_activity(raw: dict) -> dict:
    """Convert a raw Garmin activity into keyword arguments for `Activity(...)`."""
    garmin_type = raw["activityType"]["typeKey"]

    def optional_int(key: str) -> int | None:
        return int(raw[key]) if raw.get(key) is not None else None

    return {
        "garmin_activity_id": str(raw["activityId"]),
        "sport": sport_for(garmin_type),
        "garmin_activity_type": garmin_type,
        "name": raw.get("activityName") or "",
        # Local time, so "which day was this workout?" matches what you'd say
        # (matters for streaks). Format: "2026-11-06 07:00:00".
        "start_time": datetime.fromisoformat(raw["startTimeLocal"]),
        "duration_seconds": float(raw["duration"]),
        "distance_meters": raw.get("distance") or None,
        "avg_heart_rate": optional_int("averageHR"),
        "max_heart_rate": optional_int("maxHR"),
        "calories": optional_int("calories"),
    }


class GarminClient:
    def __init__(self, api_key: str, http: httpx.Client | None = None):
        if not api_key:
            raise RuntimeError(
                "GARMIN_API_KEY is not set. Add it to backend/.env, "
                "or use sample data with USE_SAMPLE_DATA=true."
            )
        self.api_key = api_key
        self.http = http or httpx.Client(base_url=BASE_URL, timeout=30)
        self._token: str | None = None

    def fetch_activities(self, start: date, end: date) -> list[dict]:
        """All raw activities from `start` to `end` (inclusive), page by page."""
        activities = []
        while True:
            response = self.http.get(
                ACTIVITIES_PATH,
                headers={"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json"},
                params={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "start": len(activities),  # offset of the first result on this page
                    "limit": PAGE_SIZE,
                },
            )
            response.raise_for_status()
            page = response.json()
            activities.extend(page)
            if len(page) < PAGE_SIZE:
                return activities

    def _access_token(self) -> str:
        """Exchange the personal API key for an access token.

        Tokens last 24 hours and a client only lives for one sync, so one token
        per client is plenty. Garmin returns the token as plain text, not JSON.
        """
        if self._token is None:
            response = self.http.post(
                TOKEN_PATH,
                headers={"Authorization": f"ApiKey {self.api_key}", "Accept": "*/*"},
            )
            response.raise_for_status()
            self._token = response.text.strip()
        return self._token
