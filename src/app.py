from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from src.analysis.edge_ranker import compute_edges
from src.analysis.implied_probs import normalized_implied_probabilities
from src.clients.matches_client import MatchesClient
from src.clients.odds_client import OddsClient
from src.config import get_settings
from src.models.poisson import PoissonModel
from src.storage.db import LocalDB

console = Console()


def _norm_team(name: str) -> str:
    return " ".join((name or "").lower().replace("-", " ").split())


def _select_result_label(home_goals: int | None, away_goals: int | None) -> str | None:
    if home_goals is None or away_goals is None:
        return None
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"


def _load_manual_results(path: str | None) -> dict[tuple[str, str, str], tuple[int, int]]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    manual: dict[tuple[str, str, str], tuple[int, int]] = {}
    for item in payload:
        key = (item["date"], _norm_team(item["home_team"]), _norm_team(item["away_team"]))
        manual[key] = (int(item["home_goals"]), int(item["away_goals"]))
    return manual


def _match_odds(match_row: dict[str, Any], odds_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    h = _norm_team(match_row["home_team"])
    a = _norm_team(match_row["away_team"])
    candidates = [
        o
        for o in odds_rows
        if _norm_team(o.get("home_team", "")) == h and _norm_team(o.get("away_team", "")) == a
    ]
    return candidates[0] if candidates else None


def build_daily_analysis(target_date: date) -> pd.DataFrame:
    settings = get_settings()
    db = LocalDB(settings.db_path)
    matches_client = MatchesClient(settings, db)
    odds_client = OddsClient(settings, db)

    matches = matches_client.get_matches(target_date)
    odds_rows = odds_client.get_odds(target_date)
    history = matches_client.get_historical_matches(end_date=target_date - timedelta(days=1), lookback_days=120)

    model = PoissonModel().fit(pd.DataFrame(history))

    rows: list[dict[str, Any]] = []
    for m in matches:
        odds = _match_odds(m, odds_rows)
        if not odds:
            continue

        implied = normalized_implied_probabilities(
            odds_home=float(odds["best_odds_home"]),
            odds_draw=float(odds["best_odds_draw"]),
            odds_away=float(odds["best_odds_away"]),
        )
        probs = model.predict_1x2(m["home_team"], m["away_team"])
        edges = compute_edges(probs, implied)

        rows.append(
            {
                "Date": target_date.isoformat(),
                "League": m.get("league"),
                "Match": f"{m.get('home_team')} vs {m.get('away_team')}",
                "HomeTeam": m.get("home_team"),
                "AwayTeam": m.get("away_team"),
                "StartTime": m.get("start_time"),
                "MatchId": m.get("match_id"),
                "Status": m.get("status"),
                "HomeGoals": m.get("home_goals"),
                "AwayGoals": m.get("away_goals"),
                "BestOddsHome": odds["best_odds_home"],
                "BestOddsDraw": odds["best_odds_draw"],
                "BestOddsAway": odds["best_odds_away"],
                "ImpliedHome": implied["home"],
                "ImpliedDraw": implied["draw"],
                "ImpliedAway": implied["away"],
                "ModelHome": probs["home"],
                "ModelDraw": probs["draw"],
                "ModelAway": probs["away"],
                "EdgeHome": edges["edge_home"],
                "EdgeDraw": edges["edge_draw"],
                "EdgeAway": edges["edge_away"],
                "EdgeMax": edges["edge_max"],
                "Score": edges["score"],
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df.sort_values(by=["Score", "EdgeMax"], ascending=False).reset_index(drop=True)


def print_analysis_table(df: pd.DataFrame, title: str) -> None:
    table = Table(title=title)
    cols = [
        "League",
        "Match",
        "StartTime",
        "BestOddsHome",
        "BestOddsDraw",
        "BestOddsAway",
        "ImpliedHome",
        "ImpliedDraw",
        "ImpliedAway",
        "ModelHome",
        "ModelDraw",
        "ModelAway",
        "EdgeMax",
        "Score",
    ]
    for c in cols:
        table.add_column(c, overflow="fold")

    for _, row in df.iterrows():
        table.add_row(
            str(row["League"]),
            str(row["Match"]),
            str(row["StartTime"]),
            f"{row['BestOddsHome']:.2f}",
            f"{row['BestOddsDraw']:.2f}",
            f"{row['BestOddsAway']:.2f}",
            f"{row['ImpliedHome']:.3f}",
            f"{row['ImpliedDraw']:.3f}",
            f"{row['ImpliedAway']:.3f}",
            f"{row['ModelHome']:.3f}",
            f"{row['ModelDraw']:.3f}",
            f"{row['ModelAway']:.3f}",
            f"{row['EdgeMax']:.3f}",
            f"{row['Score']:.2f}",
        )

    console.print(table)


def simulate_date(
    target_date: date,
    bankroll: float,
    stake: float,
    min_edge: float,
    manual_results_path: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    db = LocalDB(settings.db_path)
    df = build_daily_analysis(target_date)
    if df.empty:
        return {"rows": [], "bankroll": bankroll, "settled": 0, "pending": 0}

    manual = _load_manual_results(manual_results_path)
    rows_to_save = []
    settled = 0
    pending = 0
    bankroll_now = bankroll

    for _, r in df.iterrows():
        edge_map = {"home": r["EdgeHome"], "draw": r["EdgeDraw"], "away": r["EdgeAway"]}
        selection = max(edge_map, key=edge_map.get)
        edge = float(edge_map[selection])
        if edge < min_edge:
            continue

        odds_map = {"home": r["BestOddsHome"], "draw": r["BestOddsDraw"], "away": r["BestOddsAway"]}
        model_map = {"home": r["ModelHome"], "draw": r["ModelDraw"], "away": r["ModelAway"]}
        imp_map = {"home": r["ImpliedHome"], "draw": r["ImpliedDraw"], "away": r["ImpliedAway"]}

        actual = _select_result_label(
            int(r["HomeGoals"]) if pd.notna(r["HomeGoals"]) else None,
            int(r["AwayGoals"]) if pd.notna(r["AwayGoals"]) else None,
        )
        manual_key = (target_date.isoformat(), _norm_team(r["HomeTeam"]), _norm_team(r["AwayTeam"]))
        if actual is None and manual_key in manual:
            hg, ag = manual[manual_key]
            actual = _select_result_label(hg, ag)

        status = "PENDING"
        result = None
        payout = None
        if actual is not None:
            status = "SETTLED"
            result = "WIN" if selection == actual else "LOSS"
            payout = (stake * float(odds_map[selection])) if result == "WIN" else 0.0
            bankroll_now += payout - stake
            settled += 1
        else:
            pending += 1

        rows_to_save.append(
            {
                "sim_date": target_date.isoformat(),
                "league": r["League"],
                "match_id": r["MatchId"],
                "home_team": r["HomeTeam"],
                "away_team": r["AwayTeam"],
                "selection": selection,
                "odds": float(odds_map[selection]),
                "model_prob": float(model_map[selection]),
                "implied_prob": float(imp_map[selection]),
                "edge": edge,
                "stake": stake,
                "status": status,
                "result": result,
                "payout": payout,
            }
        )

    if persist and rows_to_save:
        db.save_positions(rows_to_save)

    return {
        "rows": rows_to_save,
        "bankroll": bankroll_now,
        "settled": settled,
        "pending": pending,
    }


def _print_simulation(rows: list[dict[str, Any]], final_bankroll: float) -> None:
    table = Table(title="Simulación (paper trading)")
    for c in ["Date", "Match", "Selection", "Odds", "Edge", "Status", "Result", "Payout"]:
        table.add_column(c)

    for r in rows:
        table.add_row(
            r["sim_date"],
            f"{r['home_team']} vs {r['away_team']}",
            r["selection"],
            f"{r['odds']:.2f}",
            f"{r['edge']:.3f}",
            r["status"],
            str(r.get("result") or "-"),
            "-" if r.get("payout") is None else f"{r['payout']:.2f}",
        )

    console.print(table)
    console.print(f"Bankroll final (solo posiciones liquidadas): [bold]{final_bankroll:.2f}[/bold]")


def _daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def run_today(args: argparse.Namespace) -> None:
    target = date.fromisoformat(args.date) if args.date else datetime.now().date()
    df = build_daily_analysis(target)
    if df.empty:
        console.print("No hay eventos con cuotas disponibles para esa fecha.")
        return
    print_analysis_table(df, title=f"Análisis diario {target.isoformat()}")


def run_simulate(args: argparse.Namespace) -> None:
    target = date.fromisoformat(args.date)
    summary = simulate_date(
        target_date=target,
        bankroll=args.bankroll,
        stake=args.stake,
        min_edge=args.min_edge,
        manual_results_path=args.manual_results,
        persist=True,
    )
    if not summary["rows"]:
        console.print("No hay eventos para simular en esa fecha.")
        return
    _print_simulation(summary["rows"], summary["bankroll"])


def run_backtest(args: argparse.Namespace) -> None:
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    bankroll = args.bankroll
    total_rows: list[dict[str, Any]] = []

    for d in _daterange(start, end):
        summary = simulate_date(
            target_date=d,
            bankroll=bankroll,
            stake=args.stake,
            min_edge=args.min_edge,
            manual_results_path=args.manual_results,
            persist=True,
        )
        bankroll = summary["bankroll"]
        total_rows.extend(summary["rows"])

    if not total_rows:
        console.print("Backtest sin posiciones. Revisa fechas, ligas o modo mock.")
        return

    settled_rows = [r for r in total_rows if r["status"] == "SETTLED"]
    wins = sum(1 for r in settled_rows if r.get("result") == "WIN")
    total_settled = len(settled_rows)
    roi = (
        (sum((r.get("payout") or 0.0) - r["stake"] for r in settled_rows) / sum(r["stake"] for r in settled_rows))
        if settled_rows
        else 0.0
    )

    console.print(f"Backtest {start} -> {end}")
    console.print(f"Posiciones: {len(total_rows)} | Liquidadas: {total_settled} | Aciertos: {wins}")
    console.print(f"ROI simulado: {roi:.2%} | Bankroll final: {bankroll:.2f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analizador local de cuotas y simulación educativa")
    sub = parser.add_subparsers(dest="command", required=True)

    p_today = sub.add_parser("today", help="Lista partidos del día con ranking de interés")
    p_today.add_argument("--date", type=str, default=None, help="Fecha YYYY-MM-DD (opcional)")
    p_today.set_defaults(func=run_today)

    p_sim = sub.add_parser("simulate", help="Ejecuta simulación paper trading por fecha")
    p_sim.add_argument("--date", type=str, required=True, help="Fecha YYYY-MM-DD")
    p_sim.add_argument("--bankroll", type=float, default=100.0)
    p_sim.add_argument("--stake", type=float, default=1.0)
    p_sim.add_argument("--min-edge", type=float, default=0.02)
    p_sim.add_argument("--manual-results", type=str, default=None, help="JSON opcional de resultados manuales")
    p_sim.set_defaults(func=run_simulate)

    p_bt = sub.add_parser("backtest", help="Backtest simple en rango de fechas")
    p_bt.add_argument("--start", type=str, required=True, help="Fecha inicio YYYY-MM-DD")
    p_bt.add_argument("--end", type=str, required=True, help="Fecha fin YYYY-MM-DD")
    p_bt.add_argument("--bankroll", type=float, default=100.0)
    p_bt.add_argument("--stake", type=float, default=1.0)
    p_bt.add_argument("--min-edge", type=float, default=0.02)
    p_bt.add_argument("--manual-results", type=str, default=None, help="JSON opcional de resultados manuales")
    p_bt.set_defaults(func=run_backtest)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
