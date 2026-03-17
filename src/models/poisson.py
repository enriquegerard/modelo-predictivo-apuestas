from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class PoissonModel:
    max_goals: int = 6
    min_matches_per_team: int = 3

    def __post_init__(self) -> None:
        self.fitted = False
        self.league_home_avg = 1.35
        self.league_away_avg = 1.10
        self.attack_home: Dict[str, float] = {}
        self.defense_home: Dict[str, float] = {}
        self.attack_away: Dict[str, float] = {}
        self.defense_away: Dict[str, float] = {}
        self.home_matches_count: Dict[str, int] = {}
        self.away_matches_count: Dict[str, int] = {}
        self.season_games_count: Dict[str, int] = {}
        self.sample_source: str = "default"

    def fit(self, matches_df: pd.DataFrame) -> "PoissonModel":
        if matches_df.empty:
            self.sample_source = "fallback"
            self.fitted = True
            return self

        finished = matches_df.dropna(subset=["home_goals", "away_goals"]).copy()
        if finished.empty:
            self.sample_source = "fallback"
            self.fitted = True
            return self

        self.sample_source = "historical_matches"

        self.league_home_avg = max(finished["home_goals"].mean(), 0.2)
        self.league_away_avg = max(finished["away_goals"].mean(), 0.2)

        home_for = defaultdict(list)
        home_against = defaultdict(list)
        away_for = defaultdict(list)
        away_against = defaultdict(list)

        for _, row in finished.iterrows():
            ht = row["home_team"]
            at = row["away_team"]
            hg = float(row["home_goals"])
            ag = float(row["away_goals"])

            home_for[ht].append(hg)
            home_against[ht].append(ag)
            away_for[at].append(ag)
            away_against[at].append(hg)

        for team, vals in home_for.items():
            self.home_matches_count[team] = len(vals)
            if len(vals) >= self.min_matches_per_team:
                self.attack_home[team] = (sum(vals) / len(vals)) / self.league_home_avg
        for team, vals in home_against.items():
            if len(vals) >= self.min_matches_per_team:
                self.defense_home[team] = (sum(vals) / len(vals)) / self.league_away_avg
        for team, vals in away_for.items():
            self.away_matches_count[team] = len(vals)
            if len(vals) >= self.min_matches_per_team:
                self.attack_away[team] = (sum(vals) / len(vals)) / self.league_away_avg
        for team, vals in away_against.items():
            if len(vals) >= self.min_matches_per_team:
                self.defense_away[team] = (sum(vals) / len(vals)) / self.league_home_avg

        self.fitted = True
        return self

    def fit_from_team_stats(self, team_stats_df: pd.DataFrame) -> "PoissonModel":
        if team_stats_df.empty:
            self.sample_source = "fallback"
            self.fitted = True
            return self

        stats = team_stats_df.copy()
        stats = stats[stats["games_played"] > 0].copy()
        if stats.empty:
            self.sample_source = "fallback"
            self.fitted = True
            return self

        self.sample_source = "season_team_stats"

        stats["gf_pg"] = stats["goals_for"] / stats["games_played"]
        stats["ga_pg"] = stats["goals_against"] / stats["games_played"]

        league_avg = max(float(stats["gf_pg"].mean()), 0.4)
        self.league_home_avg = max(league_avg * 1.08, 0.4)
        self.league_away_avg = max(league_avg * 0.92, 0.3)

        for _, row in stats.iterrows():
            team = row["team"]
            self.season_games_count[team] = int(row.get("games_played") or 0)
            attack = min(max(float(row["gf_pg"]) / league_avg, 0.45), 2.25)
            defense = min(max(float(row["ga_pg"]) / league_avg, 0.45), 2.25)
            self.attack_home[team] = attack * 1.04
            self.attack_away[team] = attack * 0.96
            self.defense_home[team] = defense * 0.96
            self.defense_away[team] = defense * 1.04

        self.fitted = True
        return self

    def get_team_sample_sizes(self, home_team: str, away_team: str) -> Dict[str, int | str]:
        return {
            "source": self.sample_source,
            "home_model_sample": int(
                self.season_games_count.get(home_team)
                or self.home_matches_count.get(home_team)
                or 0
            ),
            "away_model_sample": int(
                self.season_games_count.get(away_team)
                or self.away_matches_count.get(away_team)
                or 0
            ),
        }

    @staticmethod
    def _poisson_pmf(k: int, lam: float) -> float:
        return math.exp(-lam) * (lam**k) / math.factorial(k)

    def expected_goals(self, home_team: str, away_team: str) -> tuple[float, float]:
        if not self.fitted:
            raise RuntimeError("El modelo Poisson no está ajustado. Ejecuta fit() primero.")

        ah = self.attack_home.get(home_team, 1.0)
        dh = self.defense_home.get(home_team, 1.0)
        aa = self.attack_away.get(away_team, 1.0)
        da = self.defense_away.get(away_team, 1.0)

        lambda_home = max(0.15, self.league_home_avg * ah * da)
        lambda_away = max(0.15, self.league_away_avg * aa * dh)
        return lambda_home, lambda_away

    def most_likely_score(self, home_team: str, away_team: str) -> tuple[int, int, float]:
        return self.top_scorelines(home_team, away_team, top_n=1)[0]

    def score_matrix(self, home_team: str, away_team: str) -> list[tuple[int, int, float]]:
        lambda_home, lambda_away = self.expected_goals(home_team, away_team)
        rows: list[tuple[int, int, float]] = []
        for i in range(self.max_goals + 1):
            pi = self._poisson_pmf(i, lambda_home)
            for j in range(self.max_goals + 1):
                pj = self._poisson_pmf(j, lambda_away)
                rows.append((i, j, pi * pj))
        return rows

    def top_scorelines(self, home_team: str, away_team: str, top_n: int = 3) -> list[tuple[int, int, float]]:
        rows = sorted(self.score_matrix(home_team, away_team), key=lambda item: item[2], reverse=True)
        return rows[:top_n]

    def derived_market_probs(self, home_team: str, away_team: str) -> Dict[str, float]:
        matrix = self.score_matrix(home_team, away_team)
        p_btts_yes = sum(prob for i, j, prob in matrix if i >= 1 and j >= 1)
        p_over_15 = sum(prob for i, j, prob in matrix if i + j >= 2)
        p_over_25 = sum(prob for i, j, prob in matrix if i + j >= 3)
        p_over_35 = sum(prob for i, j, prob in matrix if i + j >= 4)
        p_under_25 = sum(prob for i, j, prob in matrix if i + j <= 2)
        p_home_clean_sheet = sum(prob for i, j, prob in matrix if j == 0)
        p_away_clean_sheet = sum(prob for i, j, prob in matrix if i == 0)
        total = sum(prob for _, _, prob in matrix) or 1.0
        return {
            "btts_yes": p_btts_yes / total,
            "btts_no": 1.0 - (p_btts_yes / total),
            "over_1_5": p_over_15 / total,
            "over_2_5": p_over_25 / total,
            "over_3_5": p_over_35 / total,
            "under_2_5": p_under_25 / total,
            "home_clean_sheet": p_home_clean_sheet / total,
            "away_clean_sheet": p_away_clean_sheet / total,
        }

    def predict_1x2(self, home_team: str, away_team: str) -> Dict[str, float]:
        if not self.fitted:
            raise RuntimeError("El modelo Poisson no está ajustado. Ejecuta fit() primero.")

        lambda_home, lambda_away = self.expected_goals(home_team, away_team)

        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0

        for i in range(self.max_goals + 1):
            pi = self._poisson_pmf(i, lambda_home)
            for j in range(self.max_goals + 1):
                pj = self._poisson_pmf(j, lambda_away)
                p = pi * pj
                if i > j:
                    p_home += p
                elif i == j:
                    p_draw += p
                else:
                    p_away += p

        total = p_home + p_draw + p_away
        if total <= 0:
            return {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}

        return {
            "home": p_home / total,
            "draw": p_draw / total,
            "away": p_away / total,
        }
