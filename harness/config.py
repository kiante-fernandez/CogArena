import os
from urllib.parse import quote

from pydantic_settings import BaseSettings
from pathlib import Path


def _default_database_url() -> str:
    if os.environ.get("VERCEL"):
        turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
        turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
        if turso_url and turso_token:
            # Convert libsql:// to https:// for the SQLAlchemy driver
            host = turso_url.replace("libsql://", "")
            token_encoded = quote(turso_token, safe="")
            return f"sqlite+libsql://{host}?authToken={token_encoded}&secure=true"
        return ""
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
    ADMIN_API_KEY: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
