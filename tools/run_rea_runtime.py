"""Attempt a runtime comparison with REA 6.9.0.

capture-process and one debug-with-gdb command are attempted. A run that does
not produce the contract line is not a completed comparison and is not a ranking.
The earlier static sample in docs/a18/REA_COMPARISON.md stays a sample of one.
"""

from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _which_rea() -> str | None:
    return shutil.which("rea")


def _capture(rea: str, elf: Path, work: Path) -> dict:
    scenario = {
        "executable": str(elf),
        "arguments": [],
        "working_directory": str(work),
        "events": [{"at_ms": 0, "type": "input", "data": "abc"}],
        "timeout_ms": 3000,
        "idle_timeout_ms": 1000,
        "settle_ms": 50,
        "finalization_ms": 0,
    }
    path = work / "scenario.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    started = time.perf_counter()
    completed = subprocess.run(
        [rea, "capture-process", str(path), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    elapsed = time.perf_counter() - started
    observed = ""
    exit_info = None
    if completed.stdout:
        try:
            payload = json.loads(completed.stdout)
            normalized = payload.get("normalized_result") or {}
            exit_info = normalized.get("exit")
            frames = normalized.get("rendered_frames") or []
            lines = []
            for frame in frames:
                for line in frame.get("lines") or []:
                    if line.strip():
                        lines.append(line)
            observed = "\n".join(lines)
        except json.JSONDecodeError:
            observed = completed.stdout[:500]
    return {
        "command": f"rea capture-process {path} --format json",
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "exit": exit_info,
        "rendered_nonempty_lines": observed,
        "contract_line_present": "count=3 sum=294" in observed,
        "stderr_tail": completed.stderr[-400:],
    }


def _gdb(rea: str, elf: Path, work: Path) -> dict:
    master, slave = pty.openpty()
    try:
        name = os.ttyname(slave)
        started = time.perf_counter()
        completed = subprocess.run(
            [rea, "debug-with-gdb", "run", "--inferior-tty", name, "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        elapsed = time.perf_counter() - started
    finally:
        os.close(master)
        os.close(slave)
    return {
        "command": "rea debug-with-gdb run --inferior-tty <pty> --format json",
        "note": "One GDB command cannot both load the ELF and redirect stdin. run with redirection is rejected. This call is run alone, so the session has no executable loaded.",
        "elf_not_passed": str(elf),
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_head": completed.stdout[:600],
        "contract_line_present": "count=3 sum=294" in completed.stdout,
    }


def main() -> int:
    work = Path(sys_argv_work())
    out = Path(sys_argv_out())
    elf = Path(sys_argv_elf())
    work.mkdir(parents=True, exist_ok=True)
    rea = _which_rea()
    version = None
    if rea:
        probed = subprocess.run([rea, "--version"], capture_output=True, text=True, check=False)
        version = probed.stdout.strip()
    report = {
        "comparison_complete": False,
        "executed": False,
        "attempts_executed": False,
        "ranking": False,
        "promotes_static_sample": False,
        "static_record": "docs/a18/REA_COMPARISON.md",
        "rea_version": version,
        "rea_path": rea,
        "gdb_version": None,
        "sample_size_scored_pairs": 0,
        "model_calls": 0,
        "model_cost": {"status": "unknown", "amount": None, "reason": "no usage report; no model endpoint was configured"},
        "metrics": {
            "correct_completion_rate": "not_collected",
            "unsupported_conclusion_rate": "not_collected",
            "coverage": "not_collected",
            "open_issues": "not_collected",
            "time_to_correct_result": "not_collected",
            "model_cost": "not_collected",
            "human_interventions": 0,
            "resource_cost": "not_collected",
        },
        "savings_percent": None,
    }
    gdb = subprocess.run(["gdb", "--version"], capture_output=True, text=True, check=False)
    report["gdb_version"] = gdb.stdout.splitlines()[0] if gdb.returncode == 0 and gdb.stdout else None
    report["rizin_on_path"] = shutil.which("rizin") is not None
    if rea is None or version != "6.9.0":
        report["reason"] = "rea 6.9.0 is not on PATH"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"comparison_complete": False, "reason": report["reason"]}))
        return 0
    capture = _capture(rea, elf, work)
    gdb_attempt = _gdb(rea, elf, work)
    report["attempts_executed"] = True
    report["attempts"] = {"capture_process": capture, "debug_with_gdb": gdb_attempt}
    report["comparison_complete"] = bool(capture["contract_line_present"] or gdb_attempt["contract_line_present"])
    report["executed"] = report["comparison_complete"]
    if not report["comparison_complete"]:
        report["reason"] = (
            "REA 6.9.0 ran. capture-process uses a PTY and idle-killed checksum_cli "
            "before it printed, because the program reads stdin until EOF and the PTY "
            "did not deliver EOF. debug-with-gdb accepts one command and rejects run "
            "with stdin redirection, so one command cannot load this ELF and feed abc. "
            "rizin is not on PATH. This is not a completed runtime comparison."
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "comparison_complete": report["comparison_complete"],
        "executed": report["executed"],
        "capture_contract": capture["contract_line_present"],
        "gdb_returncode": gdb_attempt["returncode"],
    }))
    return 0


def sys_argv_work() -> str:
    import sys
    return sys.argv[1]


def sys_argv_out() -> str:
    import sys
    return sys.argv[2]


def sys_argv_elf() -> str:
    import sys
    return sys.argv[3]


if __name__ == "__main__":
    raise SystemExit(main())
