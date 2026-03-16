from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


class LocalDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS simulation_positions (
                    sim_date TEXT NOT NULL,
                    league TEXT,
                    match_id TEXT,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    odds REAL,
                    model_prob REAL,
                    implied_prob REAL,
                    edge REAL,
                    stake REAL NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    payout REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (sim_date, home_team, away_team, selection)
                )
                """
            )

    def get_cache(self, cache_key: str, ttl_minutes: int) -> Any | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload, created_at FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row:
            return None

        created_at = datetime.fromisoformat(row["created_at"])
        if datetime.now(timezone.utc) - created_at > timedelta(minutes=ttl_minutes):
            return None
        return json.loads(row["payload"])

    def set_cache(self, cache_key: str, payload: Any) -> None:
        now = datetime.now(timezone.utc).isoformat()
        data = json.dumps(payload, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO api_cache (cache_key, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (cache_key, data, now),
            )

    def save_positions(self, rows: Iterable[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO simulation_positions (
                        sim_date, league, match_id, home_team, away_team, selection,
                        odds, model_prob, implied_prob, edge, stake, status, result,
                        payout, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sim_date, home_team, away_team, selection) DO UPDATE SET
                        odds = excluded.odds,
                        model_prob = excluded.model_prob,
                        implied_prob = excluded.implied_prob,
                        edge = excluded.edge,
                        stake = excluded.stake,
                        status = excluded.status,
                        result = excluded.result,
                        payout = excluded.payout,
                        updated_at = excluded.updated_at
                    """,
                    (
                        row["sim_date"],
                        row.get("league"),
                        row.get("match_id"),
                        row["home_team"],
                        row["away_team"],
                        row["selection"],
                        row.get("odds"),
                        row.get("model_prob"),
                        row.get("implied_prob"),
                        row.get("edge"),
                        row.get("stake", 1.0),
                        row.get("status", "PENDING"),
                        row.get("result"),
                        row.get("payout"),
                        now,
                        now,
                    ),
                )

    def list_positions(self, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM simulation_positions"
        params: list[Any] = []
        if start_date and end_date:
            query += " WHERE sim_date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        elif start_date:
            query += " WHERE sim_date = ?"
            params.append(start_date)
        query += " ORDER BY sim_date, league, home_team"

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
