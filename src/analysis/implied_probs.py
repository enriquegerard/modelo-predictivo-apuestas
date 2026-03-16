from __future__ import annotations

from typing import Dict


def normalized_implied_probabilities(odds_home: float, odds_draw: float, odds_away: float) -> Dict[str, float]:
    raw = {
        "home": (1.0 / odds_home) if odds_home and odds_home > 1 else 0.0,
        "draw": (1.0 / odds_draw) if odds_draw and odds_draw > 1 else 0.0,
        "away": (1.0 / odds_away) if odds_away and odds_away > 1 else 0.0,
    }
    total = sum(raw.values())
    if total <= 0:
        return {"home": 0.0, "draw": 0.0, "away": 0.0, "overround": 0.0}

    return {
        "home": raw["home"] / total,
        "draw": raw["draw"] / total,
        "away": raw["away"] / total,
        "overround": total,
    }
