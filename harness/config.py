import os

from pydantic_settings import BaseSettings
from pathlib import Path


def _default_database_url() -> str:
    if os.environ.get("VERCEL"):
        return ""  # Must be set via environment variable on Vercel
    return "sqlite+aiosqlite:///./data/cogarena.db"


class Settings(BaseSettings):
    APP_NAME: str = "CogArena"
    DATABASE_URL: str = _default_database_url()
    TASKS_DIR: Path = Path(__file__).parent.parent / "tasks"
    JSPSYCH_DIR: Path = Path(__file__).parent.parent / "jsPsych-8.2.3"
    DATA_DIR: Path = Path(__file__).parent.parent / "data"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    SESSION_TIMEOUT_HOURS: int = 24

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
