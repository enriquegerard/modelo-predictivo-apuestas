from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timezone
from typing import Any

import requests

from src.clients.espn_public import iter_espn_leagues, parse_espn_odds
from src.config import ROOT_DIR, Settings
from src.storage.db import LocalDB


def _norm_team(name: str) -> str:
    return " ".join((name or "").lower().replace("-", " ").split())


class OddsClient:
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

    def _cached_get(self, url: str, params: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
        key_src = json.dumps({"url": url, "params": params}, sort_keys=True)
        cache_key = "odds:" + hashlib.sha256(key_src.encode("utf-8")).hexdigest()
        cached = self.db.get_cache(cache_key, self.settings.cache_ttl_minutes)
        if cached is not None:
            return cached

        attempts = 0
        while True:
            attempts += 1
            self._rate_limit()
            try:
                response = requests.get(url, params=params, timeout=self.settings.request_timeout_sec)
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
        path = ROOT_DIR / "data" / "mock_odds.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _espn_get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        data = self._cached_get(url=url, params=params)
        if isinstance(data, list):
            return {}
        return data

    def get_odds(self, target_date: date) -> list[dict[str, Any]]:
        if self.settings.mock_mode:
            day = target_date.isoformat()
            return [o for o in self._read_mock() if o.get("date") == day]

        if not self.settings.the_odds_api_key:
            rows: list[dict[str, Any]] = []
            for _, league_slug in iter_espn_leagues(self.settings.leagues):
                url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_slug}/scoreboard"
                params = {"dates": target_date.strftime("%Y%m%d")}
                data = self._espn_get(url=url, params=params)
                rows.extend(parse_espn_odds(data, target_date=target_date))
            return rows

        if target_date != datetime.now(timezone.utc).date():
            return []

        rows: list[dict[str, Any]] = []
        for sport_key in self.settings.odds_sports:
            url = f"{self.settings.the_odds_base_url}/v4/sports/{sport_key}/odds"
            params = {
                "apiKey": self.settings.the_odds_api_key,
                "regions": "eu",
                "markets": "h2h",
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            }
            data = self._cached_get(url=url, params=params)
            for event in data:
                commence = event.get("commence_time")
                if not commence:
                    continue
                event_day = datetime.fromisoformat(commence.replace("Z", "+00:00")).date()
                if event_day != target_date:
                    continue

                home = event.get("home_team")
                away = next((t for t in event.get("teams", []) if t != home), None)
                best = {"home": None, "draw": None, "away": None}

                for book in event.get("bookmakers", []):
                    for market in book.get("markets", []):
                        if market.get("key") != "h2h":
                            continue
                        for out in market.get("outcomes", []):
                            name = _norm_team(out.get("name", ""))
                            price = out.get("price")
                            if not isinstance(price, (int, float)):
                                continue
                            if name == _norm_team(home):
                                best["home"] = max(best["home"] or 0, float(price))
                            elif name == _norm_team(away):
                                best["away"] = max(best["away"] or 0, float(price))
                            elif name in {"draw", "tie", "empate"}:
                                best["draw"] = max(best["draw"] or 0, float(price))

                if not (best["home"] and best["draw"] and best["away"]):
                    continue

                rows.append(
                    {
                        "date": target_date.isoformat(),
                        "league": event.get("sport_title", sport_key),
                        "home_team": home,
                        "away_team": away,
                        "start_time": commence,
                        "best_odds_home": best["home"],
                        "best_odds_draw": best["draw"],
                        "best_odds_away": best["away"],
                    }
                )
        return rows
