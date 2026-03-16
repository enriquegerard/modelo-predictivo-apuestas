from __future__ import annotations

from typing import Dict


def compute_edges(model_probs: Dict[str, float], implied_probs: Dict[str, float]) -> Dict[str, float]:
    edge_home = model_probs.get("home", 0.0) - implied_probs.get("home", 0.0)
    edge_draw = model_probs.get("draw", 0.0) - implied_probs.get("draw", 0.0)
    edge_away = model_probs.get("away", 0.0) - implied_probs.get("away", 0.0)

    max_edge = max(edge_home, edge_draw, edge_away)
    spread = abs(edge_home) + abs(edge_draw) + abs(edge_away)
    score = max(max_edge, 0.0) * 100 + spread * 10

    return {
        "edge_home": edge_home,
        "edge_draw": edge_draw,
        "edge_away": edge_away,
        "edge_max": max_edge,
        "score": score,
    }
