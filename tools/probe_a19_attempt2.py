"""Bounded probe declared in docs/a19/ATTEMPT2_BUDGET.md. Not the standard tier."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path("/workspace")
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.store import Store  # noqa: E402

SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["standard-tier-row"],
    "environments": ["this-process"],
    "complete_output": True,
}
ROOT = Path("/tmp/a19-attempt2")
CAP_BYTES = 256 * 1024 * 1024
RELATION_SECONDS = 90.0
FULL_RELATIONS = 50000
MIXED_SECONDS = 1800
SESSION_CAP = 2700


def dir_size(path: Path) -> int:
    total = 0
    for current, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(current) / name).stat().st_size
            except OSError:
                pass
    return total


def main() -> int:
    if ROOT.exists():
        raise SystemExit(f"refusing to reuse {ROOT}")
    ROOT.mkdir(parents=True)
    store = Store(ROOT / "ledger")
    claims = []
    observations = []
    for index in range(100):
        claims.append(store.add_record(
            kind="claim",
            payload={"statement": f"probe claim {index}", "required_scope": dict(SCOPE)},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope=dict(SCOPE),
        ))
    for index in range(500):
        observations.append(store.add_record(
            kind="observation",
            payload={
                "summary": f"probe obs {index}",
                "truncated": False,
                "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"},
            },
            provenance="observed",
            execution_result="passed",
            applicability="valid",
            usage="support",
            verification_scope=dict(SCOPE),
            source_family=f"probe-obs-{index}",
        ))
    setup_done = time.perf_counter()
    stamps = []
    relations = 0
    stop_reason = "completed-requested-supports"
    started = time.perf_counter()
    while relations < 2000:
        if time.perf_counter() - started >= RELATION_SECONDS:
            stop_reason = "relation_seconds"
            break
        if relations % 50 == 0 and dir_size(ROOT) > CAP_BYTES:
            stop_reason = "directory_cap"
            break
        store.add_relation(
            "supports",
            observations[relations % 500],
            claims[relations % 100],
            {"statement": "probe support", "method": "explicit"},
        )
        relations += 1
        if relations % 100 == 0:
            stamps.append({"relations": relations, "seconds": time.perf_counter() - started})
    elapsed = time.perf_counter() - started
    if relations >= 100:
        last = stamps[-1]["seconds"] - stamps[-2]["seconds"] if len(stamps) >= 2 else elapsed
        last_relations = 100
        last_rate = last_relations / last if last else None
    else:
        last = elapsed
        last_rate = None
    # Linear scaling from the last-100 rate through 50,000 relations.
    if last_rate:
        # cost per relation at the measured point, then sum n * unit from current to 50000
        # Budget rule: "scaled linearly by relation count from that rate through 50,000"
        # Interpret as: time = (50000 / measured_rate) * (50000 / relations_at_measurement) / 2
        # The declaration says: "the last 100 supports, scaled linearly by relation count
        # from that rate through 50,000 relations"
        # Practical reading used here: seconds per relation grows in proportion to relation
        # count, anchored at the last-100 measurement.
        anchor = relations
        seconds_per_relation = 1.0 / last_rate
        # integral_{anchor}^{50000} (n / anchor) * seconds_per_relation dn
        span = FULL_RELATIONS - anchor
        projected_remaining = seconds_per_relation * (FULL_RELATIONS + anchor) / (2 * anchor) * span
        projected_total = projected_remaining + MIXED_SECONDS
    else:
        projected_remaining = None
        projected_total = None
    start_full = bool(projected_total is not None and projected_total <= SESSION_CAP)
    counts = store.status_summary()["record_counts"]
    store.close()
    report = {
        "budget_document": "docs/a19/ATTEMPT2_BUDGET.md",
        "standard_tier_executed": False,
        "standard_tier_pass": False,
        "full_tier_started": False,
        "start_full_tier": start_full,
        "stop_reason": stop_reason,
        "relations": relations,
        "relation_seconds": elapsed,
        "setup_seconds_before_relations": setup_done and None,
        "last_100_seconds": last,
        "last_100_relations_per_second": last_rate,
        "projected_remaining_load_seconds": projected_remaining,
        "projected_load_plus_1800_seconds": projected_total,
        "session_cap_seconds": SESSION_CAP,
        "record_counts": counts,
        "directory_bytes": dir_size(ROOT),
        "stamps": stamps,
        "previous_failure_unchanged": "docs/a19/standard_tier.json",
        "mixed_phase_ran": False,
        "target_runs": 0,
    }
    # setup_seconds was measured incorrectly above; fix with stored start relative.
    report["setup_note"] = "setup records were inserted before relation_seconds"
    out = Path("/tmp/a19-attempt2-result.json")
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "relations", "relation_seconds", "stop_reason", "last_100_relations_per_second",
        "projected_remaining_load_seconds", "projected_load_plus_1800_seconds",
        "start_full_tier", "directory_bytes", "record_counts", "standard_tier_pass",
    )}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
