"""Measure the frozen base64 encode goal. One candidate: the README x86 codecs.

The sandbox drops inherited environment variables, so the frozen flag line is
run by `bash -c` inside the sandbox. The script refuses a bar other than 0.90.
It does not open sealed acceptance files. A miss stays a miss.
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
TARBALL = REPO / "targets" / "base64" / "dist" / "base64-0.5.3.tar.gz"
TARBALL_SHA256 = "74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42"
HARNESS = REPO / "targets" / "base64" / "harness" / "encode_bench.c"
GOAL = REPO / "docs" / "phase4" / "GOAL_BASE64.json"
BAR = 0.90
CANDIDATE = (
    "AVX2_CFLAGS=-mavx2 SSSE3_CFLAGS=-mssse3 SSE41_CFLAGS=-msse4.1 "
    "SSE42_CFLAGS=-msse4.2 AVX_CFLAGS=-mavx make -j4"
)
REQUIRED_ON = ("HAVE_AVX2   1", "HAVE_SSSE3  1", "HAVE_SSE41  1", "HAVE_SSE42  1", "HAVE_AVX    1")
REQUIRED_OFF = ("HAVE_AVX512 0", "HAVE_NEON32 0", "HAVE_NEON64 0")


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
    return root / "base64-0.5.3"


def _build(source: Path, candidate: bool) -> dict:
    argv = ["bash", "-c", CANDIDATE if candidate else "make -j4"]
    result = run_sandboxed(
        argv,
        work_dir=source,
        timeout=180,
        cpu_seconds=120,
        fsize_bytes=80_000_000,
        max_output_bytes=4_000_000,
    )
    binary = source / "bin" / "base64"
    lib = source / "lib" / "libbase64.o"
    config = (source / "lib" / "config.h").read_text(encoding="utf-8") if (source / "lib" / "config.h").is_file() else ""
    return {
        "make_exit": result["returncode"],
        "truncated": result["truncated"],
        "rlimits_applied": result["rlimits_applied"],
        "network_namespace": result["network_namespace"],
        "binary_exists": binary.is_file(),
        "binary_bytes": binary.stat().st_size if binary.is_file() else None,
        "lib_bytes": lib.stat().st_size if lib.is_file() else None,
        "config": config,
    }


def _config_ok(config: str, candidate: bool) -> bool:
    if candidate:
        return all(item in config for item in REQUIRED_ON) and all(item in config for item in REQUIRED_OFF)
    return all(token in config for token in (
        "HAVE_AVX2   0",
        "HAVE_SSSE3  0",
        "HAVE_SSE41  0",
        "HAVE_SSE42  0",
        "HAVE_AVX    0",
        "HAVE_AVX512 0",
    ))


def _compile(source: Path, dest: Path) -> bool:
    result = run_sandboxed(
        [
            "gcc",
            "-O2",
            "-DBASE64_STATIC_DEFINE",
            "-I",
            str(source / "include"),
            "-o",
            str(dest),
            str(HARNESS),
            str(source / "lib" / "libbase64.o"),
        ],
        work_dir=source,
        timeout=60,
        cpu_seconds=30,
        fsize_bytes=20_000_000,
        max_output_bytes=1_000_000,
    )
    return result["returncode"] == 0 and not result["truncated"] and dest.is_file()


def _bench(binary: Path, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    result = run_sandboxed(
        [str(binary)],
        work_dir=work,
        timeout=30,
        cpu_seconds=20,
        fsize_bytes=40_000_000,
        max_output_bytes=10_000,
    )
    encoded = work / "encoded.bin"
    text = result["stdout"].decode("ascii", "replace").strip()
    parsed = None
    if result["returncode"] == 0 and not result["truncated"] and text.startswith("ns=") and encoded.is_file():
        parts = {}
        for item in text.split():
            key, value = item.split("=", 1)
            parts[key] = int(value)
        blob = encoded.read_bytes()
        if len(blob) == parts["outlen"]:
            parsed = {"ns": parts["ns"], "outlen": parts["outlen"], "sha256": _sha(blob)}
    return {"parsed": parsed, "returncode": result["returncode"], "truncated": result["truncated"]}


def _cli(binary: Path, parent: Path) -> bool:
    specs = [
        ("abc", [], b"abc", 0, b"YWJj\n", None),
        ("nowrap", ["-w", "0"], b"abc", 0, b"YWJj", None),
        ("hello", [], b"hello", 0, b"aGVsbG8=\n", None),
        ("empty", [], b"", 0, b"", None),
        ("nul", [], b"\x00\x01\xff", 0, b"AAH/\n", None),
        ("decode", ["-d"], b"YWJj\n", 0, b"abc", None),
        ("invalid", ["-d"], b"!!!!", 1, b"", b"decoding error"),
    ]
    ok = True
    for name, args, stdin, exit_code, stdout, stderr_part in specs:
        work = parent / name
        work.mkdir(parents=True, exist_ok=True)
        copy = work / "base64"
        copy.write_bytes(binary.read_bytes())
        copy.chmod(0o755)
        result = run_sandboxed(
            ["./base64", *args],
            work_dir=work,
            stdin=stdin,
            timeout=20,
            cpu_seconds=10,
            fsize_bytes=5_000_000,
            max_output_bytes=1_000_000,
        )
        row_ok = (
            not result["truncated"]
            and result["returncode"] == exit_code
            and result["stdout"] == stdout
        )
        if stderr_part is not None:
            row_ok = row_ok and stderr_part in result["stderr"]
        ok = ok and row_ok
    return ok


def _environment() -> dict:
    cpu = ""
    flags = ""
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            if line.startswith("model name") and not cpu:
                cpu = line.split(":", 1)[1].strip()
            if line.startswith("flags") and not flags:
                parts = line.split()
                flags = " ".join(name for name in ("ssse3", "sse4_1", "sse4_2", "avx", "avx2", "avx512vl", "avx512vbmi") if name in parts)
    except OSError:
        pass
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    gcc = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True, check=False)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uname": uname.stdout.strip(),
        "gcc": gcc.stdout.strip(),
        "cpu": cpu,
        "simd_flags_present": flags,
        "nproc": os.cpu_count(),
    }


def main() -> int:
    goal = json.loads(GOAL.read_text(encoding="utf-8"))
    if goal.get("ratio_max") != 0.9 or goal.get("candidate_command") != CANDIDATE or goal.get("avx512") is not False:
        raise SystemExit("refusing a bar or candidate other than the frozen base64 goal")
    if len(sys.argv) != 3:
        raise SystemExit("usage: measure_base64_encode.py WORK OUT")
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    original = install(REPO)
    report: dict = {
        "goal": "docs/phase4/GOAL_BASE64.json",
        "goal_commit": "39ee2082521a5ef6944330e4f3a63cb43e9fbcfb",
        "synthetic": False,
        "bar": BAR,
        "threads": 1,
        "flags": 0,
        "environment": _environment(),
        "enhancement_met": False,
        "stable_improvement": False,
        "attempt_status": "not_done",
        "candidate_invocation": "bash -c inside run_sandboxed, because the sandbox does not pass codec flags through the environment",
    }
    try:
        baseline_src = _extract(work / "baseline")
        candidate_src = _extract(work / "candidate")
        base_build = _build(baseline_src, False)
        cand_build = _build(candidate_src, True)
        report["baseline_build"] = {key: value for key, value in base_build.items() if key != "config"}
        report["candidate_build"] = {key: value for key, value in cand_build.items() if key != "config"}
        report["baseline_config_ok"] = _config_ok(base_build["config"], False)
        report["candidate_config_ok"] = _config_ok(cand_build["config"], True)
        base_bin = work / "baseline-bench"
        cand_bin = work / "candidate-bench"
        built = (
            base_build["make_exit"] == 0
            and cand_build["make_exit"] == 0
            and not base_build["truncated"]
            and not cand_build["truncated"]
            and report["baseline_config_ok"]
            and report["candidate_config_ok"]
            and _compile(baseline_src, base_bin)
            and _compile(candidate_src, cand_bin)
        )
        if not built:
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "baseline or candidate build failed; enhancement not met"
            report["candidate_config"] = cand_build["config"]
        else:
            base_rows = [_bench(base_bin, work / f"base-speed-{index}") for index in range(22)]
            cand_rows = [_bench(cand_bin, work / f"cand-speed-{index}") for index in range(22)]
            base_samples = [row["parsed"]["ns"] for row in base_rows if row["parsed"]]
            cand_samples = [row["parsed"]["ns"] for row in cand_rows if row["parsed"]]
            base_hashes = {row["parsed"]["sha256"] for row in base_rows if row["parsed"]}
            cand_hashes = {row["parsed"]["sha256"] for row in cand_rows if row["parsed"]}
            same_bytes = len(base_hashes) == 1 and base_hashes == cand_hashes
            cli_ok = _cli(baseline_src / "bin" / "base64", work / "cli-base") and _cli(
                candidate_src / "bin" / "base64", work / "cli-cand"
            )
            correct = (
                len(base_samples) == 22
                and len(cand_samples) == 22
                and same_bytes
                and cli_ok
            )
            base_measured = base_samples[1:] if len(base_samples) == 22 else []
            cand_measured = cand_samples[1:] if len(cand_samples) == 22 else []
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
                    "same_encoded_bytes": same_bytes,
                    "encoded_sha256": next(iter(base_hashes)) if len(base_hashes) == 1 else None,
                    "baseline_samples_ns": base_measured,
                    "candidate_samples_ns": cand_measured,
                    "baseline_median_ns": base_median,
                    "candidate_median_ns": cand_median,
                    "ratio_candidate_over_baseline": ratio,
                    "baseline_binary_bytes": base_build["binary_bytes"],
                    "candidate_binary_bytes": cand_build["binary_bytes"],
                    "baseline_lib_bytes": base_build["lib_bytes"],
                    "candidate_lib_bytes": cand_build["lib_bytes"],
                    "binary_size_is_a_bar": False,
                    "enhancement_met": met,
                    "stable_improvement": False,
                    "attempt_status": "closed_met" if met else "closed_missed",
                    "sample_size": 21,
                    "warmup_excluded": 1,
                    "delivery": "enhancement met on this single sample" if met else "base64 encode goal not met",
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
        "baseline_binary_bytes": report.get("baseline_binary_bytes"),
        "candidate_binary_bytes": report.get("candidate_binary_bytes"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
