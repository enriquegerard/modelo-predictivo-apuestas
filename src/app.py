from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.analysis.bankroll_calculator import DEFAULT_SCENARIOS, compound_growth, required_monthly_return, required_roi_per_bet
from src.analysis.edge_ranker import compute_edges
from src.analysis.implied_probs import normalized_implied_probabilities
from src.analysis.match_insights import build_form_string, build_match_insight, summarize_recent_team_metrics
from src.clients.matches_client import MatchesClient
from src.clients.odds_client import OddsClient
from src.config import get_settings
from src.export.html_report import generate_html_report
from src.models.poisson import PoissonModel
from src.storage.db import LocalDB

console = Console()


def _norm_team(name: str) -> str:
    return " ".join((name or "").lower().replace("-", " ").split())


def _print_mock_notice() -> None:
    settings = get_settings()
    if settings.mock_mode:
        console.print(
            "[bold yellow]Aviso:[/bold yellow] Estás usando datos mock/locales de ejemplo. "
            "No son partidos reales en vivo."
        )
        return

    if not settings.football_data_api_key or not settings.the_odds_api_key:
        console.print(
            "[bold cyan]Fuente activa:[/bold cyan] datos reales públicos de ESPN para partidos y cuotas visibles en scoreboard."
        )


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


def build_daily_analysis(target_date: date, bankroll: float = 100.0) -> pd.DataFrame:
    settings = get_settings()
    db = LocalDB(settings.db_path)
    matches_client = MatchesClient(settings, db)
    odds_client = OddsClient(settings, db)

    matches = matches_client.get_matches(target_date)
    odds_rows = odds_client.get_odds(target_date)
    team_stats = matches_client.get_team_stats()

    if team_stats:
        model = PoissonModel().fit_from_team_stats(pd.DataFrame(team_stats))
    else:
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
        expected_home_goals, expected_away_goals = model.expected_goals(m["home_team"], m["away_team"])
        likely_score = model.most_likely_score(m["home_team"], m["away_team"])
        top_scorelines = model.top_scorelines(m["home_team"], m["away_team"], top_n=3)
        market_probs = model.derived_market_probs(m["home_team"], m["away_team"])
        recent_stats = matches_client.get_recent_team_match_stats(m["match_id"], m.get("league_code", ""))
        home_recent_rows = recent_stats.get(m["home_team"], [])
        away_recent_rows = recent_stats.get(m["away_team"], [])
        home_metrics = summarize_recent_team_metrics(home_recent_rows)
        away_metrics = summarize_recent_team_metrics(away_recent_rows)
        edges = compute_edges(probs, implied)
        sample_sizes = model.get_team_sample_sizes(m["home_team"], m["away_team"])
        insight = build_match_insight(
            home_metrics=home_metrics,
            away_metrics=away_metrics,
            home_form=build_form_string(home_recent_rows),
            away_form=build_form_string(away_recent_rows),
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
            model_home=probs["home"],
            model_draw=probs["draw"],
            model_away=probs["away"],
            likely_score=likely_score,
            top_scorelines=top_scorelines,
            market_probs=market_probs,
            edge_max=edges["edge_max"],
            odds_source=odds.get("source"),
            odds_home=float(odds["best_odds_home"]),
            odds_draw=float(odds["best_odds_draw"]),
            odds_away=float(odds["best_odds_away"]),
            implied_home=implied["home"],
            implied_draw=implied["draw"],
            implied_away=implied["away"],
            recent_home_n=len(home_recent_rows),
            recent_away_n=len(away_recent_rows),
            model_home_n=int(sample_sizes.get("home_model_sample") or 0),
            model_away_n=int(sample_sizes.get("away_model_sample") or 0),
            model_source=str(sample_sizes.get("source") or "default"),
            bankroll=bankroll,
        )

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
                "OddsSource": odds.get("source", "N/D"),
                "BestOddsHome": odds["best_odds_home"],
                "BestOddsDraw": odds["best_odds_draw"],
                "BestOddsAway": odds["best_odds_away"],
                "ImpliedHome": implied["home"],
                "ImpliedDraw": implied["draw"],
                "ImpliedAway": implied["away"],
                "ModelHome": probs["home"],
                "ModelDraw": probs["draw"],
                "ModelAway": probs["away"],
                **insight,
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
        "OddsSource",
        "BestOddsHome",
        "BestOddsDraw",
        "BestOddsAway",
        "ImpliedHome",
        "ImpliedDraw",
        "ImpliedAway",
        "ModelHome",
        "ModelDraw",
        "ModelAway",
        "LikelyOutcome",
        "LikelyScore",
        "BTTSLean",
        "GoalsLean",
        "ConfidenceLabel",
        "DecisionSignal",
        "BestPick1X2",
        "BestPickEV",
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
            str(row["OddsSource"]),
            f"{row['BestOddsHome']:.2f}",
            f"{row['BestOddsDraw']:.2f}",
            f"{row['BestOddsAway']:.2f}",
            f"{row['ImpliedHome']:.3f}",
            f"{row['ImpliedDraw']:.3f}",
            f"{row['ImpliedAway']:.3f}",
            f"{row['ModelHome']:.3f}",
            f"{row['ModelDraw']:.3f}",
            f"{row['ModelAway']:.3f}",
            str(row["LikelyOutcome"]),
            str(row["LikelyScore"]),
            str(row["BTTSLean"]),
            str(row["GoalsLean"]),
            str(row["ConfidenceLabel"]),
            str(row["DecisionSignal"]),
            str(row["BestPick1X2"]),
            f"{row['BestPickEV']:+.2%}",
            f"{row['EdgeMax']:.3f}",
            f"{row['Score']:.2f}",
        )

    console.print(table)


