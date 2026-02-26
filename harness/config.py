from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "CogArena"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/cogarena.db"
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
