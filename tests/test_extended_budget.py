"""The extended-tier floors are fixed before a run. A short result is not a pass."""

import json
from pathlib import Path

from raee_reverse.stress_budget import extended_pass, percentiles, project

REPO = Path(__file__).resolve().parents[1]
BUDGET = json.loads((REPO / "docs" / "a19" / "EXTENDED_TIER_BUDGET.json").read_text(encoding="utf-8"))


def _full():
    return {
        "claims": 10000,
        "observations": 100000,
        "relations": 250000,
        "integrity_ok": True,
        "retraction_before_accepted_pass": True,
        "retraction_after_accepted_pass": False,
        "cancelled_state": "CANCELLED",
        "mixed_seconds": 1800,
        "concurrency_levels": [1, 2, 4, 8, 16],
        "target_runs": 20,
        "target_stdout_ok": True,
        "target_accepted_pass_false": True,
        "directory_bytes": 1000,
        "latency": {
            "load_inserts": {"sample_size": 3, "p50": 0.1, "p95": 0.2, "p99": 0.3},
            "mixed_operations": {"sample_size": 3, "p50": 0.1, "p95": 0.2, "p99": 0.3},
        },
        "interleaved": True,
        "load_stopped_early": False,
    }


def test_budget_floors_match_the_declared_scale():
    assert BUDGET["declared_before_probe"] is True
    assert BUDGET["scale"]["claims"] == 10000
    assert BUDGET["scale"]["observations"] == 100000
    assert BUDGET["scale"]["relations"] == 250000
    assert BUDGET["mixed_seconds_minimum"] == 1800
    assert BUDGET["start_only_if"]["projected_seconds_at_most"] == 4200


def test_percentiles_use_the_sample_size():
    found = percentiles([0.1, 0.2, 0.3, 0.4])
    assert found["sample_size"] == 4
    assert found["p50"] == 0.2
    assert found["p99"] == 0.4
    assert percentiles([])["sample_size"] == 0


def test_short_or_partial_result_is_not_a_pass():
    assert extended_pass(_full(), BUDGET) is True
    short = _full()
    short["relations"] = 10041
    assert extended_pass(short, BUDGET) is False
    missing = _full()
    missing["latency"] = {"load_inserts": {"sample_size": 0, "p50": None, "p95": None, "p99": None}, "mixed_operations": missing["latency"]["mixed_operations"]}
    assert extended_pass(missing, BUDGET) is False
    early = _full()
    early["load_stopped_early"] = True
    assert extended_pass(early, BUDGET) is False


def test_projection_outside_the_cap_does_not_start():
    slow = {
        "finished": True,
        "claims": 100,
        "claim_seconds": 100,
        "observations": 1000,
        "observation_seconds": 100,
        "last_support_count": 100,
        "last_support_seconds": 100,
        "derived_from": 500,
        "derived_seconds": 100,
        "directory_bytes": 1000,
    }
    refused = project(slow, BUDGET)
    assert refused["start_allowed"] is False
    assert refused["pass"] is False
    fast = {
        "finished": True,
        "claims": 100,
        "claim_seconds": 0.1,
        "observations": 1000,
        "observation_seconds": 0.2,
        "last_support_count": 100,
        "last_support_seconds": 0.05,
        "derived_from": 500,
        "derived_seconds": 0.1,
        "directory_bytes": 1000,
    }
    allowed = project(fast, BUDGET)
    assert allowed["start_allowed"] is True
    assert allowed["projected_seconds"] <= 4200
    unfinished = dict(fast)
    unfinished["finished"] = False
    assert project(unfinished, BUDGET)["start_allowed"] is False
