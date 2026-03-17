from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _bar_color(prob: float) -> str:
    if prob >= 0.60:
        return "#22c55e"   # green
    if prob >= 0.40:
        return "#f59e0b"   # amber
    return "#ef4444"       # red


def _edge_color(edge: float) -> str:
    if edge >= 0.08:
        return "#22c55e"
    if edge >= 0.04:
        return "#f59e0b"
    return "#94a3b8"


def _conf_color(label: str) -> str:
    return {"Alta": "#22c55e", "Media": "#f59e0b", "Baja": "#ef4444"}.get(label, "#94a3b8")


def _form_badge(char: str) -> str:
    colors = {"W": ("#22c55e", "#052e16"), "D": ("#f59e0b", "#1c1400"), "L": ("#ef4444", "#2d0707")}
    bg, fg = colors.get(char, ("#475569", "#e2e8f0"))
    return (
        f'<span style="background:{bg};color:{fg};font-weight:700;'
        f'border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
        f'width:22px;height:22px;font-size:11px;margin:1px;">{char}</span>'
    )


def _form_html(form_str: str) -> str:
    if not form_str or form_str == "Sin datos":
        return '<span style="color:#64748b;font-size:12px;">Sin datos</span>'
    return "".join(_form_badge(c) for c in form_str)


def _prob_bar(label: str, value: float, color: str | None = None) -> str:
    c = color or _bar_color(value)
    pct = value * 100
    return f"""
        <div style="margin:4px 0;">
          <div style="display:flex;justify-content:space-between;font-size:12px;color:#cbd5e1;margin-bottom:2px;">
            <span>{label}</span><span style="font-weight:600;color:{c};">{pct:.1f}%</span>
          </div>
          <div style="background:#1e293b;border-radius:4px;height:7px;overflow:hidden;">
            <div style="width:{min(pct,100):.1f}%;height:100%;background:{c};border-radius:4px;
                        transition:width 0.4s;"></div>
          </div>
        </div>"""


def _three_way_bar(home: float, draw: float, away: float) -> str:
    """Stacked 3-way bar."""
    hp = home * 100
    dp = draw * 100
    ap = away * 100
    return f"""
        <div style="border-radius:6px;overflow:hidden;height:12px;display:flex;margin:6px 0 2px;">
          <div style="width:{hp:.1f}%;background:#3b82f6;" title="Local {hp:.1f}%"></div>
          <div style="width:{dp:.1f}%;background:#6366f1;" title="Empate {dp:.1f}%"></div>
          <div style="width:{ap:.1f}%;background:#f97316;" title="Visitante {ap:.1f}%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:11px;color:#94a3b8;margin-bottom:4px;">
          <span style="color:#3b82f6;">🏠 {hp:.1f}%</span>
          <span style="color:#6366f1;">🤝 {dp:.1f}%</span>
          <span style="color:#f97316;">✈️ {ap:.1f}%</span>
        </div>"""


def _stat_row(icon: str, label: str, home_val: str, away_val: str) -> str:
    return f"""
        <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
                    padding:5px 0;border-bottom:1px solid #1e293b;">
          <span style="font-size:13px;color:#e2e8f0;text-align:right;padding-right:10px;">{home_val}</span>
          <span style="font-size:11px;color:#64748b;text-align:center;min-width:110px;">{icon} {label}</span>
          <span style="font-size:13px;color:#e2e8f0;text-align:left;padding-left:10px;">{away_val}</span>
        </div>"""


def _tag(text: str, color: str = "#3b82f6") -> str:
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'border-radius:12px;padding:2px 10px;font-size:11px;font-weight:600;">{text}</span>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Match Card
# ──────────────────────────────────────────────────────────────────────────────

