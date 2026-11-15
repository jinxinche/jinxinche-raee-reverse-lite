"""Projection and pass rules for the extended stress tier.

The floors live in docs/a19/EXTENDED_TIER_BUDGET.json. A missing percentile
or a short count is not a pass.
"""

from __future__ import annotations

import math
from typing import Any


def percentiles(samples: list[float]) -> dict[str, Any]:
    if not samples:
        return {"sample_size": 0, "p50": None, "p95": None, "p99": None}
    ordered = sorted(samples)

    def pick(percent: float) -> float:
        rank = max(1, math.ceil(percent / 100.0 * len(ordered)))
        return ordered[rank - 1]

    return {
        "sample_size": len(ordered),
        "p50": pick(50),
        "p95": pick(95),
        "p99": pick(99),
    }


def _rate(count: int, seconds: float) -> float | None:
    if count <= 0 or seconds <= 0:
        return None
    return count / seconds


def project(measurements: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
    """Project a full extended run from a finished probe. Does not start one."""
    probe = budget["probe"]
    scale = budget["scale"]
    rules = budget["projection"]
    cap = budget["start_only_if"]
    finished = bool(measurements.get("finished"))
    claim_rate = _rate(int(measurements.get("claims") or 0), float(measurements.get("claim_seconds") or 0))
    observation_rate = _rate(
        int(measurements.get("observations") or 0), float(measurements.get("observation_seconds") or 0)
    )
    support_rate = _rate(
        int(measurements.get("last_support_count") or 0), float(measurements.get("last_support_seconds") or 0)
    )
    derived_rate = _rate(
        int(measurements.get("derived_from") or 0), float(measurements.get("derived_seconds") or 0)
    )
    rates = {
        "claims_per_second": claim_rate,
        "observations_per_second": observation_rate,
        "supports_per_second": support_rate,
        "derived_from_per_second": derived_rate,
    }
    reason = None
    raw_load = None
    if not finished:
        reason = "probe did not finish inside its time and directory stop"
    elif None in rates.values():
        reason = "a measured rate is missing"
    else:
        raw_load = (
            scale["claims"] / claim_rate
            + scale["observations"] / observation_rate
            + scale["supports"] / support_rate
            + scale["derived_from"] / derived_rate
        )
    safety = float(rules["load_safety_factor"])
    projected_load = None if raw_load is None else raw_load * safety
    projected_seconds = None
    if projected_load is not None:
        projected_seconds = projected_load + float(rules["mixed_seconds"]) + float(rules["setup_seconds"])
    probe_records = int(probe["claims"]) + int(probe["observations"]) + int(probe["supports"]) + int(probe["derived_from"])
    full_records = (
        int(scale["claims"]) + int(scale["observations"]) + int(scale["supports"]) + int(scale["derived_from"])
    )
    directory = None
    probe_bytes = measurements.get("directory_bytes")
    if finished and isinstance(probe_bytes, int) and probe_bytes >= 0 and probe_records > 0:
        directory = int(probe_bytes * (full_records / probe_records) * float(rules["directory_safety_factor"]))
    elif finished:
        reason = reason or "probe directory size is missing"
    start = (
        reason is None
        and projected_seconds is not None
        and directory is not None
        and projected_seconds <= float(cap["projected_seconds_at_most"])
        and directory <= int(cap["projected_directory_bytes_at_most"])
    )
    if not start and reason is None:
        reason = "projection is outside the declared cap"
    return {
        "finished_probe": finished,
        "rates": rates,
        "raw_load_seconds": raw_load,
        "projected_load_seconds": projected_load,
        "projected_seconds": projected_seconds,
        "projected_directory_bytes": directory,
        "start_allowed": bool(start),
        "reason": None if start else reason,
        "pass": False,
    }


def extended_pass(observed: dict[str, Any], budget: dict[str, Any]) -> bool:
    scale = budget["scale"]
    latency = observed.get("latency") if isinstance(observed.get("latency"), dict) else {}
    load = latency.get("load_inserts") if isinstance(latency.get("load_inserts"), dict) else {}
    mixed = latency.get("mixed_operations") if isinstance(latency.get("mixed_operations"), dict) else {}
    levels = observed.get("concurrency_levels")
    return bool(
        int(observed.get("claims") or 0) >= int(scale["claims"])
        and int(observed.get("observations") or 0) >= int(scale["observations"])
        and int(observed.get("relations") or 0) >= int(scale["relations"])
        and observed.get("integrity_ok") is True
        and observed.get("retraction_before_accepted_pass") is True
        and observed.get("retraction_after_accepted_pass") is False
        and observed.get("cancelled_state") == "CANCELLED"
        and observed.get("cancelled_state") != "SUCCEEDED"
        and float(observed.get("mixed_seconds") or 0) >= float(budget["mixed_seconds_minimum"])
        and levels == list(budget["concurrency_levels"])
        and int(observed.get("target_runs") or 0) >= int(budget["target_runs"])
        and observed.get("target_stdout_ok") is True
        and observed.get("target_accepted_pass_false") is True
        and int(observed.get("directory_bytes") or 0) <= int(budget["directory_cap_bytes"])
        and int(load.get("sample_size") or 0) >= 1
        and load.get("p50") is not None
        and load.get("p95") is not None
        and load.get("p99") is not None
        and int(mixed.get("sample_size") or 0) >= 1
        and mixed.get("p50") is not None
        and mixed.get("p95") is not None
        and mixed.get("p99") is not None
        and observed.get("interleaved") is True
        and observed.get("load_stopped_early") is not True
    )
