"""Score REA and this tool on the same runtime tasks.

A side that did not return an observation is not a scored pair. Model cost
stays unknown when no usage report exists. This module does not rank products.
"""

from __future__ import annotations

from typing import Any

TASKS = (
    {"id": "abc", "stdin_hex": "616263", "stdout": "count=3 sum=294\n"},
    {"id": "empty", "stdin_hex": "", "stdout": "count=0 sum=0\n"},
    {"id": "a", "stdin_hex": "61", "stdout": "count=1 sum=97\n"},
    {"id": "hello", "stdin_hex": "68656c6c6f", "stdout": "count=5 sum=532\n"},
)


def stdin_bytes(task: dict[str, str]) -> bytes:
    text = task["stdin_hex"]
    return bytes.fromhex(text) if text else b""


def score_observation(expected_stdout: str, stdout: str | None, returncode: int | None) -> dict[str, Any]:
    observed = stdout is not None and returncode is not None
    correct = bool(observed and stdout == expected_stdout and returncode == 0)
    return {"observed": observed, "correct": correct, "returncode": returncode}


def summarize_pairs(rows: list[dict[str, Any]], *, model_cost: dict[str, Any]) -> dict[str, Any]:
    scored = [row for row in rows if row["rea"]["observed"] and row["this_tool"]["observed"]]
    complete = len(scored) == len(rows) and len(rows) > 0
    if model_cost.get("status") != "known":
        model_cost = {
            "status": "unknown",
            "amount": None,
            "reason": model_cost.get("reason") or "no usage report",
        }
    if not complete:
        metrics = {
            "correct_completion_rate": "not_collected",
            "rea_correct_completion_rate": "not_collected",
            "this_tool_correct_completion_rate": "not_collected",
            "coverage": "not_collected",
            "time_to_correct_result": "not_collected",
            "model_cost": "not_collected",
            "resource_cost": "not_collected",
        }
    else:
        rea_correct = sum(1 for row in scored if row["rea"]["correct"])
        tool_correct = sum(1 for row in scored if row["this_tool"]["correct"])
        both_correct = sum(1 for row in scored if row["rea"]["correct"] and row["this_tool"]["correct"])
        metrics = {
            "correct_completion_rate": both_correct / len(scored),
            "rea_correct_completion_rate": rea_correct / len(scored),
            "this_tool_correct_completion_rate": tool_correct / len(scored),
            "coverage": 1.0,
            "time_to_correct_result": [
                row.get("rea_seconds") for row in scored if row["rea"]["correct"]
            ],
            "model_cost": model_cost,
            "resource_cost": "wall seconds are on each row; no other resource meter was read",
        }
    return {
        "comparison_complete": complete,
        "executed": complete,
        "ranking": False,
        "promotes_static_sample": False,
        "sample_size_scored_pairs": len(scored),
        "declared_tasks": len(rows),
        "model_calls": 0,
        "model_cost": model_cost,
        "savings_percent": None,
        "metrics": metrics,
        "rows": rows,
    }
