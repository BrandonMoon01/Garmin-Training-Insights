"""Run a sync from the terminal.

    python -m app.cli            # real Garmin data (needs .env)
    python -m app.cli --sample   # generated sample data
"""

import argparse

from app.database import SessionLocal, init_db
from app.services.sync import get_client, run_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync workouts from Garmin.")
    parser.add_argument("--sample", action="store_true", help="use generated sample data instead of Garmin")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        result = run_sync(db, get_client(use_sample_data=args.sample or None))
        print(f"Synced {result.new_activities} new activities.")
        for achievement in result.new_achievements:
            print(f"  Badge earned: {achievement.title} ({achievement.description})")


if __name__ == "__main__":
    main()
