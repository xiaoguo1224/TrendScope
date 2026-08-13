from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "TrendScope"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    data_dir: Path = PROJECT_ROOT / "data"
    database_path: Path | None = None

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRENDSCOPE_")

    @property
    def resolved_database_path(self) -> Path:
        return self.database_path or self.data_dir / "app.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.resolved_database_path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
