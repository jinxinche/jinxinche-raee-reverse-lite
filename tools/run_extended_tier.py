"""Extended tier declared in docs/a19/EXTENDED_TIER_BUDGET.json.

Starts only when the probe says start_allowed. A load that exceeds the
projected load seconds stops before the mixed phase and is not a pass.
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
from raee_reverse.stress_budget import extended_pass, percentiles  # noqa: E402

SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["extended-tier-row"],
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
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    elf = Path(sys.argv[3])
    probe = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
    root.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "budget_document": "docs/a19/EXTENDED_TIER_BUDGET.json",
        "probe_start_allowed": bool(probe.get("start_allowed")),
        "extended_tier_executed": False,
        "extended_tier_pass": False,
        "load_stopped_early": False,
    }
    if not probe.get("start_allowed"):
        report["reason"] = "probe did not allow the full tier"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"extended_tier_pass": False, "reason": report["reason"]}))
        return 1
    projected_load = float(probe["projected_load_seconds"])
    cap = int(budget["directory_cap_bytes"])
    scale = budget["scale"]
    store = Store(root / "ledger")
    started = time.perf_counter()
    load_latencies: list[float] = []
    try:
        def too_big() -> None:
            if dir_size(root) > cap:
                raise RuntimeError("ledger directory exceeded 4 GiB")

        def timed(function):
            mark = time.perf_counter()
            value = function()
            load_latencies.append(time.perf_counter() - mark)
            return value

        claims = []
        for index in range(int(scale["claims"])):
            claims.append(timed(lambda index=index: store.add_record(
                kind="claim",
                payload={"statement": f"extended claim {index}", "required_scope": dict(SCOPE)},
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            )))
            if index % 2000 == 0:
                too_big()
                if time.perf_counter() - started > projected_load:
                    report["load_stopped_early"] = True
                    raise RuntimeError("load exceeded the projected load seconds")
        observations = []
        for index in range(int(scale["observations"])):
            observations.append(timed(lambda index=index: store.add_record(
                kind="observation",
                payload={
                    "summary": f"extended obs {index}",
                    "truncated": False,
                    "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"},
                },
                provenance="observed",
                execution_result="passed",
                applicability="valid",
                usage="support",
                verification_scope=dict(SCOPE),
                source_family=f"extended-obs-{index}",
            )))
            if index % 5000 == 0:
                too_big()
                if time.perf_counter() - started > projected_load:
                    report["load_stopped_early"] = True
                    raise RuntimeError("load exceeded the projected load seconds")
        relations = 0
        for index in range(int(scale["supports"])):
            timed(lambda index=index: store.add_relation(
                "supports",
                observations[index % len(observations)],
                claims[index % len(claims)],
                {"statement": "extended support", "method": "explicit"},
            ))
            relations += 1
            if relations % 5000 == 0:
                too_big()
                if time.perf_counter() - started > projected_load:
                    report["load_stopped_early"] = True
                    raise RuntimeError("load exceeded the projected load seconds")
                print(json.dumps({"phase": "supports", "relations": relations}), flush=True)
        derived_target = int(scale["derived_from"])
        for index in range(derived_target):
            timed(lambda index=index: store.add_relation(
                "derived_from",
                observations[index % len(observations)],
                observations[(index + 1) % len(observations)],
                {"statement": "extended derived link", "method": "explicit"},
            ))
            relations += 1
            if index % 5000 == 0:
                too_big()
                if time.perf_counter() - started > projected_load:
                    report["load_stopped_early"] = True
                    raise RuntimeError("load exceeded the projected load seconds")
                print(json.dumps({"phase": "derived", "relations": relations}), flush=True)
        load_seconds = time.perf_counter() - started
        if load_seconds > projected_load:
            report["load_stopped_early"] = True
            raise RuntimeError("load exceeded the projected load seconds")

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
        store.retract(lone_obs, "extended-tier retraction")
        after = store.decision(lone_claim)["accepted_pass"]

        extra_obs = store.add_record(
            kind="observation",
            payload={"summary": "interleaved retract", "truncated": False, "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"}},
            provenance="observed",
            execution_result="passed",
            applicability="valid",
            usage="support",
            verification_scope=dict(SCOPE),
            source_family="interleaved-retract",
        )
        extra_claim = store.add_record(
            kind="claim",
            payload={"statement": "interleaved retraction", "required_scope": dict(SCOPE)},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope=dict(SCOPE),
        )
        store.add_relation("supports", extra_obs, extra_claim, {"statement": "only support", "method": "explicit"})
        store.add_relation(
            "depends_on", extra_claim, extra_obs,
            {"statement": "necessary", "method": "explicit"},
            role="necessary",
        )

        target_runs = []
        for index in range(int(budget["target_runs"])):
            result = run_sandboxed([str(elf)], work_dir=root / f"run-{index}", stdin=b"abc", timeout=10, cpu_seconds=5)
            target_runs.append({
                "index": index,
                "execution_result": result["execution_result"],
                "returncode": result["returncode"],
                "stdout": result["stdout"].decode("utf-8", "replace"),
                "accepted_pass": result["accepted_pass"],
            })

        store.submit_task(
            task_id="extended-cancel",
            handler="sleep_long",
            deps=[],
            owner="extended-tier",
            inputs_version="extended",
            timeout_seconds=30,
            max_attempts=1,
            resource_class="dev",
        )
        store.request_cancel("extended-cancel")
        cancelled_state = store.get_task("extended-cancel")["state"]

        def readers(level: int) -> None:
            threads = []

            def read() -> None:
                store.decision(claims[0])

            for _ in range(level):
                thread = threading.Thread(target=read)
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()

        levels = []
        for level in budget["concurrency_levels"]:
            readers(int(level))
            levels.append(int(level))

        mixed_latencies: list[float] = []
        mixed_started = time.perf_counter()
        iterations = 0
        next_heartbeat = mixed_started + 60
        interleaved = {"query": False, "report": False, "write": False, "retract": False, "cancel": False}
        while time.perf_counter() - mixed_started < float(budget["mixed_seconds_minimum"]):
            mark = time.perf_counter()
            store.decision(claims[iterations % len(claims)])
            mixed_latencies.append(time.perf_counter() - mark)
            interleaved["query"] = True
            if iterations % 10 == 0:
                mark = time.perf_counter()
                render_html(store)
                mixed_latencies.append(time.perf_counter() - mark)
                interleaved["report"] = True
            if iterations % 50 == 0:
                mark = time.perf_counter()
                store.list_events()
                mixed_latencies.append(time.perf_counter() - mark)
            if iterations % 400 == 0:
                mark = time.perf_counter()
                store.add_record(
                    kind="observation",
                    payload={"summary": f"mixed {iterations}", "truncated": False, "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"}},
                    provenance="observed",
                    execution_result="passed",
                    applicability="valid",
                    usage="background",
                    verification_scope=dict(SCOPE),
                    source_family=f"mixed-{iterations}",
                )
                mixed_latencies.append(time.perf_counter() - mark)
                interleaved["write"] = True
            if iterations == 30:
                store.retract(extra_obs, "interleaved retraction")
                interleaved["retract"] = store.decision(extra_claim)["accepted_pass"] is False
            if iterations == 60:
                store.submit_task(
                    task_id="extended-cancel-mixed",
                    handler="sleep_long",
                    deps=[],
                    owner="extended-tier",
                    inputs_version="extended",
                    timeout_seconds=30,
                    max_attempts=1,
                    resource_class="dev",
                )
                store.request_cancel("extended-cancel-mixed")
                interleaved["cancel"] = store.get_task("extended-cancel-mixed")["state"] == "CANCELLED"
            iterations += 1
            now = time.perf_counter()
            if now >= next_heartbeat:
                print(json.dumps({"heartbeat_s": round(now - mixed_started, 1), "iterations": iterations}), flush=True)
                next_heartbeat = now + 60
                if dir_size(root) > cap:
                    raise RuntimeError("ledger directory exceeded 4 GiB during the mixed phase")
            time.sleep(0.05)
        mixed_seconds = time.perf_counter() - mixed_started
        store.verify_integrity()
        counts = store.status_summary()["record_counts"]
        relation_count = len(store.list_relations())
        observed = {
            "claims": counts.get("claim", 0),
            "observations": counts.get("observation", 0),
            "relations": relation_count,
            "integrity_ok": True,
            "retraction_before_accepted_pass": before,
            "retraction_after_accepted_pass": after,
            "cancelled_state": cancelled_state,
            "mixed_seconds": mixed_seconds,
            "concurrency_levels": levels,
            "target_runs": len(target_runs),
            "target_stdout_ok": all(row["stdout"] == budget["expected_stdout"] and row["execution_result"] == "passed" for row in target_runs),
            "target_accepted_pass_false": all(row["accepted_pass"] is False for row in target_runs),
            "directory_bytes": dir_size(root),
            "latency": {
                "load_inserts": percentiles(load_latencies),
                "mixed_operations": percentiles(mixed_latencies),
            },
            "interleaved": all(interleaved.values()),
            "load_stopped_early": False,
        }
        passed = extended_pass(observed, budget)
        report.update({
            "extended_tier_executed": True,
            "extended_tier_pass": passed,
            "load_seconds": load_seconds,
            "mixed_seconds": mixed_seconds,
            "iterations": iterations,
            "record_counts": counts,
            "relation_count": relation_count,
            "retraction_before_accepted_pass": before,
            "retraction_after_accepted_pass": after,
            "cancelled_state": cancelled_state,
            "target_runs": len(target_runs),
            "target_stdout_ok": observed["target_stdout_ok"],
            "target_accepted_pass_false": observed["target_accepted_pass_false"],
            "directory_bytes": observed["directory_bytes"],
            "integrity_ok": True,
            "latency": observed["latency"],
            "interleaved": interleaved,
            "concurrency_levels": levels,
            "load_stopped_early": False,
        })
    except Exception as exc:
        report.update({
            "extended_tier_executed": False,
            "extended_tier_pass": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": time.perf_counter() - started,
        })
    finally:
        store.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {key: report[key] for key in report if key not in {"record_counts", "latency"}}
    summary["latency_sample_sizes"] = {
        "load_inserts": (report.get("latency") or {}).get("load_inserts", {}).get("sample_size"),
        "mixed_operations": (report.get("latency") or {}).get("mixed_operations", {}).get("sample_size"),
    }
    print(json.dumps(summary))
    return 0 if report.get("extended_tier_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
