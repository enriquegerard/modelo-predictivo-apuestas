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

    def fit(self, matches_df: pd.DataFrame) -> "PoissonModel":
        if matches_df.empty:
            self.fitted = True
            return self

        finished = matches_df.dropna(subset=["home_goals", "away_goals"]).copy()
        if finished.empty:
            self.fitted = True
            return self

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
            if len(vals) >= self.min_matches_per_team:
                self.attack_home[team] = (sum(vals) / len(vals)) / self.league_home_avg
        for team, vals in home_against.items():
            if len(vals) >= self.min_matches_per_team:
                self.defense_home[team] = (sum(vals) / len(vals)) / self.league_away_avg
        for team, vals in away_for.items():
            if len(vals) >= self.min_matches_per_team:
                self.attack_away[team] = (sum(vals) / len(vals)) / self.league_away_avg
        for team, vals in away_against.items():
            if len(vals) >= self.min_matches_per_team:
                self.defense_away[team] = (sum(vals) / len(vals)) / self.league_home_avg

        self.fitted = True
        return self

    @staticmethod
    def _poisson_pmf(k: int, lam: float) -> float:
        return math.exp(-lam) * (lam**k) / math.factorial(k)

    def predict_1x2(self, home_team: str, away_team: str) -> Dict[str, float]:
        if not self.fitted:
            raise RuntimeError("El modelo Poisson no está ajustado. Ejecuta fit() primero.")

        ah = self.attack_home.get(home_team, 1.0)
        dh = self.defense_home.get(home_team, 1.0)
        aa = self.attack_away.get(away_team, 1.0)
        da = self.defense_away.get(away_team, 1.0)

        lambda_home = max(0.15, self.league_home_avg * ah * da)
        lambda_away = max(0.15, self.league_away_avg * aa * dh)

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
