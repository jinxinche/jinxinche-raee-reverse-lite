"""Build the frozen candidates and run the sealed broad check.

Stock and attempt 2 use tools/reproduce_frozen_zlib_builds.py unchanged.
Attempt 3 uses tools/reproduce_frozen_zlib_attempt3.py. On x86_64 every
built candidate must pass. On another architecture, attempt 2 may fail to
compile because the frozen patch passes -msse4.2 -mpclmul; that is not a
pass. A candidate that builds and then fails the check is not a pass.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
X86_MACHINES = {"x86_64", "amd64", "AMD64"}
LABELS = ("stock", "attempt2", "attempt3")
PCLMUL_TOKENS = ("msse4.2", "mpclmul", "pclmul")


def _built(entry: dict | None) -> bool:
    if not entry:
        return False
    crc = entry.get("crc_stdin") or {}
    return bool(
        entry.get("configure_exit") == 0
        and entry.get("make_exit") == 0
        and crc.get("exit") == 0
        and crc.get("present") is True
        and entry.get("minigzip")
    )


def _run(script: Path, label: str, entry: dict, out: Path, build: Path) -> dict:
    source = Path(entry["source"])
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            label,
            str(entry["minigzip"]),
            str(source / "crc32_stdin"),
            str(out),
            str(build),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    return {
        "label": label,
        "script": script.name,
        "exit": completed.returncode,
        "pass": report.get("pass") is True,
        "executed": report.get("executed") is True,
        "sample_size": report.get("sample_size"),
        "stdout_tail": (completed.stdout or "")[-500:],
        "stderr_tail": (completed.stderr or "")[-500:],
    }


def _not_reproduced(label: str, entry: dict | None, machine: str, reason: str) -> dict:
    return {
        "label": label,
        "executed": False,
        "pass": False,
        "reproducible": False,
        "reason": reason,
        "machine": machine,
        "make_exit": None if not entry else entry.get("make_exit"),
        "make_stderr_tail": None if not entry else entry.get("make_stderr_tail"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_blind_broad.py DEST")
    if os.environ.get("CFLAGS") or os.environ.get("LDFLAGS") or os.environ.get("CC"):
        raise SystemExit("refusing to build with CFLAGS, LDFLAGS, or CC set")
    dest = Path(sys.argv[1]).resolve()
    repo = REPO.resolve()
    if dest == repo or repo in dest.parents:
        raise SystemExit("refusing to build inside the repository")
    dest.mkdir(parents=True, exist_ok=True)
    reports = dest / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(REPO / "tools" / "reproduce_frozen_zlib_builds.py"), str(dest)],
        check=False,
    )
    subprocess.run(
        [sys.executable, str(REPO / "tools" / "reproduce_frozen_zlib_attempt3.py"), str(dest)],
        check=False,
    )
    build_path = dest / "build.json"
    if not build_path.is_file():
        raise SystemExit("build.json was not written")
    build = json.loads(build_path.read_text(encoding="utf-8"))
    machine = platform.machine()
    x86 = machine in X86_MACHINES
    broad = REPO / "tools" / "check_blind_broad.py"
    enwik8 = REPO / "tools" / "check_blind_acceptance.py"
    summary = {"machine": machine, "x86_64": x86, "checks": [], "problems": []}
    built = {label: _built(build.get(label)) for label in LABELS}
    for label in LABELS:
        out = reports / f"blind_broad_{label}.json"
        if built[label]:
            summary["checks"].append(_run(broad, label, build[label], out, build_path))
        else:
            reason = "the frozen recipe did not produce minigzip and crc32_stdin"
            if label == "attempt2" and not x86:
                reason = (
                    "frozen attempt 2 compiles crc32_pclmul.c with -msse4.2 -mpclmul; "
                    "this host did not produce a binary"
                )
            payload = _not_reproduced(label, build.get(label), machine, reason)
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            summary["checks"].append(
                {
                    "label": label,
                    "script": broad.name,
                    "exit": 1,
                    "pass": False,
                    "executed": False,
                    "sample_size": None,
                    "reproducible": False,
                }
            )
    for label in ("stock", "attempt2"):
        if not built[label]:
            continue
        out = reports / f"enwik8_{label}.json"
        summary["checks"].append(_run(enwik8, label, build[label], out, build_path))

    def _check(label: str, script: str) -> dict | None:
        for item in summary["checks"]:
            if item["label"] == label and item["script"] == script:
                return item
        return None

    stock = _check("stock", broad.name)
    attempt3 = _check("attempt3", broad.name)
    attempt2 = _check("attempt2", broad.name)
    if not stock or not (stock["pass"] and stock["executed"]):
        summary["problems"].append("stock broad check did not pass")
    if not attempt3 or not (attempt3["pass"] and attempt3["executed"]):
        summary["problems"].append("attempt 3 broad check did not pass")
    if built["attempt2"]:
        if not attempt2 or not (attempt2["pass"] and attempt2["executed"]):
            summary["problems"].append("attempt 2 built but the broad check did not pass")
    elif x86:
        summary["problems"].append("attempt 2 did not build on x86_64")
    else:
        tail = str((build.get("attempt2") or {}).get("make_stderr_tail") or "")
        if not any(token in tail for token in PCLMUL_TOKENS):
            summary["problems"].append("attempt 2 failed to build and the log does not show the frozen pclmul flags")
        if attempt2 and attempt2["pass"] is not False:
            summary["problems"].append("an unreproduced attempt 2 was marked pass")
    for label in ("stock", "attempt2"):
        if not built[label]:
            continue
        item = _check(label, enwik8.name)
        if not item or not (item["pass"] and item["executed"]):
            summary["problems"].append(f"enwik8 {label} check did not pass")
    (reports / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not summary["problems"], "problems": summary["problems"], "machine": machine}))
    return 0 if not summary["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