def print_match_explanations(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        content = (
            f"[bold]{row['Match']}[/bold]\n"
            f"Fuente de cuotas: {row['OddsSource']} | Confianza analítica: {row['ConfidenceLabel']} {row['ConfidenceBar']}\n"
            f"Muestras usadas → reciente: local {int(row['RecentSampleHome'])} / visita {int(row['RecentSampleAway'])} partidos | modelo: local {int(row['ModelSampleHome'])} / visita {int(row['ModelSampleAway'])} ({row['ModelSampleSource']})\n"
            f"Guía rápida: {row['MetricsLegend']}\n"
            f"Semáforo de decisión: [bold]{row['DecisionSignal']}[/bold] → {row['DecisionReason']}\n"
            f"Stake sugerido con tu banca: [bold green]${row['BestPickStake']:.2f}[/bold green]\n"
            f"Forma reciente: local {row['HomeForm']} | visitante {row['AwayForm']}\n"
            f"Resultado más probable: [cyan]{row['LikelyOutcome']}[/cyan]\n"
            f"Marcador más probable: [cyan]{row['LikelyScore']}[/cyan] "
            f"(prob. puntual aprox. {row['LikelyScoreProb']:.1%})\n"
            f"Top 3 marcadores: {row['TopScorelines']}\n"
            f"Goles esperados: {row['ExpectedGoalsHome']:.2f} vs {row['ExpectedGoalsAway']:.2f} "
            f"| Total: {row['ExpectedGoalsTotal']:.2f} → {row['GoalsProfile']}\n"
            f"BTTS: {row['BTTSLean']} ({row['BTTSProb']:.1%}) | {row['GoalsLean']} ({row['Over25Prob']:.1%} over 2.5, {row['Under25Prob']:.1%} under 2.5)\n"
            f"Más de 1.5: {row['Over15Prob']:.1%} | Más de 3.5: {row['Over35Prob']:.1%}\n"
            f"Arco en cero: local {row['HomeCleanSheetProb']:.1%} | visitante {row['AwayCleanSheetProb']:.1%} | Lectura: {row['CleanSheetLean']}\n"
            f"Tiros estimados: {row['ExpectedShotsHome']:.1f} vs {row['ExpectedShotsAway']:.1f} | a puerta {row['ExpectedShotsOnTargetHome']:.1f} vs {row['ExpectedShotsOnTargetAway']:.1f}\n"
            f"Lectura tiros: {row['ShotsTilt']}\n"
            f"Corners estimados: {row['ExpectedCornersHome']:.1f} vs {row['ExpectedCornersAway']:.1f} | total {row['ExpectedCornersTotal']:.1f}\n"
            f"Lectura corners: {row['CornersTilt']}\n"
            f"Tarjetas estimadas: {row['ExpectedCardsHome']:.1f} vs {row['ExpectedCardsAway']:.1f} | total {row['ExpectedCardsTotal']:.1f}\n"
            f"Lectura tarjetas: {row['CardsTilt']}\n"
            f"Probabilidades del modelo 1X2: local {row['ModelHome']:.1%}, empate {row['ModelDraw']:.1%}, visitante {row['ModelAway']:.1%}\n"
            f"[bold green]Top 3 sugerencias analíticas[/bold green]\n"
            f"1) {row['Suggestion1']}\n"
            f"2) {row['Suggestion2']}\n"
            f"3) {row['Suggestion3']}"
        )
        console.print(Panel(content, title=str(row["League"]), expand=False))


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
    _print_mock_notice()
    target = date.fromisoformat(args.date) if args.date else datetime.now().date()
    bankroll = float(getattr(args, "bankroll", 2500.0))
    target_profit = float(getattr(args, "target_profit", 500.0))
    df = build_daily_analysis(target, bankroll=bankroll)
    if df.empty:
        console.print("No hay eventos con cuotas disponibles para esa fecha.")
        return
    print_analysis_table(df, title=f"Análisis diario {target.isoformat()}")
    print_match_explanations(df)
    if getattr(args, "html", False):
        out = generate_html_report(df, target, bankroll=bankroll, target_profit=target_profit)
        console.print(f"[bold green]✔ Reporte HTML generado:[/bold green] {out}")


def run_simulate(args: argparse.Namespace) -> None:
    _print_mock_notice()
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
    _print_mock_notice()
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


def run_calculator(args: argparse.Namespace) -> None:
    bankroll = float(args.bankroll)
    target_profit = float(args.target_profit)
    required_monthly = required_monthly_return(bankroll, target_profit)
    signal_filter = args.signal_filter

    if args.last_days and not (args.from_date and args.to_date):
        range_end = date.fromisoformat(args.end_date) if args.end_date else (datetime.now().date() - timedelta(days=1))
        range_start = range_end - timedelta(days=max(args.last_days - 1, 0))
        args.from_date = range_start.isoformat()
        args.to_date = range_end.isoformat()

    summary = Panel(
        (
            f"Bankroll inicial: [bold]${bankroll:,.2f}[/bold]\n"
            f"Meta mensual: [bold]${target_profit:,.2f}[/bold]\n"
            f"Retorno mensual requerido sobre banca: [bold yellow]{required_monthly:.1%}[/bold yellow]\n"
            f"Lectura: para pasar de ${bankroll:,.0f} a ${bankroll + target_profit:,.0f} en 1 mes necesitarías una rentabilidad muy alta si la banca es chica."
        ),
        title="Calculadora de meta mensual",
        expand=False,
    )
    console.print(summary)

    scenario_table = Table(title="Escenarios mensuales estimados")
    for col in ["Perfil", "Stake medio", "Picks/día", "ROI por apuesta", "Retorno mensual", "Ganancia/mes"]:
        scenario_table.add_column(col)

    for scenario in DEFAULT_SCENARIOS:
        monthly_return = scenario.monthly_return_pct
        profit = scenario.monthly_profit(bankroll)
        scenario_table.add_row(
            scenario.name,
            f"{scenario.stake_pct:.1%}",
            str(scenario.bets_per_day),
            f"{scenario.roi_per_bet:.1%}",
            f"{monthly_return:.1%}",
            f"${profit:,.2f}",
        )

    console.print(scenario_table)

    req_table = Table(title="Qué necesitarías para llegar a la meta")
    for col in ["Stake medio", "Picks/día", "ROI por apuesta requerido"]:
        req_table.add_column(col)

    requirement_options = [
        (0.03, 3),
        (0.04, 4),
        (0.05, 4),
        (0.08, 5),
    ]
    for stake_pct, bets_per_day in requirement_options:
        roi_needed = required_roi_per_bet(
            bankroll=bankroll,
            target_profit=target_profit,
            stake_pct=stake_pct,
            bets_per_day=bets_per_day,
        )
        req_table.add_row(f"{stake_pct:.1%}", str(bets_per_day), f"{roi_needed:.1%}")

    console.print(req_table)

    projection = compound_growth(bankroll, monthly_return_pct=0.20 if bankroll > 0 else 0.0, months=args.months)
    growth_table = Table(title=f"Proyección compuesta ejemplo ({args.months} meses al 20% mensual)")
    for col in ["Mes", "Banca inicial", "Ganancia", "Banca final"]:
        growth_table.add_column(col)
    for row in projection:
        growth_table.add_row(
            str(int(row["month"])),
            f"${row['start_bankroll']:,.2f}",
            f"${row['profit']:,.2f}",
            f"${row['end_bankroll']:,.2f}",
        )
    console.print(growth_table)

    if args.based_on_date:
        based_date = date.fromisoformat(args.based_on_date)
        df = build_daily_analysis(based_date)
        if df.empty:
            console.print(f"[bold red]Sin partidos para calcular en {based_date}.[/bold red]")
        else:
            eligible = df[(df["BestPickEV"] > 0) & (df["BestPickKellyQuarter"] > 0)].copy()
            if eligible.empty:
                console.print(f"[bold yellow]No hay picks positivos en {based_date} para proyectar.[/bold yellow]")
            else:
                eligible["StakePct"] = eligible["BestPickKellyQuarter"].astype(float)
                eligible["StakeUSD"] = bankroll * eligible["StakePct"]
                eligible["ExpectedProfitUSD"] = eligible["StakeUSD"] * eligible["BestPickEV"].astype(float)

                picks_table = Table(title=f"Picks reales del día usados para proyección ({based_date})")
                for col in ["Partido", "Señal", "Pick", "EV", "Stake %", "Stake $", "Exp. $"]:
                    picks_table.add_column(col)

                for _, row in eligible.iterrows():
                    picks_table.add_row(
                        str(row["Match"]),
                        str(row["DecisionSignal"]),
                        str(row["BestPick1X2"]),
                        f"{float(row['BestPickEV']):+.2%}",
                        f"{float(row['StakePct']):.2%}",
                        f"${float(row['StakeUSD']):,.2f}",
                        f"${float(row['ExpectedProfitUSD']):,.2f}",
                    )
                console.print(picks_table)

                total_stake_day = float(eligible["StakeUSD"].sum())
                total_expected_day = float(eligible["ExpectedProfitUSD"].sum())
                monthly_expected = total_expected_day * 30
                monthly_return_real = (monthly_expected / bankroll) if bankroll > 0 else 0.0
                avg_ev = float(eligible["BestPickEV"].mean())

                real_panel = Panel(
                    (
                        f"Fecha base: [bold]{based_date}[/bold]\n"
                        f"Picks positivos detectados: [bold]{len(eligible)}[/bold]\n"
                        f"Stake total diario estimado: [bold]${total_stake_day:,.2f}[/bold]\n"
                        f"Ganancia esperada diaria: [bold green]${total_expected_day:,.2f}[/bold green]\n"
                        f"Ganancia esperada mensual si repitieras un día así: [bold green]${monthly_expected:,.2f}[/bold green]\n"
                        f"Retorno mensual implícito: [bold yellow]{monthly_return_real:.1%}[/bold yellow]\n"
                        f"EV promedio de los picks positivos: [bold]{avg_ev:+.2%}[/bold]"
                    ),
                    title="Proyección basada en picks reales del día",
                    expand=False,
                )
                console.print(real_panel)

                if monthly_expected >= target_profit:
                    console.print("[bold green]Según ese día puntual, la meta mensual sí quedaría al alcance.[/bold green]")
                else:
                    console.print("[bold yellow]Según ese día puntual, la meta mensual todavía no alcanza.[/bold yellow]")

    if args.from_date and args.to_date:
        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date)
        per_day_rows: list[dict[str, Any]] = []

        for d in _daterange(start, end):
            df = build_daily_analysis(d)
            if df.empty:
                per_day_rows.append(
                    {
                        "date": d.isoformat(),
                        "picks": 0,
                        "stake": 0.0,
                        "expected_profit": 0.0,
                        "avg_ev": 0.0,
                    }
                )
                continue

            eligible = df[(df["BestPickEV"] > 0) & (df["BestPickKellyQuarter"] > 0)].copy()
            if signal_filter == "green":
                eligible = eligible[eligible["DecisionSignal"].astype(str).str.contains("🟢", na=False)].copy()
            elif signal_filter == "green-yellow":
                eligible = eligible[
                    eligible["DecisionSignal"].astype(str).str.contains("🟢|🟡", na=False, regex=True)
                ].copy()
            if eligible.empty:
                per_day_rows.append(
                    {
                        "date": d.isoformat(),
                        "picks": 0,
                        "stake": 0.0,
                        "expected_profit": 0.0,
                        "avg_ev": 0.0,
                    }
                )
                continue

            eligible["StakePct"] = eligible["BestPickKellyQuarter"].astype(float)
            eligible["StakeUSD"] = bankroll * eligible["StakePct"]
            eligible["ExpectedProfitUSD"] = eligible["StakeUSD"] * eligible["BestPickEV"].astype(float)

            per_day_rows.append(
                {
                    "date": d.isoformat(),
                    "picks": int(len(eligible)),
                    "stake": float(eligible["StakeUSD"].sum()),
                    "expected_profit": float(eligible["ExpectedProfitUSD"].sum()),
                    "avg_ev": float(eligible["BestPickEV"].mean()),
                }
            )

        if per_day_rows:
            range_table = Table(title=f"Proyección por rango usando picks reales ({start} → {end})")
            for col in ["Fecha", "Picks +EV", "Stake total $", "Ganancia esperada $", "EV prom."]:
                range_table.add_column(col)

            for row in per_day_rows:
                range_table.add_row(
                    row["date"],
                    str(row["picks"]),
                    f"${row['stake']:,.2f}",
                    f"${row['expected_profit']:,.2f}",
                    "-" if row["picks"] == 0 else f"{row['avg_ev']:+.2%}",
                )
            console.print(range_table)

            total_days = len(per_day_rows)
            active_days = sum(1 for row in per_day_rows if row["picks"] > 0)
            total_expected = sum(row["expected_profit"] for row in per_day_rows)
            total_stake = sum(row["stake"] for row in per_day_rows)
            avg_expected_day = total_expected / total_days if total_days else 0.0
            avg_stake_day = total_stake / total_days if total_days else 0.0
            avg_active_stake_day = (total_stake / active_days) if active_days else 0.0
            monthly_projection = avg_expected_day * 30
            monthly_return_projection = (monthly_projection / bankroll) if bankroll > 0 else 0.0
            avg_picks_day = (sum(row["picks"] for row in per_day_rows) / total_days) if total_days else 0.0
            avg_picks_active_day = (sum(row["picks"] for row in per_day_rows) / active_days) if active_days else 0.0
            best_day = max(per_day_rows, key=lambda row: row["expected_profit"])
            worst_day = min(per_day_rows, key=lambda row: row["expected_profit"])

            range_panel = Panel(
                (
                    f"Rango analizado: [bold]{start} → {end}[/bold]\n"
                    f"Filtro aplicado: [bold]{signal_filter}[/bold]\n"
                    f"Días analizados: [bold]{total_days}[/bold] | Días con picks positivos: [bold]{active_days}[/bold]\n"
                    f"Promedio picks/día: [bold]{avg_picks_day:.2f}[/bold] | Promedio picks en días activos: [bold]{avg_picks_active_day:.2f}[/bold]\n"
                    f"Stake total estimado del rango: [bold]${total_stake:,.2f}[/bold]\n"
                    f"Stake medio por día: [bold]${avg_stake_day:,.2f}[/bold] | Stake medio en días activos: [bold]${avg_active_stake_day:,.2f}[/bold]\n"
                    f"Ganancia esperada acumulada del rango: [bold green]${total_expected:,.2f}[/bold green]\n"
                    f"Promedio diario esperado: [bold green]${avg_expected_day:,.2f}[/bold green]\n"
                    f"Proyección mensual usando promedio del rango: [bold green]${monthly_projection:,.2f}[/bold green]\n"
                    f"Retorno mensual implícito: [bold yellow]{monthly_return_projection:.1%}[/bold yellow]\n"
                    f"Mejor día del rango: [bold]{best_day['date']}[/bold] (${best_day['expected_profit']:,.2f}) | Peor día: [bold]{worst_day['date']}[/bold] (${worst_day['expected_profit']:,.2f})"
                ),
                title="Resumen de proyección por rango",
                expand=False,
            )
            console.print(range_panel)

            if monthly_projection >= target_profit:
                console.print("[bold green]Según el promedio del rango, la meta mensual sí quedaría al alcance.[/bold green]")
            else:
                console.print("[bold yellow]Según el promedio del rango, la meta mensual todavía no alcanza.[/bold yellow]")

    if bankroll == 1000 and target_profit >= 1000:
        console.print(
            "[bold yellow]Lectura directa:[/bold yellow] con $1000 buscar $1000/mes implica [bold]100% mensual[/bold]. "
            "Es posible en papel, pero no es una expectativa estable ni probable a largo plazo."
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analizador local de cuotas y simulación educativa")
    sub = parser.add_subparsers(dest="command", required=True)

    p_today = sub.add_parser("today", help="Lista partidos del día con ranking de interés")
    p_today.add_argument("--date", type=str, default=None, help="Fecha YYYY-MM-DD (opcional)")
    p_today.add_argument("--html", action="store_true", default=False, help="Exportar reporte visual HTML al escritorio")
    p_today.add_argument("--bankroll", type=float, default=2500.0, help="Tu banca actual en USD (default: 2500)")
    p_today.add_argument("--target-profit", dest="target_profit", type=float, default=500.0, help="Meta de ganancia mensual en USD (default: 500)")
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

    p_calc = sub.add_parser("calculator", help="Calcula metas de bankroll y retorno mensual requerido")
    p_calc.add_argument("--bankroll", type=float, required=True, help="Bankroll inicial")
    p_calc.add_argument("--target-profit", type=float, required=True, help="Meta de ganancia mensual")
    p_calc.add_argument("--months", type=int, default=6, help="Meses para proyección compuesta de ejemplo")
    p_calc.add_argument("--based-on-date", type=str, default=None, help="Fecha YYYY-MM-DD para proyectar usando picks reales del día")
    p_calc.add_argument("--from", dest="from_date", type=str, default=None, help="Fecha inicio YYYY-MM-DD para proyectar con promedio de rango")
    p_calc.add_argument("--to", dest="to_date", type=str, default=None, help="Fecha fin YYYY-MM-DD para proyectar con promedio de rango")
    p_calc.add_argument("--last-days", type=int, default=None, help="Analiza automáticamente los últimos N días")
    p_calc.add_argument("--end-date", type=str, default=None, help="Fecha final YYYY-MM-DD para usar con --last-days; por defecto ayer")
    p_calc.add_argument(
        "--signal-filter",
        type=str,
        default="green-yellow",
        choices=["all-positive", "green-yellow", "green"],
        help="Filtra picks para la proyección: todos los +EV, verdes+amarillos, o solo verdes",
    )
    p_calc.set_defaults(func=run_calculator)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
