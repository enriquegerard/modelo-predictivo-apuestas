from __future__ import annotations

from datetime import date
from typing import Any


ESPN_LEAGUE_MAP: dict[str, str] = {
    # ─── Top 5 Europeas ──────────────────────────────────────────────
    "PL":   "eng.1",   # Premier League (Inglaterra)
    "PD":   "esp.1",   # La Liga (España)
    "SA":   "ita.1",   # Serie A (Italia)
    "BL1":  "ger.1",   # Bundesliga (Alemania)
    "FL1":  "fra.1",   # Ligue 1 (Francia)
    # ─── Segunda Línea Europea ───────────────────────────────────────
    "DED":  "ned.1",   # Eredivisie (Países Bajos)
    "PPL":  "por.1",   # Primeira Liga (Portugal)
    "ELC":  "eng.2",   # Championship (2ª División Inglaterra)
    "TUR":  "tur.1",   # Süper Lig (Turquía)
    "SPL":  "sco.1",   # Scottish Premiership (Escocia)
    "BEL":  "bel.1",   # Belgian Pro League (Bélgica)
    # ─── UEFA ────────────────────────────────────────────────────────
    "CL":   "uefa.champions",    # Champions League
    "EL":   "uefa.europa",       # Europa League
    "UECL": "uefa.europa.conf",  # Conference League
    # ─── Américas ────────────────────────────────────────────────────
    "MLS":  "usa.1",   # MLS (Estados Unidos)
    "MX1":  "mex.1",   # Liga MX (México)
    "BSA":  "bra.1",   # Brasileirão Serie A
    "ARG":  "arg.1",   # Primera División (Argentina)
}

# Human-readable display names for use in reports
ESPN_LEAGUE_DISPLAY: dict[str, str] = {
    "PL":   "Premier League",
    "PD":   "La Liga",
    "SA":   "Serie A",
    "BL1":  "Bundesliga",
    "FL1":  "Ligue 1",
    "DED":  "Eredivisie",
    "PPL":  "Primeira Liga",
    "ELC":  "Championship",
    "TUR":  "Süper Lig",
    "SPL":  "Scottish Premiership",
    "BEL":  "Belgian Pro League",
    "CL":   "UEFA Champions League",
    "EL":   "UEFA Europa League",
    "UECL": "UEFA Conference League",
    "MLS":  "MLS",
    "MX1":  "Liga MX",
    "BSA":  "Brasileirão",
    "ARG":  "Primera División Argentina",
}


def iter_espn_leagues(leagues: list[str]) -> list[tuple[str, str]]:
    return [(league_code, ESPN_LEAGUE_MAP[league_code]) for league_code in leagues if league_code in ESPN_LEAGUE_MAP]


