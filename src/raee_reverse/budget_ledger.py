"""Atomic budget reservations shared by work units.

A missing price is unknown, not zero. A cancelled call that might still be
billed stays on the ledger. Review slots cannot be spent on generation.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_config (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  call_cap INTEGER NOT NULL,
  review_reserve INTEGER NOT NULL,
  high_tier_cap INTEGER NOT NULL,
  money_cap TEXT
);
CREATE TABLE IF NOT EXISTS reservations (
  id TEXT PRIMARY KEY,
  unit_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  tier TEXT,
  calls INTEGER NOT NULL,
  money_status TEXT NOT NULL,
  money_amount TEXT,
  status TEXT NOT NULL,
  billing TEXT NOT NULL,
  usage_json TEXT
);
"""


class BudgetDenied(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class BudgetLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        row = self._conn.execute("SELECT id FROM budget_config WHERE id=1").fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO budget_config (id, call_cap, review_reserve, high_tier_cap, money_cap) VALUES (1, 8, 1, 2, NULL)"
            )

    def configure(
        self,
        *,
        call_cap: int,
        review_reserve: int,
        high_tier_cap: int,
        money_cap: str | None,
    ) -> None:
        if review_reserve < 0 or review_reserve >= call_cap:
            raise BudgetDenied("review reserve must leave at least one non-review call slot")
        with self._lock:
            self._conn.execute(
                "UPDATE budget_config SET call_cap=?, review_reserve=?, high_tier_cap=?, money_cap=? WHERE id=1",
                (call_cap, review_reserve, high_tier_cap, money_cap),
            )

    def reserve(
        self,
        *,
        unit_id: str,
        kind: str,
        calls: int = 1,
        tier: str | None = None,
        price_status: str = "unknown",
        price_amount: str | None = None,
    ) -> dict[str, Any]:
        if kind not in ("generation", "review"):
            raise BudgetDenied("kind must be generation or review")
        if price_status not in ("known", "unknown"):
            raise BudgetDenied("price_status must be known or unknown")
        if price_status == "known" and price_amount is None:
            raise BudgetDenied("a known price needs an amount")
        if price_status == "unknown":
            price_amount = None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                config = self._conn.execute("SELECT * FROM budget_config WHERE id=1").fetchone()
                active = self._conn.execute(
                    "SELECT * FROM reservations WHERE status IN ('held', 'committed')"
                ).fetchall()
                reason = self._fits(config, active, kind, calls, tier, price_status, price_amount)
                if reason is not None:
                    self._conn.rollback()
                    raise BudgetDenied(reason)
                reservation_id = uuid.uuid4().hex
                self._conn.execute(
                    """
                    INSERT INTO reservations
                      (id, unit_id, kind, tier, calls, money_status, money_amount, status, billing, usage_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'held', 'not_issued', NULL)
                    """,
                    (reservation_id, unit_id, kind, tier, calls, price_status, price_amount),
                )
                self._conn.commit()
            except BudgetDenied:
                raise
            except Exception:
                self._conn.rollback()
                raise
        return self.get(reservation_id)

    def mark_issued(self, reservation_id: str) -> dict[str, Any]:
        return self._set(reservation_id, status="held", billing="issued_maybe_billed")

    def cancel(self, reservation_id: str) -> dict[str, Any]:
        """Cancellation does not delete the row and does not set cost to zero."""
        return self._set(reservation_id, status="committed", billing="cancelled_maybe_billed")

    def commit_usage(self, reservation_id: str, usage: dict[str, Any] | None) -> dict[str, Any]:
        import json

        payload = json.dumps(usage) if isinstance(usage, dict) else None
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "UPDATE reservations SET status='committed', billing='completed', usage_json=? WHERE id=?",
                    (payload, reservation_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get(reservation_id)

    def release(self, reservation_id: str) -> dict[str, Any]:
        """Release only a reservation that was never issued."""
        current = self.get(reservation_id)
        if current["billing"] != "not_issued":
            raise BudgetDenied("an issued call cannot be released as free")
        return self._set(reservation_id, status="released", billing="not_issued")

    def get(self, reservation_id: str) -> dict[str, Any]:
        row = self._conn.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        if row is None:
            raise BudgetDenied("reservation not found")
        return _row_dict(row)

    def rollup(self) -> dict[str, Any]:
        import json

        rows = [
            _row_dict(row)
            for row in self._conn.execute("SELECT * FROM reservations WHERE status != 'released'").fetchall()
        ]
        money_known = []
        money_unknown = False
        raw = 0
        cache_hit = 0
        billed = 0
        raw_known = True
        cache_known = True
        billed_known = True
        for row in rows:
            if row["money_status"] == "unknown" or row["money_amount"] is None:
                money_unknown = True
            else:
                money_known.append(row["money_amount"])
            usage = json.loads(row["usage_json"]) if row["usage_json"] else None
            normalized = _normalize_usage(usage)
            for key, flag in (
                ("raw_input_tokens", "raw_known"),
                ("cache_hit_tokens", "cache_known"),
                ("billed_tokens", "billed_known"),
            ):
                if normalized[key]["status"] != "known":
                    if flag == "raw_known":
                        raw_known = False
                    elif flag == "cache_known":
                        cache_known = False
                    else:
                        billed_known = False
                else:
                    if key == "raw_input_tokens":
                        raw += normalized[key]["value"]
                    elif key == "cache_hit_tokens":
                        cache_hit += normalized[key]["value"]
                    else:
                        billed += normalized[key]["value"]
        return {
            "calls": rows,
            "call_count": len(rows),
            "includes_failed_and_cancelled": True,
            "money_status": "unknown" if money_unknown or not rows else "known",
            "money_amount": None if money_unknown or not rows else _sum_decimal(money_known),
            "raw_input_tokens": {"status": "known" if raw_known and rows else "unknown", "value": raw if raw_known and rows else None},
            "cache_hit_tokens": {"status": "known" if cache_known and rows else "unknown", "value": cache_hit if cache_known and rows else None},
            "billed_tokens": {"status": "known" if billed_known and rows else "unknown", "value": billed if billed_known and rows else None},
            "savings_percent": None,
        }

    def close(self) -> None:
        self._conn.close()

    def _fits(self, config, active, kind, calls, tier, price_status, price_amount) -> str | None:
        generation = sum(row["calls"] for row in active if row["kind"] == "generation")
        review = sum(row["calls"] for row in active if row["kind"] == "review")
        high = sum(row["calls"] for row in active if row["tier"] == "T3")
        unknown_money = any(row["money_status"] == "unknown" and row["kind"] == "generation" for row in active)
        if kind == "generation":
            if generation + calls > config["call_cap"] - config["review_reserve"]:
                return "generation would consume the review reserve"
        else:
            if review + calls > config["review_reserve"]:
                return "review reserve exceeded"
        if tier == "T3" and high + calls > config["high_tier_cap"]:
            return "high-tier cap exceeded"
        if config["money_cap"] is not None:
            if unknown_money or price_status == "unknown":
                if unknown_money:
                    return "an unknown-price reservation is outstanding, so remaining money is unknown"
                # This reservation itself is unknown. Allow one outstanding unknown
                # so the call is recorded, but do not treat it as free.
                return None
            spent = _sum_decimal(
                [row["money_amount"] for row in active if row["money_status"] == "known" and row["money_amount"] is not None]
            )
            if _decimal_gt(_decimal_add(spent, price_amount), config["money_cap"]):
                return "money cap exceeded"
        return None

    def _set(self, reservation_id: str, *, status: str, billing: str) -> dict[str, Any]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "UPDATE reservations SET status=?, billing=? WHERE id=?",
                    (status, billing, reservation_id),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get(reservation_id)


def _normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    keys = ("raw_input_tokens", "cache_hit_tokens", "billed_tokens", "output_tokens")
    if not isinstance(usage, dict):
        return {key: {"status": "unknown", "value": None} for key in keys}
    out = {}
    for key in keys:
        value = usage.get(key)
        if isinstance(value, dict) and value.get("status") == "known" and isinstance(value.get("value"), int):
            out[key] = {"status": "known", "value": value["value"]}
        elif isinstance(value, int) and value >= 0:
            out[key] = {"status": "known", "value": value}
        else:
            out[key] = {"status": "unknown", "value": None}
    return out


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _sum_decimal(values: list[str]) -> str:
    total = 0
    for value in values:
        total += _to_cents(value)
    return _from_cents(total)


def _decimal_add(left: str, right: str) -> str:
    return _from_cents(_to_cents(left) + _to_cents(right))


def _decimal_gt(left: str, right: str) -> bool:
    return _to_cents(left) > _to_cents(right)


def _to_cents(value: str) -> int:
    text = str(value)
    if "." in text:
        whole, frac = text.split(".", 1)
        frac = (frac + "00")[:2]
    else:
        whole, frac = text, "00"
    sign = -1 if whole.startswith("-") else 1
    whole = whole.lstrip("-") or "0"
    return sign * (int(whole) * 100 + int(frac))


def _from_cents(value: int) -> str:
    sign = "-" if value < 0 else ""
    value = abs(value)
    return f"{sign}{value // 100}.{value % 100:02d}"
