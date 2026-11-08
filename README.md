# Garmin Training Insights

A personal training app built on my own Garmin data. I run, cycle, swim and lift;
this pulls those workouts from the **Garmin Connect Personal API**, turns them
into training analytics, and rewards consistency with streaks, PRs and badges.

| Phase | What | Status |
|---|---|---|
| 1 | Python backend: Garmin sync, analytics, gamification, REST API | **Done** |
| 2 | iPhone app (React Native / Expo) on top of the API | Next |
| 3 | AI coach agent (Claude tool-calling, driven by a spec file) | Later |

## How it works

```
Garmin Personal API ──► sync ──► SQLite ──► REST API (FastAPI) ──► iPhone app
                         │
                         └─► gamification (PRs, streak badges)
```

1. **Sync** (`app/services/sync.py`) fetches workouts newer than the last one
   stored, converts them with `normalize_activity`, and skips any it already has.
2. Right after saving, **gamification** (`app/services/gamification.py`) checks
   for new personal records and streak milestones and stores any badges earned.
3. The **API** serves activities plus analytics that are calculated on request
   (`app/services/analytics.py`), so they're never stale.

### Project layout (`backend/`)

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app setup |
| `app/cli.py` | `python -m app.cli` – sync from the terminal |
| `app/config.py` | Settings from `.env` |
| `app/models.py` | Tables: `activities`, `personal_records`, `achievements` |
| `app/schemas.py` | JSON response shapes |
| `app/routers/` | One file per group of endpoints |
| `app/services/garmin_client.py` | Garmin HTTP calls + raw → `Activity` conversion |
| `app/services/sample_data.py` | Fake-but-realistic workouts for demos |
| `app/services/analytics.py` | Training load, weekly summaries (pure functions) |
| `app/services/gamification.py` | Streaks, PRs, badges |
| `tests/` | pytest suite (no network calls) |

## Key concepts

**Training load (ACWR).** Load is minutes trained, which works for every sport,
lifting included. The *acute:chronic workload ratio* compares the last 7 days
with the weekly average of the last 28. Roughly 0.8–1.3 is the "sweet spot";
above ~1.5 means a spike that's linked to injury risk.

**Streaks.** Consecutive days with at least one run, ride, swim or lifting
session. Walks, yoga, hiking and other activities don't count. A streak stays
alive until the end of the day after your last workout. Badges unlock at 3, 7, 14, 30, 60, 100
and 365 days.

**PRs** (running, cycling, swimming):
- per workout: longest distance, longest duration, fastest pace (pace needs a
  minimum distance, so a short jog can't count)
- per period: biggest week, biggest month by distance

The first sync sets these as quiet baselines. Importing a year of history
would otherwise award hundreds of badges at once. After that, every new PR
earns a badge.

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/activities?sport=&start=&end=&limit=` | Workouts, newest first |
| GET | `/training-load?days=42` | Daily load, ACWR and zone |
| GET | `/summary/weekly?weeks=8` | Per-sport weekly totals |
| GET | `/records` | Current PRs with display values (`"5:12 /km"`) |
| GET | `/streaks` | Current and longest streak |
| GET | `/achievements` | Badges earned, newest first |
| POST | `/sync` | Pulls new workouts and returns any new badges |

Interactive docs: http://localhost:8000/docs once the server is running.

## Running it

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then fill it in (see below)

.venv/bin/python -m app.cli --sample   # load sample data, or omit --sample for Garmin
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0   # --host lets the phone reach it
.venv/bin/pytest
```

### Connecting Garmin

1. In Garmin Connect, open the **Personal API Key** page and create a key.
   It's shown only once, so put it straight into `.env` as `GARMIN_API_KEY`.
2. From the Personal API Swagger docs, copy the base URL, the token endpoint
   and the activities endpoint into `.env`.
3. If Garmin's field names differ from the standard activity-summary names,
   `normalize_activity` in `garmin_client.py` is the only function to update.
4. Delete `training.db` if you loaded sample data, then run `python -m app.cli`.
