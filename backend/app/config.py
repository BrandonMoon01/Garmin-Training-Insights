"""App settings, loaded from environment variables or backend/.env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{BACKEND_DIR / 'training.db'}"

    # Personal API key from Garmin Connect (Settings -> Personal API Key).
    garmin_api_key: str = ""

    # Use generated fake workouts instead of calling Garmin (handy for demos/dev).
    use_sample_data: bool = False

    # How far back the very first sync reaches.
    initial_sync_days: int = 365


settings = Settings()
