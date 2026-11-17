"""Probe the extended tier. Does not start the full tier.

The budget file is the authority. This script only writes the projection.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.store import Store  # noqa: E402
from raee_reverse.stress_budget import project  # noqa: E402

SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["extended-probe"],
    "environments": ["this-process"],
    "complete_output": True,
}


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


def main() -> int:
    budget = json.loads((REPO / "docs" / "a19" / "EXTENDED_TIER_BUDGET.json").read_text(encoding="utf-8"))
    root = Path(sys.argv[1] if len(sys.argv) > 1 else budget["probe"]["directory"])
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/a19-extended-probe.json")
    shape = budget["probe"]
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root / "ledger")
    started = time.perf_counter()
    measurements = {
        "finished": False,
        "claims": 0,
        "observations": 0,
        "supports": 0,
        "derived_from": 0,
        "claim_seconds": 0.0,
        "observation_seconds": 0.0,
        "support_seconds": 0.0,
        "derived_seconds": 0.0,
        "last_support_count": 0,
        "last_support_seconds": 0.0,
        "directory_bytes": 0,
        "stop_reason": None,
    }
    try:
        def over() -> bool:
            if time.perf_counter() - started > float(shape["stop_seconds"]):
                measurements["stop_reason"] = "time"
                return True
            if dir_size(root) > int(shape["stop_directory_bytes"]):
                measurements["stop_reason"] = "directory"
                return True
            return False

        claims = []
        mark = time.perf_counter()
        for index in range(int(shape["claims"])):
            if over():
                break
            claims.append(store.add_record(
                kind="claim",
                payload={"statement": f"probe claim {index}", "required_scope": dict(SCOPE)},
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            ))
        measurements["claim_seconds"] = time.perf_counter() - mark
        measurements["claims"] = len(claims)
        observations = []
        mark = time.perf_counter()
        for index in range(int(shape["observations"])):
            if over():
                break
            observations.append(store.add_record(
                kind="observation",
                payload={"summary": f"probe obs {index}", "truncated": False, "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"}},
                provenance="observed",
                execution_result="passed",
                applicability="valid",
                usage="support",
                verification_scope=dict(SCOPE),
                source_family=f"probe-obs-{index}",
            ))
        measurements["observation_seconds"] = time.perf_counter() - mark
        measurements["observations"] = len(observations)
        mark = time.perf_counter()
        last_mark = None
        supports = 0
        target_supports = int(shape["supports"])
        for index in range(target_supports):
            if over():
                break
            if index == target_supports - 100:
                last_mark = time.perf_counter()
            store.add_relation(
                "supports",
                observations[index % len(observations)],
                claims[index % len(claims)],
                {"statement": "probe support", "method": "explicit"},
            )
            supports += 1
        measurements["support_seconds"] = time.perf_counter() - mark
        measurements["supports"] = supports
        if last_mark is not None and supports == target_supports:
            measurements["last_support_count"] = 100
            measurements["last_support_seconds"] = time.perf_counter() - last_mark
        mark = time.perf_counter()
        derived = 0
        for index in range(int(shape["derived_from"])):
            if over():
                break
            store.add_relation(
                "derived_from",
                observations[index % len(observations)],
                observations[(index + 1) % len(observations)],
                {"statement": "probe derived", "method": "explicit"},
            )
            derived += 1
        measurements["derived_seconds"] = time.perf_counter() - mark
        measurements["derived_from"] = derived
        measurements["directory_bytes"] = dir_size(root)
        measurements["finished"] = (
            measurements["stop_reason"] is None
            and measurements["claims"] == int(shape["claims"])
            and measurements["observations"] == int(shape["observations"])
            and measurements["supports"] == int(shape["supports"])
            and measurements["derived_from"] == int(shape["derived_from"])
        )
    finally:
        store.close()
    projected = project(measurements, budget)
    report = {
        "budget_document": "docs/a19/EXTENDED_TIER_BUDGET.json",
        "measurements": measurements,
        "projection": projected,
        "start_allowed": projected["start_allowed"],
        "projected_load_seconds": projected["projected_load_seconds"],
        "projected_seconds": projected["projected_seconds"],
        "extended_tier_pass": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "start_allowed": report["start_allowed"],
        "projected_seconds": report["projected_seconds"],
        "projected_load_seconds": report["projected_load_seconds"],
        "reason": projected["reason"],
        "elapsed_seconds": report["elapsed_seconds"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
