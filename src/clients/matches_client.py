from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from src.config import ROOT_DIR, Settings
from src.storage.db import LocalDB


class MatchesClient:
    def __init__(self, settings: Settings, db: LocalDB) -> None:
        self.settings = settings
        self.db = db
        self.last_request_ts = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_ts
        wait = self.settings.min_request_interval_sec - elapsed
        if wait > 0:
            time.sleep(wait)
        self.last_request_ts = time.time()

    def _cached_get(self, url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        key_src = json.dumps({"url": url, "params": params}, sort_keys=True)
        cache_key = "matches:" + hashlib.sha256(key_src.encode("utf-8")).hexdigest()
        cached = self.db.get_cache(cache_key, self.settings.cache_ttl_minutes)
        if cached is not None:
            return cached

        attempts = 0
        while True:
            attempts += 1
            self._rate_limit()
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.settings.request_timeout_sec,
                )
                if response.status_code == 429:
                    time.sleep(min(8, attempts * 2))
                    if attempts < 4:
                        continue
                if 500 <= response.status_code < 600 and attempts < 4:
                    time.sleep(min(8, attempts * 2))
                    continue
                response.raise_for_status()
                payload = response.json()
                self.db.set_cache(cache_key, payload)
                return payload
            except requests.RequestException:
                if attempts >= 4:
                    raise
                time.sleep(min(8, attempts * 2))

    def _read_mock(self) -> list[dict[str, Any]]:
        path = ROOT_DIR / "data" / "mock_matches.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def get_matches(self, target_date: date) -> list[dict[str, Any]]:
        if self.settings.mock_mode or not self.settings.football_data_api_key:
            day = target_date.isoformat()
            return [m for m in self._read_mock() if m.get("date") == day]

        all_matches: list[dict[str, Any]] = []
        headers = {"X-Auth-Token": self.settings.football_data_api_key}

        for league in self.settings.leagues:
            url = f"{self.settings.football_data_base_url}/competitions/{league}/matches"
            params = {"dateFrom": target_date.isoformat(), "dateTo": target_date.isoformat()}
            data = self._cached_get(url=url, params=params, headers=headers)

            for m in data.get("matches", []):
                score = m.get("score", {})
                full = score.get("fullTime", {})
                all_matches.append(
                    {
                        "match_id": str(m.get("id")),
                        "date": target_date.isoformat(),
                        "league": m.get("competition", {}).get("name", league),
                        "league_code": league,
                        "home_team": m.get("homeTeam", {}).get("name"),
                        "away_team": m.get("awayTeam", {}).get("name"),
                        "start_time": m.get("utcDate"),
                        "status": m.get("status"),
                        "home_goals": full.get("home"),
                        "away_goals": full.get("away"),
                    }
                )

        return all_matches

    def get_historical_matches(self, end_date: date, lookback_days: int = 120) -> list[dict[str, Any]]:
        start_date = end_date - timedelta(days=lookback_days)

        if self.settings.mock_mode or not self.settings.football_data_api_key:
            all_mock = self._read_mock()
            return [
                m
                for m in all_mock
                if start_date.isoformat() <= m.get("date", "") <= end_date.isoformat() and m.get("status") == "FINISHED"
            ]

        all_matches: list[dict[str, Any]] = []
        headers = {"X-Auth-Token": self.settings.football_data_api_key}

        for league in self.settings.leagues:
            url = f"{self.settings.football_data_base_url}/competitions/{league}/matches"
            params = {"dateFrom": start_date.isoformat(), "dateTo": end_date.isoformat(), "status": "FINISHED"}
            data = self._cached_get(url=url, params=params, headers=headers)
            for m in data.get("matches", []):
                dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).date().isoformat()
                score = m.get("score", {})
                full = score.get("fullTime", {})
                all_matches.append(
                    {
                        "match_id": str(m.get("id")),
                        "date": dt,
                        "league": m.get("competition", {}).get("name", league),
                        "league_code": league,
                        "home_team": m.get("homeTeam", {}).get("name"),
                        "away_team": m.get("awayTeam", {}).get("name"),
                        "start_time": m.get("utcDate"),
                        "status": m.get("status"),
                        "home_goals": full.get("home"),
                        "away_goals": full.get("away"),
                    }
                )
        return all_matches
