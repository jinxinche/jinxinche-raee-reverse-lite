"""Measure the frozen Lua loadbuffer goal. One candidate: MYCFLAGS=-O3.

The script refuses a bar other than 0.90. It does not open sealed acceptance
files. A miss stays a miss. One sample does not set stable_improvement.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.path_guard import install, restore  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

REPO = ROOT
TARBALL = REPO / "targets" / "lua" / "dist" / "lua-5.4.9.tar.gz"
TARBALL_SHA256 = "2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6"
HARNESS = REPO / "targets" / "lua" / "harness" / "loadbuffer_bench.c"
GOAL = REPO / "docs" / "phase4" / "GOAL_LUA.json"
REPETITIONS = 200000
PAYLOAD_BYTES = 1200000
BAR = 0.90
SYNTAX_STDERR = b"./luac: chunk.lua:1: <name> expected near '='\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    blob = TARBALL.read_bytes()
    if _sha(blob) != TARBALL_SHA256:
        raise SystemExit("tarball sha256 does not match the frozen pin")
    root = dest.resolve()
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(f"tarball path escapes the work directory: {member.name}")
            archive.extract(member, root)
    return root / "lua-5.4.9"


def _build(source: Path, mycflags: str | None) -> dict:
    argv = ["make", "linux"]
    if mycflags is not None:
        argv.append(f"MYCFLAGS={mycflags}")
    result = run_sandboxed(
        argv,
        work_dir=source,
        timeout=180,
        cpu_seconds=120,
        fsize_bytes=80_000_000,
        max_output_bytes=4_000_000,
    )
    echo_argv = ["make", "echo"]
    if mycflags is not None:
        echo_argv.append(f"MYCFLAGS={mycflags}")
    echo = run_sandboxed(
        echo_argv,
        work_dir=source,
        timeout=30,
        cpu_seconds=10,
        fsize_bytes=1_000_000,
        max_output_bytes=100_000,
    )
    luac = source / "src" / "luac"
    lib = source / "src" / "liblua.a"
    text = echo["stdout"].decode("utf-8", "replace")
    return {
        "make_exit": result["returncode"],
        "truncated": result["truncated"],
        "rlimits_applied": result["rlimits_applied"],
        "network_namespace": result["network_namespace"],
        "luac_exists": luac.is_file(),
        "luac_bytes": luac.stat().st_size if luac.is_file() else None,
        "liblua_bytes": lib.stat().st_size if lib.is_file() else None,
        "echo": text,
        "echo_has_o3": "-O3" in text,
        "echo_has_flto": "-flto" in text,
    }


def _compile(source: Path, dest: Path) -> bool:
    result = run_sandboxed(
        [
            "gcc",
            "-O2",
            "-I",
            str(source / "src"),
            "-o",
            str(dest),
            str(HARNESS),
            str(source / "src" / "liblua.a"),
            "-lm",
            "-ldl",
        ],
        work_dir=source,
        timeout=60,
        cpu_seconds=30,
        fsize_bytes=20_000_000,
        max_output_bytes=1_000_000,
    )
    return result["returncode"] == 0 and not result["truncated"] and dest.is_file()


def _parse_line(stdout: bytes) -> tuple[int, int, int] | None:
    text = stdout.decode("ascii", "replace").strip()
    if not text.startswith("rc="):
        return None
    parts = {}
    for item in text.split():
        key, value = item.split("=", 1)
        parts[key] = int(value)
    return parts["rc"], parts["ns"], parts["len"]


def _bench(binary: Path, work: Path, mode: str) -> dict:
    result = run_sandboxed(
        [str(binary), str(REPETITIONS), mode],
        work_dir=work,
        timeout=30,
        cpu_seconds=20,
        fsize_bytes=5_000_000,
        max_output_bytes=10_000,
    )
    parsed = _parse_line(result["stdout"]) if not result["truncated"] and result["returncode"] == 0 else None
    return {"parsed": parsed, "returncode": result["returncode"], "truncated": result["truncated"]}


def _cli(luac: Path, parent: Path, name: str, data: bytes | None, args: list[str], stdin: bytes = b"") -> dict:
    work = parent / name
    work.mkdir(parents=True, exist_ok=True)
    copy = work / "luac"
    copy.write_bytes(luac.read_bytes())
    copy.chmod(0o755)
    if data is not None:
        (work / "chunk.lua").write_bytes(data)
    result = run_sandboxed(
        ["./luac", *args],
        work_dir=work,
        stdin=stdin,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )
    return {
        "exit_code": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "truncated": result["truncated"],
        "output_exists": (work / "luac.out").exists(),
    }


def _cli_ok(luac: Path, parent: Path) -> bool:
    specs = [
        ("empty", b"", ["-p", "chunk.lua"], 0, b"", b""),
        ("return1", b"return 1\n", ["-p", "chunk.lua"], 0, b"", b""),
        ("print_abc", b'print("abc")\n', ["-p", "chunk.lua"], 0, b"", b""),
        ("syntax", b"local =\n", ["-p", "chunk.lua"], 1, b"", SYNTAX_STDERR),
    ]
    ok = True
    for name, data, args, exit_code, stdout, stderr in specs:
        row = _cli(luac, parent, name, data, args)
        ok = ok and (
            not row["truncated"]
            and row["exit_code"] == exit_code
            and row["stdout"] == stdout
            and row["stderr"] == stderr
            and row["output_exists"] is False
        )
    return ok


def _environment() -> dict:
    cpu = ""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = ""
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    gcc = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True, check=False)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uname": uname.stdout.strip(),
        "gcc": gcc.stdout.strip(),
        "cpu": cpu,
        "nproc": os.cpu_count(),
    }


def main() -> int:
    goal = json.loads(GOAL.read_text(encoding="utf-8"))
    if goal.get("ratio_max") != 0.9 or goal.get("candidate_command") != "make linux MYCFLAGS=-O3":
        raise SystemExit("refusing a bar or candidate other than the frozen Lua goal")
    if len(sys.argv) != 3:
        raise SystemExit("usage: measure_lua_parse.py WORK OUT")
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    original = install(REPO)
    report: dict = {
        "goal": "docs/phase4/GOAL_LUA.json",
        "goal_commit": "39ee2082521a5ef6944330e4f3a63cb43e9fbcfb",
        "synthetic": False,
        "bar": BAR,
        "threads": 1,
        "environment": _environment(),
        "enhancement_met": False,
        "stable_improvement": False,
        "attempt_status": "not_done",
    }
    try:
        baseline_src = _extract(work / "baseline")
        candidate_src = _extract(work / "candidate")
        base_build = _build(baseline_src, None)
        cand_build = _build(candidate_src, "-O3")
        report["baseline_build"] = {key: value for key, value in base_build.items() if key != "echo"}
        report["candidate_build"] = {key: value for key, value in cand_build.items() if key != "echo"}
        report["baseline_echo_has_o3"] = base_build["echo_has_o3"]
        report["candidate_echo_has_o3"] = cand_build["echo_has_o3"]
        report["candidate_echo_has_flto"] = cand_build["echo_has_flto"]
        base_bin = work / "baseline-bench"
        cand_bin = work / "candidate-bench"
        built = (
            base_build["make_exit"] == 0
            and cand_build["make_exit"] == 0
            and not base_build["truncated"]
            and not cand_build["truncated"]
            and base_build["luac_exists"]
            and cand_build["luac_exists"]
            and not base_build["echo_has_o3"]
            and cand_build["echo_has_o3"]
            and not cand_build["echo_has_flto"]
            and _compile(baseline_src, base_bin)
            and _compile(candidate_src, cand_bin)
        )
        if not built:
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "baseline or candidate build failed; enhancement not met"
        else:
            base_bad = _bench(base_bin, work / "base-bad", "bad")
            cand_bad = _bench(cand_bin, work / "cand-bad", "bad")
            base_samples = []
            cand_samples = []
            base_ok = True
            cand_ok = True
            for index in range(22):
                base_row = _bench(base_bin, work / f"base-speed-{index}", "speed")
                cand_row = _bench(cand_bin, work / f"cand-speed-{index}", "speed")
                if base_row["parsed"] is None or base_row["parsed"][0] != 0 or base_row["parsed"][2] != PAYLOAD_BYTES:
                    base_ok = False
                else:
                    base_samples.append(base_row["parsed"][1])
                if cand_row["parsed"] is None or cand_row["parsed"][0] != 0 or cand_row["parsed"][2] != PAYLOAD_BYTES:
                    cand_ok = False
                else:
                    cand_samples.append(cand_row["parsed"][1])
            base_measured = base_samples[1:] if base_samples else []
            cand_measured = cand_samples[1:] if cand_samples else []
            cli_ok = _cli_ok(baseline_src / "src" / "luac", work / "cli-base") and _cli_ok(
                candidate_src / "src" / "luac", work / "cli-cand"
            )
            bad_ok = (
                base_bad["parsed"] is not None
                and cand_bad["parsed"] is not None
                and base_bad["parsed"][0] != 0
                and cand_bad["parsed"][0] != 0
            )
            correct = base_ok and cand_ok and len(base_measured) == 21 and len(cand_measured) == 21 and cli_ok and bad_ok
            base_median = statistics.median(base_measured) if len(base_measured) == 21 else None
            cand_median = statistics.median(cand_measured) if len(cand_measured) == 21 else None
            ratio = None
            if base_median and cand_median is not None and base_median > 0:
                ratio = cand_median / base_median
            met = bool(correct and ratio is not None and ratio <= BAR)
            report.update(
                {
                    "correct": correct,
                    "cli_ok": cli_ok,
                    "bad_chunk_rejected": bad_ok,
                    "baseline_samples_ns": base_measured,
                    "candidate_samples_ns": cand_measured,
                    "baseline_median_ns": base_median,
                    "candidate_median_ns": cand_median,
                    "ratio_candidate_over_baseline": ratio,
                    "baseline_luac_bytes": base_build["luac_bytes"],
                    "candidate_luac_bytes": cand_build["luac_bytes"],
                    "baseline_liblua_bytes": base_build["liblua_bytes"],
                    "candidate_liblua_bytes": cand_build["liblua_bytes"],
                    "binary_size_is_a_bar": False,
                    "enhancement_met": met,
                    "stable_improvement": False,
                    "attempt_status": "closed_met" if met else "closed_missed",
                    "sample_size": 21,
                    "warmup_excluded": 1,
                    "delivery": "enhancement met on this single sample" if met else "lua parse goal not met",
                }
            )
    finally:
        restore(original)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "enhancement_met": report.get("enhancement_met"),
        "ratio": report.get("ratio_candidate_over_baseline"),
        "correct": report.get("correct"),
        "attempt_status": report.get("attempt_status"),
        "baseline_median_ns": report.get("baseline_median_ns"),
        "candidate_median_ns": report.get("candidate_median_ns"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
