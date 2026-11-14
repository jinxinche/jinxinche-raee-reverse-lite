"""Standard tier declared in docs/a19/STANDARD_TIER_BUDGET.md.

Stops without a pass if the ledger directory exceeds 2 GiB.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.report_html import render_html  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402
from raee_reverse.store import Store  # noqa: E402

SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["standard-tier-row"],
    "environments": ["this-process"],
    "complete_output": True,
}
CAP_BYTES = 2 * 1024 * 1024 * 1024


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
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    elf = Path(sys.argv[3])
    root.mkdir(parents=True, exist_ok=True)
    store = Store(root / "ledger")
    started = time.perf_counter()
    report: dict = {
        "budget_document": "docs/a19/STANDARD_TIER_BUDGET.md",
        "standard_tier_executed": False,
        "standard_tier_pass": False,
    }
    try:
        claims = []
        observations = []
        for index in range(1000):
            claims.append(store.add_record(
                kind="claim",
                payload={"statement": f"tier claim {index}", "required_scope": dict(SCOPE)},
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            ))
        for index in range(10000):
            observations.append(store.add_record(
                kind="observation",
                payload={
                    "summary": f"tier obs {index}",
                    "truncated": False,
                    "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"},
                },
                provenance="observed",
                execution_result="passed",
                applicability="valid",
                usage="support",
                verification_scope=dict(SCOPE),
                source_family=f"tier-obs-{index}",
            ))
        relations = 0
        for index, observation in enumerate(observations):
            store.add_relation(
                "supports",
                observation,
                claims[index % 1000],
                {"statement": "tier support", "method": "explicit"},
            )
            relations += 1
            if dir_size(root) > CAP_BYTES:
                raise RuntimeError("ledger directory exceeded 2 GiB")
        while relations < 50000:
            store.add_relation(
                "derived_from",
                observations[relations % 10000],
                observations[(relations + 1) % 10000],
                {"statement": "tier derived link", "method": "explicit"},
            )
            relations += 1
            if relations % 5000 == 0 and dir_size(root) > CAP_BYTES:
                raise RuntimeError("ledger directory exceeded 2 GiB")
        load_seconds = time.perf_counter() - started

        # Dedicated retraction check.
        lone_obs = store.add_record(
            kind="observation",
            payload={"summary": "retract me", "truncated": False, "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"}},
            provenance="observed",
            execution_result="passed",
            applicability="valid",
            usage="support",
            verification_scope=dict(SCOPE),
            source_family="retract-source",
        )
        lone_claim = store.add_record(
            kind="claim",
            payload={"statement": "retraction check", "required_scope": dict(SCOPE)},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope=dict(SCOPE),
        )
        store.add_relation("supports", lone_obs, lone_claim, {"statement": "only support", "method": "explicit"})
        store.add_relation(
            "depends_on", lone_claim, lone_obs,
            {"statement": "necessary", "method": "explicit"},
            role="necessary",
        )
        before = store.decision(lone_claim)["accepted_pass"]
        store.retract(lone_obs, "standard-tier retraction")
        after = store.decision(lone_claim)["accepted_pass"]

        target_runs = []
        for index in range(20):
            result = run_sandboxed([str(elf)], work_dir=root / f"run-{index}", stdin=b"abc", timeout=10, cpu_seconds=5)
            target_runs.append({
                "index": index,
                "execution_result": result["execution_result"],
                "returncode": result["returncode"],
                "stdout": result["stdout"].decode("utf-8", "replace"),
                "accepted_pass": result["accepted_pass"],
            })

        # Cancel a task and keep it from succeeding.
        store.submit_task(
            task_id="tier-cancel",
            handler="sleep_long",
            deps=[],
            owner="standard-tier",
            inputs_version="tier",
            timeout_seconds=30,
            max_attempts=1,
            resource_class="dev",
        )
        store.request_cancel("tier-cancel")
        cancelled_state = store.get_task("tier-cancel")["state"]

        def readers(level: int) -> None:
            threads = []
            def read() -> None:
                store.decision(claims[0])
                store.list_records("claim")
            for _ in range(level):
                thread = threading.Thread(target=read)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()

        for level in (1, 2, 4, 8, 16):
            readers(level)

        mixed_started = time.perf_counter()
        iterations = 0
        next_heartbeat = mixed_started + 60
        while time.perf_counter() - mixed_started < 1800:
            store.decision(claims[iterations % 1000])
            if iterations % 10 == 0:
                render_html(store)
            if iterations % 50 == 0:
                store.list_events()
            iterations += 1
            now = time.perf_counter()
            if now >= next_heartbeat:
                print(json.dumps({"heartbeat_s": round(now - mixed_started, 1), "iterations": iterations}), flush=True)
                next_heartbeat = now + 60
            if dir_size(root) > CAP_BYTES:
                raise RuntimeError("ledger directory exceeded 2 GiB during the mixed phase")
            time.sleep(0.05)
        mixed_seconds = time.perf_counter() - mixed_started
        store.verify_integrity()
        counts = store.status_summary()["record_counts"]
        relation_count = len(store.list_relations())
        passed = (
            counts.get("claim", 0) >= 1000
            and counts.get("observation", 0) >= 10000
            and relation_count >= 50000
            and before is True
            and after is False
            and cancelled_state == "CANCELLED"
            and len(target_runs) == 20
            and all(row["execution_result"] == "passed" and row["stdout"] == "count=3 sum=294\n" and row["accepted_pass"] is False for row in target_runs)
            and mixed_seconds >= 1800
            and dir_size(root) <= CAP_BYTES
        )
        report.update({
            "standard_tier_executed": True,
            "standard_tier_pass": passed,
            "load_seconds": load_seconds,
            "mixed_seconds": mixed_seconds,
            "iterations": iterations,
            "record_counts": counts,
            "relation_count": relation_count,
            "retraction_before_accepted_pass": before,
            "retraction_after_accepted_pass": after,
            "cancelled_state": cancelled_state,
            "target_runs": len(target_runs),
            "target_stdout_ok": all(row["stdout"] == "count=3 sum=294\n" for row in target_runs),
            "directory_bytes": dir_size(root),
            "integrity_ok": True,
        })
    except Exception as exc:
        report.update({
            "standard_tier_executed": False,
            "standard_tier_pass": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": time.perf_counter() - started,
        })
    finally:
        store.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "record_counts"}))
    return 0 if report.get("standard_tier_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
