from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic import ValidationError
from pydantic.dataclasses import dataclass as pydantic_dataclass


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@pydantic_dataclass
class Settings:
    timezone: str = Field(default="Europe/Madrid")
    leagues: List[str] = Field(default_factory=lambda: ["PL", "PD", "SA"])
    odds_sports: List[str] = Field(default_factory=lambda: ["soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a"])
    football_data_api_key: str | None = Field(default=None)
    football_data_base_url: str = Field(default="https://api.football-data.org/v4")
    the_odds_api_key: str | None = Field(default=None)
    the_odds_base_url: str = Field(default="https://api.the-odds-api.com")
    request_timeout_sec: int = Field(default=15)
    min_request_interval_sec: float = Field(default=0.35)
    cache_ttl_minutes: int = Field(default=15)
    mock_mode: bool = Field(default=False)
    db_path: str = Field(default=str(ROOT_DIR / "data" / "app.db"))


def _split_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or default


def get_settings() -> Settings:
    _load_dotenv(ENV_PATH)
    try:
        settings = Settings(
            timezone=os.getenv("TIMEZONE", "Europe/Madrid"),
            leagues=_split_csv(os.getenv("LEAGUES"), ["PL", "PD", "SA"]),
            odds_sports=_split_csv(
                os.getenv("ODDS_SPORTS"),
                ["soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a"],
            ),
            football_data_api_key=os.getenv("FOOTBALL_DATA_API_KEY"),
            football_data_base_url=os.getenv("FOOTBALL_DATA_BASE_URL", "https://api.football-data.org/v4"),
            the_odds_api_key=os.getenv("THE_ODDS_API_KEY"),
            the_odds_base_url=os.getenv("THE_ODDS_BASE_URL", "https://api.the-odds-api.com"),
            request_timeout_sec=int(os.getenv("REQUEST_TIMEOUT_SEC", "15")),
            min_request_interval_sec=float(os.getenv("MIN_REQUEST_INTERVAL_SEC", "0.35")),
            cache_ttl_minutes=int(os.getenv("CACHE_TTL_MINUTES", "15")),
            mock_mode=os.getenv("MOCK_MODE", "false").lower() in {"1", "true", "yes"},
            db_path=os.getenv("DB_PATH", str(ROOT_DIR / "data" / "app.db")),
        )
    except ValidationError as exc:
        raise RuntimeError(f"Configuración inválida: {exc}") from exc

    return settings