def _match_card(row: dict[str, Any], bankroll: float = 2500.0) -> str:
    home = row.get("HomeTeam", "")
    away = row.get("AwayTeam", "")
    league = row.get("League", "")
    start = row.get("StartTime", "")
    status = str(row.get("Status", ""))

    # Odds
    odds_h = float(row.get("BestOddsHome", 0))
    odds_d = float(row.get("BestOddsDraw", 0))
    odds_a = float(row.get("BestOddsAway", 0))

    # Model probs
    mh = float(row.get("ModelHome", 0))
    md_ = float(row.get("ModelDraw", 0))
    ma = float(row.get("ModelAway", 0))

    # Implied
    ih = float(row.get("ImpliedHome", 0))
    id_ = float(row.get("ImpliedDraw", 0))
    ia = float(row.get("ImpliedAway", 0))

    # Edges
    edge_h = float(row.get("EdgeHome", 0))
    edge_d = float(row.get("EdgeDraw", 0))
    edge_a = float(row.get("EdgeAway", 0))
    edge_max = float(row.get("EdgeMax", 0))

    # Insight fields
    conf_label = str(row.get("ConfidenceLabel", ""))
    conf_color = _conf_color(conf_label)
    home_form = str(row.get("HomeForm", ""))
    away_form = str(row.get("AwayForm", ""))
    likely_score = str(row.get("LikelyScore", ""))
    likely_outcome = str(row.get("LikelyOutcome", ""))
    likely_prob = float(row.get("LikelyScoreProb", 0))
    top_lines = str(row.get("TopScorelines", ""))
    goals_home = float(row.get("ExpectedGoalsHome", 0))
    goals_away = float(row.get("ExpectedGoalsAway", 0))
    goals_total = float(row.get("ExpectedGoalsTotal", 0))
    goals_profile = str(row.get("GoalsProfile", ""))

    btts_prob = float(row.get("BTTSProb", 0))
    btts_lean = str(row.get("BTTSLean", ""))
    over15 = float(row.get("Over15Prob", 0))
    over25 = float(row.get("Over25Prob", 0))
    over35 = float(row.get("Over35Prob", 0))
    under25 = float(row.get("Under25Prob", 0))

    shots_h = float(row.get("ExpectedShotsHome", 0))
    shots_a = float(row.get("ExpectedShotsAway", 0))
    sot_h = float(row.get("ExpectedShotsOnTargetHome", 0))
    sot_a = float(row.get("ExpectedShotsOnTargetAway", 0))
    corners_h = float(row.get("ExpectedCornersHome", 0))
    corners_a = float(row.get("ExpectedCornersAway", 0))
    cards_h = float(row.get("ExpectedCardsHome", 0))
    cards_a = float(row.get("ExpectedCardsAway", 0))

    home_cs = float(row.get("HomeCleanSheetProb", 0))
    away_cs = float(row.get("AwayCleanSheetProb", 0))

    odds_source = str(row.get("OddsSource", "N/D"))
    score = float(row.get("Score", 0))

    # ── Status badge ──
    status_map = {
        "STATUS_SCHEDULED": ("Programado", "#3b82f6"),
        "STATUS_IN_PROGRESS": ("En curso 🔴", "#22c55e"),
        "STATUS_FINAL": ("Finalizado", "#64748b"),
        "pre": ("Programado", "#3b82f6"),
        "in": ("En curso 🔴", "#22c55e"),
        "post": ("Finalizado", "#64748b"),
    }
    status_text, status_color = status_map.get(status, (status, "#94a3b8"))

    # ── Best selection highlight ──
    edge_map = {"home": edge_h, "draw": edge_d, "away": edge_a}
    best_sel = max(edge_map, key=edge_map.get)
    sel_label = {"home": f"Local ({home})", "draw": "Empate", "away": f"Visitante ({away})"}[best_sel]
    best_edge = edge_map[best_sel]
    best_odds = {"home": odds_h, "draw": odds_d, "away": odds_a}[best_sel]
    best_pick_ev = float(row.get("BestPickEV", 0.0))
    best_pick_kelly = float(row.get("BestPickKellyQuarter", 0.0))
    best_pick_stake = float(row.get("BestPickStake", 0.0))
    decision_signal = str(row.get("DecisionSignal", ""))
    decision_reason = str(row.get("DecisionReason", ""))
    suggestion_1 = str(row.get("Suggestion1", ""))
    suggestion_2 = str(row.get("Suggestion2", ""))
    suggestion_3 = str(row.get("Suggestion3", ""))
    metrics_legend = str(row.get("MetricsLegend", ""))
    recent_home_n = int(row.get("RecentSampleHome", 0) or 0)
    recent_away_n = int(row.get("RecentSampleAway", 0) or 0)
    model_home_n = int(row.get("ModelSampleHome", 0) or 0)
    model_away_n = int(row.get("ModelSampleAway", 0) or 0)
    model_sample_source = str(row.get("ModelSampleSource", "N/D"))

    return f"""
    <div style="background:#0f172a;border-radius:16px;border:1px solid #1e293b;
                margin-bottom:24px;overflow:hidden;box-shadow:0 4px 24px #00000066;">

      <!-- Header -->
      <div style="background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
                  padding:18px 24px;border-bottom:1px solid #1e293b;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
          <div>
            <div style="font-size:11px;color:#64748b;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">
              {league} &nbsp;·&nbsp; {start} &nbsp;·&nbsp;
              <span style="color:{status_color};">{status_text}</span>
            </div>
            <div style="font-size:22px;font-weight:800;color:#f1f5f9;letter-spacing:-0.5px;">
              {home}
              <span style="color:#334155;font-size:16px;margin:0 10px;">vs</span>
              {away}
            </div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
            <span style="background:{conf_color}22;color:{conf_color};border:1px solid {conf_color}55;
                         border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;">
              Confianza: {conf_label}
            </span>
            <span style="color:#64748b;font-size:11px;">Fuente: {odds_source} &nbsp;|&nbsp; Score: {score:.2f}</span>
          </div>
        </div>
      </div>

      <!-- Body grid -->
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;padding:0;">

        <!-- Col 1: Probs + Odds -->
        <div style="padding:20px;border-right:1px solid #1e293b;">
          <div style="font-size:11px;color:#64748b;letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;">
            📊 Probabilidades
          </div>

          {_three_way_bar(mh, md_, ma)}

          <table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:10px;">
            <tr style="color:#475569;">
              <th style="text-align:left;padding:3px 0;"></th>
              <th style="text-align:center;">Cuota</th>
              <th style="text-align:center;">Implícita</th>
              <th style="text-align:center;">Modelo</th>
              <th style="text-align:center;">Edge</th>
            </tr>
            <tr style="color:#e2e8f0;">
              <td style="padding:4px 0;color:#3b82f6;font-weight:700;">1</td>
              <td style="text-align:center;">{odds_h:.2f}</td>
              <td style="text-align:center;">{_pct(ih)}</td>
              <td style="text-align:center;">{_pct(mh)}</td>
              <td style="text-align:center;color:{_edge_color(edge_h)};font-weight:700;">{edge_h:+.3f}</td>
            </tr>
            <tr style="color:#e2e8f0;">
              <td style="padding:4px 0;color:#6366f1;font-weight:700;">X</td>
              <td style="text-align:center;">{odds_d:.2f}</td>
              <td style="text-align:center;">{_pct(id_)}</td>
              <td style="text-align:center;">{_pct(md_)}</td>
              <td style="text-align:center;color:{_edge_color(edge_d)};font-weight:700;">{edge_d:+.3f}</td>
            </tr>
            <tr style="color:#e2e8f0;">
              <td style="padding:4px 0;color:#f97316;font-weight:700;">2</td>
              <td style="text-align:center;">{odds_a:.2f}</td>
              <td style="text-align:center;">{_pct(ia)}</td>
              <td style="text-align:center;">{_pct(ma)}</td>
              <td style="text-align:center;color:{_edge_color(edge_a)};font-weight:700;">{edge_a:+.3f}</td>
            </tr>
          </table>

          <!-- Best pick -->
          <div style="margin-top:14px;background:#172033;border:1px solid {_edge_color(best_edge)}44;
                      border-radius:10px;padding:10px 14px;">
            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Selección sugerida</div>
            <div style="font-size:15px;color:{_edge_color(best_edge)};font-weight:700;margin-top:2px;">{sel_label}</div>
            <div style="font-size:12px;color:#94a3b8;">@ {best_odds:.2f} &nbsp;·&nbsp; Edge: <span style="color:{_edge_color(best_edge)};font-weight:700;">{best_edge:+.3f}</span></div>
            <div style="font-size:12px;color:#94a3b8;margin-top:4px;">EV: <span style="color:{_edge_color(best_edge)};font-weight:700;">{best_pick_ev:+.2%}</span> &nbsp;·&nbsp; Kelly 25%: <span style="color:#22c55e;font-weight:700;">{best_pick_kelly:.1%}</span></div>
          </div>

          <div style="margin-top:10px;background:#0b1220;border:1px solid #334155;border-radius:10px;padding:10px 12px;">
            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Semáforo de decisión</div>
            <div style="font-size:14px;font-weight:800;color:#e2e8f0;margin-top:2px;">{decision_signal}</div>
            <div style="font-size:11px;color:#94a3b8;margin-top:2px;line-height:1.4;">{decision_reason}</div>
            <div style="font-size:12px;color:#cbd5e1;margin-top:6px;">Stake sugerido con tu banca de <strong style="color:#3b82f6;">${bankroll:,.0f}</strong> (Kelly 25%): <strong style="color:#22c55e;">${best_pick_stake:.2f}</strong></div>
          </div>

          <div style="margin-top:12px;font-size:11px;color:#64748b;line-height:1.4;">
            <div><strong style="color:#cbd5e1;">Muestras usadas:</strong> reciente local {recent_home_n}, reciente visita {recent_away_n}</div>
            <div>modelo local {model_home_n}, modelo visita {model_away_n} ({model_sample_source})</div>
          </div>
        </div>

        <!-- Col 2: Goals / Scores / Markets -->
        <div style="padding:20px;border-right:1px solid #1e293b;">
          <div style="font-size:11px;color:#64748b;letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;">
            ⚽ Goles &amp; Marcadores
          </div>

          <!-- Expected goals visual -->
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:900;color:#3b82f6;">{goals_home:.2f}</div>
              <div style="font-size:11px;color:#64748b;">xG local</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:14px;color:#475569;font-weight:600;">vs</div>
              <div style="font-size:11px;color:#64748b;margin-top:2px;">total {goals_total:.2f}</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:900;color:#f97316;">{goals_away:.2f}</div>
              <div style="font-size:11px;color:#64748b;">xG visitante</div>
            </div>
          </div>

          <!-- Goals profile tag -->
          <div style="text-align:center;margin-bottom:12px;">
            {_tag(goals_profile, "#6366f1")}
          </div>

          <!-- Most likely score -->
          <div style="background:#172033;border-radius:10px;padding:12px;margin-bottom:10px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Marcador más probable</div>
            <div style="font-size:30px;font-weight:900;color:#f1f5f9;letter-spacing:2px;margin:4px 0;">{likely_score}</div>
            <div style="font-size:12px;color:#f59e0b;">{likely_outcome} &nbsp;·&nbsp; {likely_prob:.1%} prob.</div>
          </div>

          <!-- Top scorelines -->
          <div style="font-size:11px;color:#64748b;margin-bottom:6px;">Top marcadores:</div>
          <div style="font-size:12px;color:#cbd5e1;background:#172033;padding:8px;border-radius:8px;">{top_lines}</div>

          <!-- O/U bars -->
          <div style="margin-top:12px;">
            {_prob_bar("Más de 1.5 goles", over15, "#22c55e")}
            {_prob_bar("Más de 2.5 goles", over25, "#f59e0b")}
            {_prob_bar("Más de 3.5 goles", over35, "#ef4444")}
            {_prob_bar("BTTS (ambos marcan)", btts_prob, "#8b5cf6")}
          </div>

          <!-- Clean sheet -->
          <div style="margin-top:10px;display:flex;gap:6px;">
            {_tag(f"CS Local {home_cs:.0%}", "#06b6d4")}
            {_tag(f"CS Visita {away_cs:.0%}", "#ec4899")}
          </div>
        </div>

        <!-- Col 3: Stats + Form -->
        <div style="padding:20px;">
          <div style="font-size:11px;color:#64748b;letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;">
            📋 Estadísticas estimadas
          </div>

          <!-- Stats table -->
          <div style="font-size:11px;color:#64748b;display:grid;grid-template-columns:1fr auto 1fr;
                      margin-bottom:4px;text-align:center;">
            <span style="text-align:right;padding-right:10px;">{home}</span>
            <span></span>
            <span style="text-align:left;padding-left:10px;">{away}</span>
          </div>
          {_stat_row("🎯", "Tiros totales", f"{shots_h:.1f}", f"{shots_a:.1f}")}
          {_stat_row("🔵", "A puerta", f"{sot_h:.1f}", f"{sot_a:.1f}")}
          {_stat_row("🚩", "Corners", f"{corners_h:.1f}", f"{corners_a:.1f}")}
          {_stat_row("🟨", "Tarjetas", f"{cards_h:.1f}", f"{cards_a:.1f}")}

          <!-- Form -->
          <div style="margin-top:16px;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
              📈 Forma reciente
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
              <span style="font-size:12px;color:#94a3b8;width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{home[:15]}</span>
              <div>{_form_html(home_form)}</div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:12px;color:#94a3b8;width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{away[:15]}</span>
              <div>{_form_html(away_form)}</div>
            </div>
          </div>

          <!-- Market tags -->
          <div style="margin-top:14px;display:flex;flex-wrap:wrap;gap:6px;">
            {_tag(btts_lean, "#8b5cf6")}
            {_tag(str(row.get("GoalsLean", "")), "#f59e0b")}
          </div>

          <div style="margin-top:16px;background:#172033;border:1px solid #334155;border-radius:10px;padding:12px;">
            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Top 3 sugerencias analíticas</div>
            <div style="font-size:12px;color:#e2e8f0;line-height:1.45;">
              <div style="margin-bottom:6px;">1) {suggestion_1}</div>
              <div style="margin-bottom:6px;">2) {suggestion_2}</div>
              <div>3) {suggestion_3}</div>
            </div>
            <div style="font-size:11px;color:#64748b;margin-top:8px;">{metrics_legend}</div>
          </div>
        </div>

      </div><!-- end grid -->
    </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Glossary
# ──────────────────────────────────────────────────────────────────────────────

def _gterm(term: str, definition: str, extra: str = "") -> str:
    extra_html = f'<div style="font-size:11px;color:#64748b;margin-top:3px;">{extra}</div>' if extra else ""
    return f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;">
      <div style="font-size:13px;font-weight:700;color:#3b82f6;margin-bottom:4px;">{term}</div>
      <div style="font-size:12px;color:#cbd5e1;line-height:1.55;">{definition}</div>
      {extra_html}
    </div>"""


