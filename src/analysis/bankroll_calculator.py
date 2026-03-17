from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GrowthScenario:
    name: str
    stake_pct: float
    bets_per_day: int
    roi_per_bet: float

    @property
    def monthly_return_pct(self) -> float:
        return self.stake_pct * self.bets_per_day * 30 * self.roi_per_bet

    def monthly_profit(self, bankroll: float) -> float:
        return bankroll * self.monthly_return_pct


DEFAULT_SCENARIOS: list[GrowthScenario] = [
    GrowthScenario("Conservador", 0.02, 3, 0.03),
    GrowthScenario("Moderado", 0.03, 3, 0.04),
    GrowthScenario("Bueno", 0.04, 4, 0.05),
    GrowthScenario("Agresivo", 0.05, 4, 0.06),
    GrowthScenario("Muy agresivo", 0.08, 5, 0.08),
]


def required_monthly_return(bankroll: float, target_profit: float) -> float:
    if bankroll <= 0:
        return 0.0
    return target_profit / bankroll


def required_roi_per_bet(
    bankroll: float,
    target_profit: float,
    stake_pct: float,
    bets_per_day: int,
    days: int = 30,
) -> float:
    base = bankroll * stake_pct * bets_per_day * days
    if base <= 0:
        return 0.0
    return target_profit / base


def compound_growth(start_bankroll: float, monthly_return_pct: float, months: int = 6) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    bankroll = start_bankroll
    for month in range(1, months + 1):
        profit = bankroll * monthly_return_pct
        end_bankroll = bankroll + profit
        rows.append(
            {
                "month": float(month),
                "start_bankroll": bankroll,
                "profit": profit,
                "end_bankroll": end_bankroll,
            }
        )
        bankroll = end_bankroll
    return rows
