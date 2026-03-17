from __future__ import annotations

from typing import Any


def _avg(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def summarize_recent_team_metrics(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    return {
        "goals_for": _avg(rows, "goals_for"),
        "goals_against": _avg(rows, "goals_against"),
        "shots_for": _avg(rows, "shots_for"),
        "shots_against": _avg(rows, "shots_against"),
        "shots_on_target_for": _avg(rows, "shots_on_target_for"),
        "shots_on_target_against": _avg(rows, "shots_on_target_against"),
        "corners_for": _avg(rows, "corners_for"),
        "corners_against": _avg(rows, "corners_against"),
        "cards_weighted": _avg(rows, "cards_weighted"),
        "cards_against_weighted": _avg(rows, "cards_against_weighted"),
    }


def build_form_string(rows: list[dict[str, Any]], max_matches: int = 5) -> str:
    if not rows:
        return "Sin datos"
    symbols: list[str] = []
    for row in rows[:max_matches]:
        gf = float(row.get("goals_for") or 0.0)
        ga = float(row.get("goals_against") or 0.0)
        if gf > ga:
            symbols.append("W")
        elif gf < ga:
            symbols.append("L")
        else:
            symbols.append("D")
    return "".join(symbols)


def _blend(primary: float | None, secondary: float | None, fallback: float) -> float:
    if primary is None and secondary is None:
        return fallback
    if primary is None:
        return float(secondary)
    if secondary is None:
        return float(primary)
    return (float(primary) + float(secondary)) / 2.0


def outcome_label(model_home: float, model_draw: float, model_away: float) -> str:
    best = max(
        [("Local", model_home), ("Empate", model_draw), ("Visitante", model_away)],
        key=lambda item: item[1],
    )
    return best[0]


def total_goals_band(expected_total_goals: float) -> str:
    if expected_total_goals < 2.2:
        return "Partido de pocos goles"
    if expected_total_goals < 3.1:
        return "Partido de goles moderados"
    return "Partido de goles altos"


def _yes_no_label(prob_yes: float, yes_label: str, no_label: str) -> str:
    return yes_label if prob_yes >= 0.5 else no_label


def _confidence_label(max_outcome_prob: float, edge_max: float) -> tuple[str, str]:
    score = max_outcome_prob + max(edge_max, 0.0)
    if score >= 0.72:
        return "Alta", "███"
    if score >= 0.58:
        return "Media", "██░"
    return "Baja", "█░░"


def _tilt_label(home_value: float, away_value: float, metric_name: str) -> str:
    diff = home_value - away_value
    if abs(diff) < 0.35:
        return f"{metric_name} equilibrado"
    return f"{metric_name} inclinado al local" if diff > 0 else f"{metric_name} inclinado al visitante"


def _ev(prob: float, odds: float) -> float:
    return (prob * odds) - 1.0


def _kelly_fraction(prob: float, odds: float) -> float:
    b = odds - 1.0
    if b <= 0:
        return 0.0
    q = 1.0 - prob
    return max(0.0, ((b * prob) - q) / b)


def _edge_label(edge: float) -> str:
    if edge >= 0.08:
        return "Muy alto"
    if edge >= 0.04:
        return "Alto"
    if edge >= 0.02:
        return "Moderado"
    return "Bajo"


def _sample_source_label(source: str) -> str:
    if source == "season_team_stats":
        return "Estadísticas de temporada"
    if source == "historical_matches":
        return "Histórico de partidos"
    return "Referencia base"


def _decision_signal(ev: float, kelly_q: float) -> tuple[str, str]:
    if ev <= 0 or kelly_q <= 0:
        return "🔴 No conviene", "EV <= 0 o stake sugerido nulo (No Bet)."
    if ev < 0.03:
        return "🟡 Marginal", "Ventaja pequeña; solo stake mínimo o esperar mejor cuota."
    if ev < 0.08:
        return "🟡 Conviene", "Ventaja razonable; stake moderado con disciplina."
    return "🟢 Conviene fuerte", "Ventaja alta; sigue gestión de banca (Kelly fraccional)."


def _stake_from_bankroll(bankroll: float, kelly_fraction: float) -> float:
    if bankroll <= 0 or kelly_fraction <= 0:
        return 0.0
    return min(bankroll, max(0.0, bankroll * kelly_fraction))


def build_match_insight(
    home_metrics: dict[str, float | None],
    away_metrics: dict[str, float | None],
    home_form: str,
    away_form: str,
    expected_home_goals: float,
    expected_away_goals: float,
    model_home: float,
    model_draw: float,
    model_away: float,
    likely_score: tuple[int, int, float],
    top_scorelines: list[tuple[int, int, float]],
    market_probs: dict[str, float],
    edge_max: float,
    odds_source: str | None,
    odds_home: float,
    odds_draw: float,
    odds_away: float,
    implied_home: float,
    implied_draw: float,
    implied_away: float,
    recent_home_n: int,
    recent_away_n: int,
    model_home_n: int,
    model_away_n: int,
    model_source: str,
    bankroll: float = 100.0,
) -> dict[str, Any]:
    expected_home_shots = _blend(home_metrics.get("shots_for"), away_metrics.get("shots_against"), 11.0)
    expected_away_shots = _blend(away_metrics.get("shots_for"), home_metrics.get("shots_against"), 9.5)
    expected_home_sot = _blend(home_metrics.get("shots_on_target_for"), away_metrics.get("shots_on_target_against"), 4.0)
    expected_away_sot = _blend(away_metrics.get("shots_on_target_for"), home_metrics.get("shots_on_target_against"), 3.2)
    expected_home_corners = _blend(home_metrics.get("corners_for"), away_metrics.get("corners_against"), 4.8)
    expected_away_corners = _blend(away_metrics.get("corners_for"), home_metrics.get("corners_against"), 4.1)
    expected_home_cards = _blend(home_metrics.get("cards_weighted"), away_metrics.get("cards_against_weighted"), 2.1)
    expected_away_cards = _blend(away_metrics.get("cards_weighted"), home_metrics.get("cards_against_weighted"), 2.2)

    total_goals = expected_home_goals + expected_away_goals
    total_corners = expected_home_corners + expected_away_corners
    total_cards = expected_home_cards + expected_away_cards
    likely_home_goals, likely_away_goals, score_prob = likely_score
    max_outcome_prob = max(model_home, model_draw, model_away)
    confidence_label, confidence_bar = _confidence_label(max_outcome_prob, edge_max)
    top_scores_text = " | ".join(f"{hg}-{ag} ({prob:.1%})" for hg, ag, prob in top_scorelines)

    edges = {
        "home": model_home - implied_home,
        "draw": model_draw - implied_draw,
        "away": model_away - implied_away,
    }
    probs = {"home": model_home, "draw": model_draw, "away": model_away}
    odds = {"home": odds_home, "draw": odds_draw, "away": odds_away}
    labels = {"home": "1 (Local)", "draw": "X (Empate)", "away": "2 (Visitante)"}
    best_pick = max(edges, key=edges.get)
    best_pick_edge = float(edges[best_pick])
    best_pick_ev = _ev(probs[best_pick], odds[best_pick])
    kelly_full = _kelly_fraction(probs[best_pick], odds[best_pick])
    kelly_quarter = kelly_full * 0.25

    if market_probs["over_2_5"] >= market_probs["under_2_5"]:
        goals_pick = "Over 2.5 goles"
        goals_pick_prob = market_probs["over_2_5"]
    else:
        goals_pick = "Under 2.5 goles"
        goals_pick_prob = market_probs["under_2_5"]

    if market_probs["btts_yes"] >= 0.5:
        btts_pick = "BTTS Sí"
        btts_pick_prob = market_probs["btts_yes"]
    else:
        btts_pick = "BTTS No"
        btts_pick_prob = market_probs["btts_no"]

    recommendation_1 = (
        f"1X2 Valor: {labels[best_pick]} | p={probs[best_pick]:.1%}, cuota={odds[best_pick]:.2f}, "
        f"edge={best_pick_edge:+.1%}, EV={best_pick_ev:+.2%}, Kelly 25%={kelly_quarter:.1%}"
    )
    recommendation_2 = f"Goles: {goals_pick} | prob. modelo {goals_pick_prob:.1%}"
    recommendation_3 = f"BTTS: {btts_pick} | prob. modelo {btts_pick_prob:.1%}"
    decision_signal, decision_reason = _decision_signal(best_pick_ev, kelly_quarter)
    stake_bankroll = _stake_from_bankroll(bankroll, kelly_quarter)

    return {
        "LikelyOutcome": outcome_label(model_home, model_draw, model_away),
        "LikelyScore": f"{likely_home_goals}-{likely_away_goals}",
        "LikelyScoreProb": score_prob,
        "TopScorelines": top_scores_text,
        "ExpectedGoalsHome": expected_home_goals,
        "ExpectedGoalsAway": expected_away_goals,
        "ExpectedGoalsTotal": total_goals,
        "ExpectedShotsHome": expected_home_shots,
        "ExpectedShotsAway": expected_away_shots,
        "ExpectedShotsOnTargetHome": expected_home_sot,
        "ExpectedShotsOnTargetAway": expected_away_sot,
        "ExpectedCornersHome": expected_home_corners,
        "ExpectedCornersAway": expected_away_corners,
        "ExpectedCornersTotal": total_corners,
        "ExpectedCardsHome": expected_home_cards,
        "ExpectedCardsAway": expected_away_cards,
        "ExpectedCardsTotal": total_cards,
        "HomeForm": home_form,
        "AwayForm": away_form,
        "GoalsProfile": total_goals_band(total_goals),
        "BTTSProb": market_probs["btts_yes"],
        "BTTSLean": _yes_no_label(market_probs["btts_yes"], "BTTS Sí", "BTTS No"),
        "Over15Prob": market_probs["over_1_5"],
        "Over25Prob": market_probs["over_2_5"],
        "Under25Prob": market_probs["under_2_5"],
        "Over35Prob": market_probs["over_3_5"],
        "GoalsLean": _yes_no_label(market_probs["over_2_5"], "Más de 2.5 goles", "Menos de 2.5 goles"),
        "HomeCleanSheetProb": market_probs["home_clean_sheet"],
        "AwayCleanSheetProb": market_probs["away_clean_sheet"],
        "CleanSheetLean": _yes_no_label(market_probs["home_clean_sheet"], "Local podría dejar arco en cero", "Visitante podría dejar arco en cero"),
        "ShotsTilt": _tilt_label(expected_home_shots, expected_away_shots, "Volumen de tiros"),
        "CornersTilt": _tilt_label(expected_home_corners, expected_away_corners, "Corners"),
        "CardsTilt": _tilt_label(expected_home_cards, expected_away_cards, "Tarjetas"),
        "ConfidenceLabel": confidence_label,
        "ConfidenceBar": confidence_bar,
        "OddsSource": odds_source or "N/D",
        "BestPick1X2": labels[best_pick],
        "BestPickProb": probs[best_pick],
        "BestPickOdds": odds[best_pick],
        "BestPickEdge": best_pick_edge,
        "BestPickEdgeLabel": _edge_label(best_pick_edge),
        "BestPickEV": best_pick_ev,
        "BestPickKellyQuarter": kelly_quarter,
        "BestPickStake": stake_bankroll,
        "DecisionSignal": decision_signal,
        "DecisionReason": decision_reason,
        "Suggestion1": recommendation_1,
        "Suggestion2": recommendation_2,
        "Suggestion3": recommendation_3,
        "MetricsLegend": "Edge = prob. modelo - prob. implícita | EV = (p*cuota)-1 | Kelly25 = 25% Kelly",
        "RecentSampleHome": recent_home_n,
        "RecentSampleAway": recent_away_n,
        "ModelSampleHome": model_home_n,
        "ModelSampleAway": model_away_n,
        "ModelSampleSource": _sample_source_label(model_source),
    }