from datetime import date, datetime

import httpx
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Activity
from app.routers.sync import activity_source
from app.services.garmin_client import BASE_URL, PAGE_SIZE, GarminClient, normalize_activity, sport_for
from app.services.sample_data import SampleGarminClient
from app.services.sync import run_sync

TODAY = date(2026, 11, 6)


def test_sport_for_maps_garmin_types():
    assert sport_for("TRAIL_RUNNING") == "running"
    assert sport_for("indoor_cycling") == "cycling"
    assert sport_for("open_water_swimming") == "swimming"
    assert sport_for("strength_training") == "strength"
    assert sport_for("yoga") == "other"


def test_normalize_activity():
    raw = {
        "activityId": 42,
        "activityName": "Morning Run",
        "activityType": {"typeKey": "trail_running", "typeId": 6},
        "startTimeLocal": "2026-11-06 06:30:00",
        "duration": 1800.0,
        "distance": 5000.0,
        "averageHR": 151.0,
        "calories": 410.0,
    }
    fields = normalize_activity(raw)
    assert fields["garmin_activity_id"] == "42"
    assert fields["sport"] == "running"
    assert fields["start_time"] == datetime(2026, 11, 6, 6, 30)
    assert fields["avg_heart_rate"] == 151
    assert fields["max_heart_rate"] is None


def test_garmin_client_gets_token_then_pages_through_activities():
    requests = []

    def fake_garmin(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(200, text="fake-jwt\n")  # token comes back as plain text
        offset = int(request.url.params["start"])
        remaining = max(0, 150 - offset)  # pretend there are 150 activities
        return httpx.Response(200, json=[{"activityId": offset + i} for i in range(min(PAGE_SIZE, remaining))])

    http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(fake_garmin))
    activities = GarminClient("my-key", http=http).fetch_activities(date(2026, 1, 1), date(2026, 11, 6))

    assert len(activities) == 150
    token_request, first_page, second_page = requests
    assert token_request.headers["Authorization"] == "ApiKey my-key"
    assert first_page.headers["Authorization"] == "Bearer fake-jwt"
    assert first_page.url.params["startDate"] == "2026-01-01"
    assert (first_page.url.params["start"], second_page.url.params["start"]) == ("0", "100")


def test_resyncing_never_duplicates(db):
    first = run_sync(db, SampleGarminClient(), today=TODAY)
    second = run_sync(db, SampleGarminClient(), today=TODAY)
    assert first.new_activities > 50
    assert second.new_activities == 0
    assert db.query(Activity).count() == first.new_activities


def test_api_endpoints_with_sample_data(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[activity_source] = SampleGarminClient
    try:
        client = TestClient(app)
        sync = client.post("/sync").json()
        assert sync["new_activities"] > 50

        assert len(client.get("/activities", params={"sport": "swimming", "limit": 5}).json()) == 5
        assert client.get("/training-load").json()["days"]
        assert len(client.get("/summary/weekly", params={"weeks": 4}).json()) == 4
        assert client.get("/streaks").json()["longest_days"] >= 3
        assert {r["sport"] for r in client.get("/records").json()} == {"running", "cycling", "swimming"}
        assert client.get("/achievements").json()
    finally:
        app.dependency_overrides.clear()