def _gsection(title: str, icon: str, items: list[tuple[str, str, str]]) -> str:
    cards = "".join(_gterm(t, d, e) for t, d, e in items)
    return f"""
    <div style="margin-bottom:32px;">
      <h3 style="font-size:14px;font-weight:700;color:#94a3b8;letter-spacing:2px;
                 text-transform:uppercase;margin-bottom:14px;padding-bottom:8px;
                 border-bottom:1px solid #1e293b;">
        {icon}&nbsp; {title}
      </h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;">
        {cards}
      </div>
    </div>"""


def _glossary_section() -> str:
    cuotas = _gsection("Cuotas y Probabilidades", "📐", [
        (
            "Cuota Decimal",
            "Número que multiplica tu apuesta en caso de ganar. Una cuota de 2.50 significa que por cada $1 apostado recibirás $2.50 (ganancia neta de $1.50).",
            "Ejemplo: $10 × 2.50 = $25 total devuelto",
        ),
        (
            "Probabilidad Implícita",
            "Probabilidad que la casa de apuestas asigna a un resultado, calculada como 1 ÷ cuota. Incluye el margen (vig) del bookmaker.",
            "Ej: cuota 2.00 → implícita 50%, cuota 3.00 → 33.3%",
        ),
        (
            "Probabilidad del Modelo",
            "Probabilidad que nuestro modelo estadístico (Poisson) asigna al resultado, basada en el poder de ataque/defensa histórico de cada equipo.",
            "Es la estimación «justa» sin margen comercial",
        ),
        (
            "Edge (Ventaja)",
            "Diferencia entre la probabilidad del modelo y la probabilidad implícita de la cuota. Edge positivo significa que el modelo cree que el resultado está subvalorado.",
            "Edge = P(modelo) − P(implícita) · Ej: 0.60 − 0.50 = +0.10",
        ),
        (
            "Vig / Margen del Bookmaker",
            "Porcentaje extra que cobra la casa. Si las probabilidades implícitas de 1X2 suman más de 100%, el exceso es el vig.",
            "Vig típico: 4–8%. Es la razón por la que el edge debe ser positivo para apostar.",
        ),
        (
            "Score Compuesto",
            "Métrica interna que combina edge máximo y diferencia de probabilidades para rankear partidos de mayor a menor interés analítico.",
            "Se usa para ordenar los partidos en la tabla",
        ),
    ])

    mercados = _gsection("Mercados y Apuestas", "🎰", [
        (
            "1X2 (Resultado Final)",
            "El mercado más común: apostás al resultado a 90 minutos (más tiempo extra sin contar). 1 = gana el local, X = empate, 2 = gana el visitante.",
            "",
        ),
        (
            "BTTS – Both Teams To Score",
            "Mercado en el que apostás a que AMBOS equipos anoten al menos un gol en el partido, sin importar el resultado final.",
            "Sí: ambos anotan. No: al menos uno termina con 0 goles.",
        ),
        (
            "Over/Under (Más/Menos)",
            "Apostás a si el total de goles del partido superará (Over) o no llegará (Under) a una línea específica: 1.5, 2.5, 3.5, etc.",
            "Más de 2.5 → necesitás 3 o más goles para ganar el Over",
        ),
        (
            "Clean Sheet (Arco en Cero)",
            "Probabilidad de que un equipo no reciba goles en el partido. Alta probabilidad de CS local implica una defensa sólida ante el rival.",
            "",
        ),
        (
            "Handicap Asiático",
            "Mercado que da ventaja/desventaja de goles a cada equipo antes de comenzar. Elimina el empate y permite apostar en partidos muy disparejos.",
            "Ej: Local −1.5 → el local debe ganar por 2 o más",
        ),
        (
            "Selección Sugerida",
            "El resultado (1, X o 2) con el edge más alto según el modelo. No es una recomendación de apuesta, sino el mercado más subvalorado encontrado.",
            "",
        ),
    ])

    estadisticas = _gsection("Estadísticas del Partido", "📊", [
        (
            "xG – Goles Esperados",
            "Métrica que estima cuántos goles debería haber marcado un equipo basándose en la calidad y posición de los tiros generados.",
            "xG alto → equipo dominante en ataque. xG bajo → pocas oportunidades claras.",
        ),
        (
            "Tiros Totales",
            "Cantidad total de remates al arco y fuera. Indicador de dominio ofensivo y presión sobre el rival.",
            "Promedio en ligas top: ~13 tiros por partido por equipo",
        ),
        (
            "Tiros a Puerta (SOT)",
            "Remates que van dirigidos al marco (habrían entrado de no ser por el arquero o los postes). Mejor predictor de goles que los tiros totales.",
            "Conversión promedio: 30–35% de tiros a puerta terminan en gol",
        ),
        (
            "Corners (Tiros de Esquina)",
            "Cantidad de corners obtenidos. Alta cantidad indica presión ofensiva y que el rival desvió muchos centros.",
            "Relación: más corners generalmente = más dominio territorial",
        ),
        (
            "Tarjetas Amarillas/Rojas",
            "Indicador de intensidad y agresividad del partido. Las tarjetas rojas cambian radicalmente el juego (superioridad numérica).",
            "Peso ponderado usado: amarilla = 1pt, roja = 2pts",
        ),
        (
            "Forma Reciente (W/D/L)",
            "Resultados de los últimos 5 partidos del equipo: W = Victoria (Win), D = Empate (Draw), L = Derrota (Loss). El primero es el más reciente.",
            "Ej: WWDLW → 3 victorias, 1 empate, 1 derrota en los últimos 5",
        ),
    ])

    modelo = _gsection("Modelo Predictivo", "🧠", [
        (
            "Modelo de Poisson",
            "Modelo estadístico que usa la distribución de Poisson para estimar la probabilidad de que cada equipo marque 0, 1, 2, 3... goles, basándose en su fuerza de ataque y defensa.",
            "Supuesto: los goles son eventos independientes con tasa constante λ",
        ),
        (
            "Fuerza de Ataque / Defensa",
            "Parámetros calculados del historial de cada equipo. Fuerza de ataque > 1 indica equipo goleador; fuerza de defensa < 1 indica defensa sólida.",
            "Se ajustan a la media de la liga para ser comparables entre equipos",
        ),
        (
            "λ (Lambda) – Tasa de Goles",
            "Valor esperado de goles para cada equipo en un partido específico, calculado como: λ_local = ataque_local × defensa_visitante × promedio_liga.",
            "Ej: λ = 1.8 → se esperan ~1.8 goles de ese equipo",
        ),
        (
            "Matriz de Marcadores",
            "Grilla de probabilidades para todos los posibles resultados (0-0, 0-1, 1-0, 1-1... hasta 6-6). Permite derivar probabilidades de cualquier mercado.",
            "Se calcula combinando las distribuciones de Poisson de ambos equipos",
        ),
        (
            "Top Marcadores",
            "Los 3 resultados exactos con mayor probabilidad según la matriz de marcadores. Útil para el mercado de marcador exacto.",
            "",
        ),
        (
            "Confianza Analítica (Alta/Media/Baja)",
            "Indicador de cuán consistente y fuerte es la señal del modelo. Combina la probabilidad máxima del resultado predicho con el edge máximo encontrado.",
            "Alta ≥ 0.72 · Media ≥ 0.58 · Baja < 0.58",
        ),
    ])

    finanzas = _gsection("Gestión de Bankroll", "💰", [
        (
            "Bankroll",
            "Capital total destinado exclusivamente a apuestas. Gestionar el bankroll correctamente es más importante que acertar partidos.",
            "Regla básica: nunca apostar más del 2–5% del bankroll en una sola apuesta",
        ),
        (
            "Criterio de Kelly",
            "Fórmula matemática para calcular el tamaño óptimo de la apuesta: f = (edge × cuota) / (cuota − 1). Maximiza el crecimiento del capital a largo plazo.",
            "Ej: edge=0.10, cuota=2.0 → f = 0.10 · 2 / (2−1) = 20% del bankroll",
        ),
        (
            "ROI – Retorno sobre Inversión",
            "Ganancia neta dividida por el total apostado, expresada en porcentaje. Un ROI positivo a largo plazo indica una estrategia ganadora.",
            "ROI = (Ganancias − Pérdidas) / Total Apostado × 100%",
        ),
        (
            "Value Betting",
            "Estrategia de apostar solo cuando el edge es positivo (el modelo cree que la probabilidad real es mayor que la implícita de la cuota).",
            "No busca acertar el resultado, sino encontrar cuotas subvaloradas",
        ),
        (
            "Paper Trading",
            "Simular apuestas sin dinero real para validar la estrategia antes de arriesgar capital. Este sistema incluye un módulo de paper trading.",
            "",
        ),
        (
            "Expected Value (EV)",
            "Ganancia esperada promedio por apuesta: EV = P(ganar) × ganancia − P(perder) × pérdida. Se debe apostar solo con EV > 0.",
            "EV > 0 = apuesta con valor positivo a largo plazo",
        ),
    ])

    ligas = _gsection("Ligas Cubiertas", "🌍", [
        ("Premier League (PL)", "Primera división de Inglaterra. Una de las ligas más competitivas y con más liquidez de mercado del mundo.", "20 equipos · Agosto–Mayo"),
        ("La Liga (PD)", "Primera división de España. Históricamente dominada por Real Madrid y FC Barcelona.", "20 equipos · Agosto–Mayo"),
        ("Serie A (SA)", "Primera división de Italia. Conocida por su solidez defensiva y táctica.", "20 equipos · Agosto–Mayo"),
        ("Bundesliga (BL1)", "Primera división de Alemania. El Bayern Munich domina históricamente. Alta presión colectiva.", "18 equipos · Agosto–Mayo"),
        ("Ligue 1 (FL1)", "Primera división de Francia. El PSG domina desde 2011.", "18 equipos · Agosto–Mayo"),
        ("Eredivisie (DED)", "Primera división de Países Bajos. Conocida por desarrollar talento joven.", "18 equipos · Agosto–Mayo"),
        ("Primeira Liga (PPL)", "Primera división de Portugal. Dominada por Porto, Benfica y Sporting.", "18 equipos · Agosto–Mayo"),
        ("Championship (ELC)", "Segunda división de Inglaterra. Considerada una de las mejores segundas divisiones del mundo.", "24 equipos · Agosto–Mayo"),
        ("Süper Lig (TUR)", "Primera división de Turquía. Galatasaray, Fenerbahçe y Beşiktaş son los grandes.", "19 equipos · Agosto–Mayo"),
        ("Scottish Premiership (SPL)", "Primera división de Escocia. Celtic y Rangers dominan el fútbol escocés.", "12 equipos · Agosto–Mayo"),
        ("Belgian Pro League (BEL)", "Primera división de Bélgica. Conocida por exportar talento a las grandes ligas.", "16 equipos · Agosto–Mayo"),
        ("UEFA Champions League (CL)", "La competición de clubes más prestigiosa del mundo. Incluye los mejores equipos de Europa.", "32/36 equipos · Sept–Mayo"),
        ("UEFA Europa League (EL)", "Segunda competición europea de clubes. Más accesible que la Champions.", ""),
        ("UEFA Conference League (UECL)", "Tercera competición europea de clubes. Creada en 2021 para más equipos.", ""),
        ("MLS (MLS)", "Major League Soccer de Estados Unidos y Canadá. Temporada inversa al hemisferio norte.", "29 equipos · Feb–Nov"),
        ("Liga MX (MX1)", "Primera división de México. Apertura (Jul–Dic) y Clausura (Ene–May).", "18 equipos"),
        ("Brasileirão Serie A (BSA)", "Primera división de Brasil. Temporada de mayo a diciembre.", "20 equipos · Mayo–Dic"),
        ("Primera División Argentina (ARG)", "Primera división de Argentina. Zona norte (ZN) y Copa de la Liga.", "28 equipos"),
    ])

    return f"""
  <!-- Glossary -->
  <div style="max-width:1300px;margin:0 auto;padding:0 24px 64px;" id="glosario">
    <div style="border-top:2px solid #1e293b;padding-top:48px;">
      <div style="text-align:center;margin-bottom:40px;">
        <div style="font-size:11px;color:#475569;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">
          Referencia completa
        </div>
        <h2 style="font-size:30px;font-weight:900;background:linear-gradient(135deg,#8b5cf6,#ec4899);
                   -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
          Glosario de Términos
        </h2>
        <p style="color:#475569;font-size:13px;margin-top:8px;">
          Todo lo que necesitás saber para interpretar el reporte
        </p>
      </div>
      {cuotas}
      {mercados}
      {estadisticas}
      {modelo}
      {finanzas}
      {ligas}
    </div>
  </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Full page
def _assign_bookmaker(ev: float, stake: float, index: int) -> tuple[str, str, str, str]:
    """Returns (house, house_color, house_bg, reason) for a pick.

    Rules to avoid detection:
    - EV > 25% or stake > $200 → 1xBet only (too obvious for Bet365)
    - EV 6-25% → alternate between houses (even index=1xBet, odd=Bet365)
    - 1xBet: full Kelly stake
    - Bet365: 40-50% of stake, rounded to nearest $5 (never exact amounts)
    """
    if ev > 0.25 or stake > 200:
        return "1xBet", "#22c55e", "#052e16", "EV/stake alto → 1xBet full"
    if index % 2 == 0:
        return "1xBet", "#22c55e", "#052e16", "Rotación de casa"
    return "Bet365", "#f97316", "#1c0a00", "Rotación de casa"


def _bet365_stake(stake: float) -> float:
    """Bet365 stake: ~45% of Kelly, rounded to nearest $5 to avoid detection."""
    raw = stake * 0.45
    return round(raw / 5) * 5 if raw >= 5 else max(1.0, round(raw))


# ──────────────────────────────────────────────────────────────────────────────
# Action Plan Section
# ──────────────────────────────────────────────────────────────────────────────

def _action_plan_section(df: pd.DataFrame, bankroll: float, target_profit: float) -> str:
    """Top-of-report panel: what to bet today, how much, and whether it tracks toward the monthly goal."""
    target_daily = target_profit / 30.0
    target_to = bankroll + target_profit

    # Separate green vs conviene picks
    green_df = pd.DataFrame()
    yellow_df = pd.DataFrame()
    if not df.empty:
        green_df = df[df["DecisionSignal"].astype(str).str.contains("🟢", na=False)].copy()
        yellow_df = df[
            df["DecisionSignal"].astype(str).str.contains("🟡 Conviene$", na=False, regex=True)
        ].copy()

    actionable = pd.concat([green_df, yellow_df], ignore_index=True) if not green_df.empty or not yellow_df.empty else pd.DataFrame()

    total_stake = 0.0
    total_expected = 0.0
    total_stake_1xbet = 0.0
    total_stake_b365 = 0.0
    pick_rows_html = ""

    if not actionable.empty:
        for idx, (_, row) in enumerate(actionable.iterrows()):
            ev = float(row.get("BestPickEV", 0) or 0)
            stake = float(row.get("BestPickStake", 0) or 0)
            expected = stake * ev
            total_stake += stake
            total_expected += expected

            house, house_color, house_bg, house_reason = _assign_bookmaker(ev, stake, idx)
            b365_stake = _bet365_stake(stake)

            if house == "1xBet":
                total_stake_1xbet += stake
                stake_display = f'<span style="color:#22c55e;font-weight:700;">${stake:,.2f}</span>'
                b365_display = f'<span style="color:#64748b;font-size:11px;">${b365_stake:,.0f} (opcional)</span>'
            else:
                total_stake_b365 += b365_stake
                stake_display = f'<span style="color:#64748b;font-size:11px;">${stake:,.2f} (ref.)</span>'
                b365_display = f'<span style="color:#f97316;font-weight:700;">${b365_stake:,.0f}</span>'

            signal = str(row.get("DecisionSignal", ""))
            match_name = str(row.get("Match", ""))
            pick = str(row.get("BestPick1X2", ""))
            odds = float(row.get("BestPickOdds", 1) or 1)
            net_win = stake * (odds - 1)
            league = str(row.get("League", ""))
            conf = str(row.get("ConfidenceLabel", ""))
            conf_color = _conf_color(conf)

            pick_rows_html += f"""
            <tr style="border-bottom:1px solid #1e293b;">
              <td style="padding:8px 10px;font-size:11px;color:#64748b;">{league}</td>
              <td style="padding:8px 10px;font-size:13px;color:#e2e8f0;font-weight:600;">{match_name}</td>
              <td style="padding:8px 10px;font-size:13px;font-weight:700;">{signal}</td>
              <td style="padding:8px 10px;font-size:13px;color:#3b82f6;font-weight:700;">{pick} @ {odds:.2f}</td>
              <td style="padding:8px 10px;">
                <div style="background:{house_bg};color:{house_color};border:1px solid {house_color}55;
                     border-radius:8px;padding:3px 10px;font-size:12px;font-weight:700;display:inline-block;">
                  {house}
                </div>
                <div style="font-size:10px;color:#475569;margin-top:2px;">{house_reason}</div>
              </td>
              <td style="padding:8px 10px;font-size:13px;">{stake_display}</td>
              <td style="padding:8px 10px;font-size:13px;">{b365_display}</td>
              <td style="padding:8px 10px;font-size:12px;color:#f59e0b;">${net_win:,.2f} si gana</td>
              <td style="padding:8px 10px;font-size:12px;color:{_edge_color(ev)};">{ev:+.2%}</td>
              <td style="padding:8px 10px;"><span style="background:{conf_color}22;color:{conf_color};border:1px solid {conf_color}55;border-radius:8px;padding:2px 8px;font-size:11px;">{conf}</span></td>
            </tr>"""

    monthly_projection = total_expected * 30
    daily_gap = total_expected - target_daily
    on_track = total_expected >= target_daily
    status_color = "#22c55e" if on_track else "#f59e0b"
    status_text = "✅ En camino a tu meta" if on_track else "⚠️ Por debajo del ritmo diario"
    status_detail = (
        f"Ganás ${daily_gap:+.2f}/día de más respecto a tu objetivo"
        if on_track
        else f"Faltan ${abs(daily_gap):.2f}/día para alcanzar tu meta mensual"
    )

    # Days-to-goal at this rate
    if total_expected > 0:
        days_to_goal = math.ceil(target_profit / total_expected)
        days_html = f"<strong style='color:#8b5cf6;'>{days_to_goal} días activos</strong> como hoy para acumular ${target_profit:,.0f}"
    else:
        days_to_goal = None
        days_html = "<span style='color:#ef4444;'>Hoy no hay picks con señal suficiente para proyectar</span>"

    # No picks case
    if actionable.empty:
        no_picks_msg = """
        <div style="text-align:center;padding:24px;color:#64748b;font-size:14px;">
          <div style="font-size:32px;margin-bottom:8px;">🔴</div>
          <div>Hoy no hay picks con señal verde o verde-amarilla.<br>
          No apuestes. Esperá un día con mejores condiciones.</div>
        </div>"""
        table_html = no_picks_msg
    else:
        table_html = f"""
        <div style="overflow-x:auto;margin-top:16px;">
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#1e293b;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
                <th style="padding:8px 10px;text-align:left;">Liga</th>
                <th style="padding:8px 10px;text-align:left;">Partido</th>
                <th style="padding:8px 10px;text-align:left;">Señal</th>
                <th style="padding:8px 10px;text-align:left;">Apuesta</th>
                <th style="padding:8px 10px;text-align:left;">Casa principal</th>
                <th style="padding:8px 10px;text-align:left;color:#22c55e;">Stake 1xBet</th>
                <th style="padding:8px 10px;text-align:left;color:#f97316;">Stake Bet365</th>
                <th style="padding:8px 10px;text-align:left;">Ganancia si gana</th>
                <th style="padding:8px 10px;text-align:left;">EV</th>
                <th style="padding:8px 10px;text-align:left;">Confianza</th>
              </tr>
            </thead>
            <tbody>{pick_rows_html}</tbody>
          </table>
        </div>

        <!-- Anti-ban tip -->
        <div style="background:#0b1220;border:1px solid #334155;border-radius:10px;padding:12px 16px;margin-top:14px;
                    display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;">
          <div style="font-size:20px;">🛡️</div>
          <div>
            <div style="font-size:12px;font-weight:700;color:#f59e0b;margin-bottom:4px;">Estrategia anti-ban activa</div>
            <div style="font-size:12px;color:#94a3b8;line-height:1.6;">
              · <strong style="color:#22c55e;">1xBet</strong>: usá el stake completo sugerido. Es tolerante con apostadores ganadores.<br>
              · <strong style="color:#f97316;">Bet365</strong>: stake reducido al ~45%, <em>siempre redondeado a múltiplos de $5</em> (nunca el monto exacto del modelo).<br>
              · Podés apostar el mismo pick en <strong>ambas casas</strong> para maximizar exposición sin levantar sospechas.<br>
              · Picks con EV &gt; 25% o stake &gt; $200 van <strong>solo a 1xBet</strong> — en Bet365 son demasiado obvios.
            </div>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:14px;">
          <div style="background:#172033;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Picks de hoy</div>
            <div style="font-size:26px;font-weight:900;color:#3b82f6;margin-top:4px;">{len(actionable)}</div>
          </div>
          <div style="background:#052e16;border:1px solid #22c55e44;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Total 1xBet</div>
            <div style="font-size:26px;font-weight:900;color:#22c55e;margin-top:4px;">${total_stake_1xbet:,.0f}</div>
            <div style="font-size:11px;color:#64748b;">stake completo</div>
          </div>
          <div style="background:#1c0a00;border:1px solid #f9731644;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Total Bet365</div>
            <div style="font-size:26px;font-weight:900;color:#f97316;margin-top:4px;">${total_stake_b365:,.0f}</div>
            <div style="font-size:11px;color:#64748b;">~45%, redondeado</div>
          </div>
          <div style="background:#172033;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Ganancia esperada</div>
            <div style="font-size:26px;font-weight:900;color:#22c55e;margin-top:4px;">${total_expected:,.2f}</div>
            <div style="font-size:11px;color:#64748b;">meta diaria ${target_daily:.2f}</div>
          </div>
          <div style="background:#172033;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Proyección mensual</div>
            <div style="font-size:26px;font-weight:900;color:#8b5cf6;margin-top:4px;">${monthly_projection:,.2f}</div>
            <div style="font-size:11px;color:#64748b;">si cada día es como hoy</div>
          </div>
        </div>"""

    return f"""
  <!-- Action Plan -->
  <div style="max-width:1300px;margin:0 auto;padding:24px 24px 0;" id="plan-hoy">
    <div style="background:linear-gradient(135deg,#0f172a 0%,#172033 100%);border:1px solid #334155;
                border-radius:16px;padding:24px;margin-bottom:24px;">

      <!-- Header row -->
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;margin-bottom:20px;">
        <div>
          <div style="font-size:11px;color:#475569;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">
            🎯 Plan de acción · Hoy
          </div>
          <h2 style="font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:-0.5px;">
            Tu ruta para ganar lo máximo posible
          </h2>
          <div style="font-size:13px;color:#64748b;margin-top:4px;">
            Banca: <strong style="color:#3b82f6;">${bankroll:,.0f}</strong>
            &nbsp;→&nbsp; Meta: <strong style="color:#22c55e;">${target_to:,.0f}</strong>
            &nbsp;(+$<strong style="color:#22c55e;">{target_profit:,.0f}</strong>/mes)
          </div>
        </div>
        <div style="background:{status_color}22;border:1px solid {status_color}55;border-radius:12px;padding:14px 20px;text-align:center;">
          <div style="font-size:14px;font-weight:800;color:{status_color};">{status_text}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:4px;">{status_detail}</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:2px;">{days_html}</div>
        </div>
      </div>

      <!-- Rules reminder -->
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:20px;">
        <div style="background:#0b1220;border-left:3px solid #22c55e;border-radius:8px;padding:10px 14px;">
          <div style="font-size:11px;color:#22c55e;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Solo 🟢 y 🟡 Conviene</div>
          <div style="font-size:12px;color:#94a3b8;line-height:1.5;">Apostá únicamente picks con señal verde o "Conviene". Ignorá todo lo rojo y marginal.</div>
        </div>
        <div style="background:#0b1220;border-left:3px solid #3b82f6;border-radius:8px;padding:10px 14px;">
          <div style="font-size:11px;color:#3b82f6;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Kelly 25% fraccionado</div>
          <div style="font-size:12px;color:#94a3b8;line-height:1.5;">Usá el 25% del Kelly calculado por el modelo. El stake sugerido ya está limitado para proteger la banca.</div>
        </div>
        <div style="background:#0b1220;border-left:3px solid #f59e0b;border-radius:8px;padding:10px 14px;">
          <div style="font-size:11px;color:#f59e0b;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">No perseguir pérdidas</div>
          <div style="font-size:12px;color:#94a3b8;line-height:1.5;">Si perdés, no aumentes stakes. El modelo trabaja a largo plazo. Días sin picks son días de no apostar.</div>
        </div>
        <div style="background:#0b1220;border-left:3px solid #8b5cf6;border-radius:8px;padding:10px 14px;">
          <div style="font-size:11px;color:#8b5cf6;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Compounding</div>
          <div style="font-size:12px;color:#94a3b8;line-height:1.5;">Recalculá tu banca periódicamente. Si crece, el stake crece proporcionalmente. Así funciona el interés compuesto.</div>
        </div>
      </div>

      <!-- Picks table -->
      <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
        📋 Picks accionables de hoy · <span style="color:#22c55e;">1xBet</span> stake completo · <span style="color:#f97316;">Bet365</span> stake reducido anti-ban
      </div>
      {table_html}

    </div>
  </div>"""


# ──────────────────────────────────────────────────────────────────────────────
# Full page
# ──────────────────────────────────────────────────────────────────────────────

def generate_html_report(
    df: pd.DataFrame,
    report_date: date,
    output_path: Path | None = None,
    bankroll: float = 2500.0,
    target_profit: float = 500.0,
) -> Path:
    """Build a standalone HTML report and write it to *output_path*.

    Returns the resolved Path of the written file.
    """
    if output_path is None:
        output_path = Path.home() / "Desktop" / f"reporte_apuestas_{report_date.isoformat()}.html"

    output_path = Path(output_path)

    # Build match cards
    cards_html = ""
    if df.empty:
        cards_html = (
            '<div style="text-align:center;color:#475569;padding:60px;font-size:18px;">'
            "No hay partidos disponibles para esta fecha.</div>"
        )
    else:
        for _, row in df.iterrows():
            cards_html += _match_card(row.to_dict(), bankroll=bankroll)

    total_matches = len(df)
    high_conf = int((df["ConfidenceLabel"] == "Alta").sum()) if not df.empty else 0
    avg_edge = float(df["EdgeMax"].mean()) if not df.empty else 0.0
    leagues = ", ".join(df["League"].dropna().unique().tolist()) if not df.empty else "—"

    action_plan_html = _action_plan_section(df, bankroll=bankroll, target_profit=target_profit)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Reporte de Apuestas · {report_date.isoformat()}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      background: #020817;
      color: #e2e8f0;
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; }}
    ::selection {{ background: #3b82f644; }}
    /* scrollbar */
    ::-webkit-scrollbar {{ width: 8px; }}
    ::-webkit-scrollbar-track {{ background: #0f172a; }}
    ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 4px; }}
  </style>
</head>
<body>

  <!-- Top gradient bar -->
  <div style="height:4px;background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899,#f97316);"></div>

  <!-- Hero header -->
  <div style="background:linear-gradient(180deg,#0f172a 0%,#020817 100%);padding:48px 32px 32px;text-align:center;border-bottom:1px solid #1e293b;">
    <div style="font-size:11px;color:#475569;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;">
      Modelo Predictivo · Análisis Diario
    </div>
    <h1 style="font-size:38px;font-weight:900;background:linear-gradient(135deg,#3b82f6,#8b5cf6);
               -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
               letter-spacing:-1px;margin-bottom:8px;">
      {report_date.strftime('%A %d de %B, %Y').capitalize()}
    </h1>
    <p style="color:#475569;font-size:14px;">{leagues}</p>

    <!-- Summary pills -->
    <div style="display:flex;justify-content:center;gap:16px;margin-top:28px;flex-wrap:wrap;">
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px 28px;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#3b82f6;">{total_matches}</div>
        <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:2px;">Partidos</div>
      </div>
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px 28px;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#22c55e;">{high_conf}</div>
        <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:2px;">Alta confianza</div>
      </div>
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:14px 28px;text-align:center;">
        <div style="font-size:28px;font-weight:900;color:#f59e0b;">{avg_edge:+.3f}</div>
        <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-top:2px;">Edge promedio</div>
      </div>
    </div>
  </div>

  {action_plan_html}

  <!-- Legend -->
  <div style="max-width:1300px;margin:0 auto;padding:20px 24px 8px;display:flex;gap:20px;flex-wrap:wrap;align-items:center;">
    <span style="font-size:11px;color:#475569;text-transform:uppercase;letter-spacing:1px;">Leyenda:</span>
    <span style="font-size:12px;"><span style="color:#22c55e;">■</span> Alta confianza / Edge fuerte</span>
    <span style="font-size:12px;"><span style="color:#f59e0b;">■</span> Media confianza / Edge moderado</span>
    <span style="font-size:12px;"><span style="color:#ef4444;">■</span> Baja confianza / Edge débil</span>
    <span style="font-size:12px;"><span style="color:#3b82f6;">■</span> Local &nbsp;<span style="color:#6366f1;">■</span> Empate &nbsp;<span style="color:#f97316;">■</span> Visitante</span>
  </div>

  <!-- Cards -->
  <div style="max-width:1300px;margin:0 auto;padding:16px 24px 48px;">
    {cards_html}
  </div>

  {_glossary_section()}

  <!-- Footer -->
  <div style="border-top:1px solid #1e293b;padding:24px;text-align:center;color:#334155;font-size:12px;">
    Generado el {report_date.isoformat()} &nbsp;·&nbsp; Banca: ${bankroll:,.0f} &nbsp;·&nbsp; Meta mensual: +${target_profit:,.0f}
    &nbsp;·&nbsp; Solo para uso educativo y analítico. Las predicciones son estimaciones estadísticas, no garantías.
  </div>

</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path