def american_to_decimal(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        value = int(value)

    if not isinstance(value, (int, float)) or value == 0:
        return None

    value = float(value)
    if value > 0:
        return 1.0 + (value / 100.0)
    return 1.0 + (100.0 / abs(value))


def parse_espn_matches(scoreboard: dict[str, Any], league_code: str, target_date: date) -> list[dict[str, Any]]:
    league_name = scoreboard.get("leagues", [{}])[0].get("name", league_code)
    rows: list[dict[str, Any]] = []

    for event in scoreboard.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue

        status_type = competition.get("status", {}).get("type", {})
        completed = bool(status_type.get("completed"))

        rows.append(
            {
                "match_id": str(event.get("id")),
                "date": target_date.isoformat(),
                "league": league_name,
                "league_code": league_code,
                "home_team": home.get("team", {}).get("displayName"),
                "away_team": away.get("team", {}).get("displayName"),
                "start_time": event.get("date"),
                "status": "FINISHED" if completed else "SCHEDULED",
                "home_goals": int(home.get("score")) if completed and str(home.get("score", "")).isdigit() else None,
                "away_goals": int(away.get("score")) if completed and str(away.get("score", "")).isdigit() else None,
            }
        )

    return rows


def parse_espn_odds(scoreboard: dict[str, Any], target_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    league_name = scoreboard.get("leagues", [{}])[0].get("name")

    for event in scoreboard.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        odds_entry = (competition.get("odds") or [{}])[0]
        if not isinstance(odds_entry, dict):
            continue
        moneyline = odds_entry.get("moneyline", {})
        if not home or not away or not moneyline:
            continue

        home_price = american_to_decimal(moneyline.get("home", {}).get("close", {}).get("odds"))
        draw_price = american_to_decimal(moneyline.get("draw", {}).get("close", {}).get("odds"))
        away_price = american_to_decimal(moneyline.get("away", {}).get("close", {}).get("odds"))
        if not (home_price and draw_price and away_price):
            continue

        rows.append(
            {
                "date": target_date.isoformat(),
                "league": league_name,
                "home_team": home.get("team", {}).get("displayName"),
                "away_team": away.get("team", {}).get("displayName"),
                "start_time": event.get("date"),
                "best_odds_home": home_price,
                "best_odds_draw": draw_price,
                "best_odds_away": away_price,
                "source": odds_entry.get("provider", {}).get("displayName", "ESPN"),
            }
        )

    return rows


def parse_espn_team_stats(standings: dict[str, Any], league_code: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    league_name = standings.get("name", league_code)

    for child in standings.get("children", []):
        for entry in child.get("standings", {}).get("entries", []):
            stats = {item.get("name"): item.get("value") for item in entry.get("stats", [])}
            team_name = entry.get("team", {}).get("displayName")
            games_played = float(stats.get("gamesPlayed") or 0.0)
            goals_for = float(stats.get("pointsFor") or 0.0)
            goals_against = float(stats.get("pointsAgainst") or 0.0)
            if not team_name or games_played <= 0:
                continue

            rows.append(
                {
                    "league": league_name,
                    "league_code": league_code,
                    "team": team_name,
                    "games_played": games_played,
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                }
            )

    return rows


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace("%", "")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def parse_espn_form_event_ids(summary: dict[str, Any]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for team_block in summary.get("boxscore", {}).get("form", []):
        team_name = team_block.get("team", {}).get("displayName")
        event_ids = []
        for item in team_block.get("events", []):
            event_id = item.get("id")
            if event_id:
                event_ids.append(str(event_id))
        if team_name:
            rows[team_name] = event_ids
    return rows


def parse_espn_event_team_stats(summary: dict[str, Any]) -> list[dict[str, Any]]:
    teams = summary.get("boxscore", {}).get("teams", [])
    if len(teams) != 2:
        return []

    competitor_rows = {}
    for competitor in summary.get("header", {}).get("competitions", [{}])[0].get("competitors", []):
        team_name = competitor.get("team", {}).get("displayName")
        if team_name:
            competitor_rows[team_name] = competitor

    parsed = []
    for idx, team_row in enumerate(teams):
        team_name = team_row.get("team", {}).get("displayName")
        opp_row = teams[1 - idx]
        opp_name = opp_row.get("team", {}).get("displayName")
        if not team_name or not opp_name:
            continue

        stats_map = {item.get("name"): _safe_float(item.get("displayValue")) for item in team_row.get("statistics", [])}
        opp_stats_map = {item.get("name"): _safe_float(item.get("displayValue")) for item in opp_row.get("statistics", [])}
        team_competitor = competitor_rows.get(team_name, {})
        opp_competitor = competitor_rows.get(opp_name, {})
        yellow_cards = stats_map.get("yellowCards") or 0.0
        red_cards = stats_map.get("redCards") or 0.0
        opp_yellow_cards = opp_stats_map.get("yellowCards") or 0.0
        opp_red_cards = opp_stats_map.get("redCards") or 0.0

        parsed.append(
            {
                "event_id": str(summary.get("header", {}).get("id") or ""),
                "date": summary.get("header", {}).get("competitions", [{}])[0].get("date"),
                "team": team_name,
                "opponent": opp_name,
                "home_away": team_row.get("homeAway"),
                "goals_for": _safe_float(team_competitor.get("score")) or 0.0,
                "goals_against": _safe_float(opp_competitor.get("score")) or 0.0,
                "shots_for": stats_map.get("totalShots") or 0.0,
                "shots_against": opp_stats_map.get("totalShots") or 0.0,
                "shots_on_target_for": stats_map.get("shotsOnTarget") or 0.0,
                "shots_on_target_against": opp_stats_map.get("shotsOnTarget") or 0.0,
                "corners_for": stats_map.get("wonCorners") or 0.0,
                "corners_against": opp_stats_map.get("wonCorners") or 0.0,
                "yellow_cards": yellow_cards,
                "red_cards": red_cards,
                "cards_weighted": yellow_cards + 2.0 * red_cards,
                "cards_against_weighted": opp_yellow_cards + 2.0 * opp_red_cards,
            }
        )

    return parsed