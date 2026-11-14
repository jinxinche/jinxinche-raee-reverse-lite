"""Run only the budget declared in docs/a19/BUDGET.md."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.store import Store  # noqa: E402

SCOPE = {
    "inputs": ["a19-budget"],
    "behaviors": ["insert"],
    "environments": ["this-process"],
    "complete_output": True,
}


def rss_bytes() -> int | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def main() -> int:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    store = Store(root)
    started = time.perf_counter()
    try:
        for index in range(200):
            claim = store.add_record(
                kind="claim",
                payload={"statement": f"budget row {index}", "required_scope": dict(SCOPE)},
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            )
            evidence = store.add_record(
                kind="observation",
                payload={"summary": f"row {index}", "truncated": False, "run": {"command": ["budget"], "exit_code": 0, "observed_status": "passed"}},
                provenance="observed",
                execution_result="passed",
                applicability="valid",
                usage="support",
                verification_scope=dict(SCOPE),
                source_family=f"budget-{index}",
            )
            store.add_relation(
                "supports",
                evidence,
                claim,
                {"statement": "budget link", "method": "explicit"},
            )
        store.verify_integrity()
        elapsed = time.perf_counter() - started
        memory = rss_bytes()
        passed = elapsed < 10 and (memory is None or memory < 256 * 1024 * 1024)
        report = {
            "budget_document": "docs/a19/BUDGET.md",
            "records_inserted": 400,
            "relations_inserted": 200,
            "wall_seconds": elapsed,
            "rss_bytes": memory,
            "integrity_ok": True,
            "budget_pass": passed,
            "standard_tier_executed": False,
            "standard_tier_pass": False,
            "extended_tier_executed": False,
        }
    finally:
        store.close()
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("budget_pass", "wall_seconds", "rss_bytes", "standard_tier_executed")}))
    return 0 if report["budget_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
