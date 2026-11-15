"""Measure the frozen crc32 goal. The bar is read from GOAL_CRC32.json and must be 0.90.

This process refuses to open the held-out tree and the non-blind seal.
It does not edit docs/phase4/GOAL.md or docs/evidence/zlib_enhancement.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.path_guard import install, restore  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
GOAL = REPO / "docs" / "phase4" / "GOAL_CRC32.json"
CANDIDATE = REPO / "targets" / "zlib" / "candidate" / "crc32_pclmul.c"
BENCH = REPO / "targets" / "zlib" / "harness" / "crc32_bench.c"
HOOK_FROM = """    /* Return initial CRC, if requested. */
    if (buf == Z_NULL) return 0;
"""
HOOK_TO = """    /* Return initial CRC, if requested. */
    if (buf == Z_NULL) return 0;
#if defined(__x86_64__)
    {
        uLong pclmul_crc = 0;
        extern int crc32_z_pclmul_try(uLong crc, const unsigned char FAR *buf, z_size_t len, uLong *out);
        if (crc32_z_pclmul_try(crc, buf, len, &pclmul_crc)) return pclmul_crc;
    }
#endif
"""
IDENTITY = {
    "empty": b"",
    "abc": b"abc",
    "hello": b"hello",
}


def _load_goal() -> dict:
    goal = json.loads(GOAL.read_text(encoding="utf-8"))
    if goal.get("crc32_ratio_max") != 0.9:
        raise SystemExit("the frozen bar is 0.90; this script will not measure a different bar")
    if goal.get("supersedes_closed_goal") is not False:
        raise SystemExit("this goal must not supersede the closed speed goal")
    return goal


def _extract(dest: Path) -> Path:
    root = dest.resolve()
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(member.name)
            archive.extract(member, root)
    return root / "zlib-1.4"


def _patch(source: Path) -> None:
    text = (source / "crc32.c").read_text(encoding="utf-8")
    count = text.count(HOOK_FROM)
    if count != 2:
        raise SystemExit(f"crc32.c hook sites: {count}")
    (source / "crc32.c").write_text(text.replace(HOOK_FROM, HOOK_TO), encoding="utf-8")
    shutil.copyfile(CANDIDATE, source / "crc32_pclmul.c")
    makefile = source / "Makefile"
    body = makefile.read_text(encoding="utf-8")
    needle = "OBJZ = adler32.o crc32.o "
    pic = "PIC_OBJZ = adler32.lo crc32.lo "
    if needle not in body or pic not in body:
        raise SystemExit("Makefile is missing OBJZ")
    body = body.replace(needle, "OBJZ = adler32.o crc32.o crc32_pclmul.o ", 1)
    body = body.replace(pic, "PIC_OBJZ = adler32.lo crc32.lo crc32_pclmul.lo ", 1)
    body += (
        "\ncrc32_pclmul.o: crc32_pclmul.c\n"
        "\t$(CC) $(CFLAGS) -msse4.2 -mpclmul $(ZINC) -c -o $@ crc32_pclmul.c\n"
        "crc32_pclmul.lo: crc32_pclmul.c\n"
        "\t-@mkdir objs 2>/dev/null || test -d objs\n"
        "\t$(CC) $(SFLAGS) -msse4.2 -mpclmul $(ZINC) -DPIC -c -o objs/crc32_pclmul.o crc32_pclmul.c\n"
        "\t-@mv objs/crc32_pclmul.o $@\n"
    )
    makefile.write_text(body, encoding="utf-8")


def _build(source: Path, *, candidate: bool) -> dict:
    configure = subprocess.run(["./configure"], cwd=source, capture_output=True, text=True, check=False)
    if candidate and configure.returncode == 0:
        _patch(source)
    make = subprocess.run(["make", "-j4"], cwd=source, capture_output=True, text=True, check=False)
    return {
        "configure_exit": configure.returncode,
        "make_exit": make.returncode,
        "configure_stderr_tail": configure.stderr[-400:],
        "make_stderr_tail": make.stderr[-800:],
        "minigzip": (source / "minigzip").is_file(),
        "libz": (source / "libz.a").is_file(),
    }


def _compile_bench(source: Path) -> bool:
    completed = subprocess.run(
        ["gcc", "-O2", "-o", "crc32_bench", str(BENCH), "libz.a"],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    (source / "bench_build.txt").write_text(completed.stderr[-800:], encoding="utf-8")
    return completed.returncode == 0 and (source / "crc32_bench").is_file()


def _samples(binary: Path) -> tuple[list[float], str, str, int]:
    completed = subprocess.run([str(binary)], cwd=binary.parent, capture_output=True, check=False)
    payload_crc = ""
    check = ""
    samples = []
    for line in completed.stdout.decode("ascii", "replace").splitlines():
        if line.startswith("payload_crc "):
            payload_crc = line.split()[1]
        elif line.startswith("check123456789 "):
            check = line.split()[1]
        elif line.startswith("sample "):
            samples.append(float(line.split()[1]))
    return samples, payload_crc, check, completed.returncode


def _minigzip(binary: Path, data: bytes, work: Path) -> bytes | None:
    result = run_sandboxed(
        [str(binary)],
        work_dir=work,
        stdin=data,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=1_000_000,
        max_output_bytes=100_000,
    )
    if result["returncode"] != 0 or result["execution_result"] != "passed":
        return None
    return result["stdout"]


def _environment() -> dict:
    cpu = ""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    gcc = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True, check=False)
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uname": uname.stdout.strip(),
        "gcc": gcc.stdout.strip(),
        "cpu": cpu,
        "nproc": os.cpu_count(),
    }


def main() -> int:
    goal = _load_goal()
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    original_open = install(REPO)
    report: dict = {
        "goal": "docs/phase4/GOAL_CRC32.json",
        "goal_sha256": hashlib.sha256(GOAL.read_bytes()).hexdigest(),
        "closed_goal_untouched": True,
        "supersedes_closed_goal": False,
        "bar": goal["crc32_ratio_max"],
        "threads": 1,
        "environment": _environment(),
        "enhancement_met": False,
        "stable_improvement": False,
    }
    try:
        baseline_src = _extract(work / "baseline")
        candidate_src = _extract(work / "candidate")
        base_build = _build(baseline_src, candidate=False)
        cand_build = _build(candidate_src, candidate=True)
        report["baseline_build"] = base_build
        report["candidate_build"] = cand_build
        if not (base_build["minigzip"] and cand_build["minigzip"] and _compile_bench(baseline_src) and _compile_bench(candidate_src)):
            report["delivery"] = "compatible baseline build or candidate build failed; enhancement not met"
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"enhancement_met": False, "reason": "build failed"}))
            return 0
        base_samples, base_crc, base_check, base_code = _samples(baseline_src / "crc32_bench")
        cand_samples, cand_crc, cand_check, cand_code = _samples(candidate_src / "crc32_bench")
        # The first printed sample is the warmup.
        base_measured = base_samples[1:]
        cand_measured = cand_samples[1:]
        identity = {}
        identity_ok = True
        for name, data in IDENTITY.items():
            base_out = _minigzip(baseline_src / "minigzip", data, work / "id-base" / name)
            cand_out = _minigzip(candidate_src / "minigzip", data, work / "id-cand" / name)
            same = base_out is not None and base_out == cand_out
            identity[name] = {"same_stdout": same, "bytes": None if base_out is None else len(base_out)}
            identity_ok = identity_ok and same
        correct = (
            base_code == 0
            and cand_code == 0
            and len(base_measured) == 21
            and len(cand_measured) == 21
            and base_crc == cand_crc
            and base_crc != ""
            and base_check == "cbf43926"
            and cand_check == "cbf43926"
            and identity_ok
        )
        base_median = statistics.median(base_measured) if base_measured else None
        cand_median = statistics.median(cand_measured) if cand_measured else None
        ratio = None
        if base_median and cand_median is not None and base_median > 0:
            ratio = cand_median / base_median
        faster = bool(correct and ratio is not None and ratio <= 0.90)
        met = bool(correct and faster)
        report.update(
            {
                "correct": correct,
                "baseline_crc": base_crc,
                "candidate_crc": cand_crc,
                "baseline_check123456789": base_check,
                "candidate_check123456789": cand_check,
                "minigzip_identity": identity,
                "baseline_samples_seconds": base_measured,
                "candidate_samples_seconds": cand_measured,
                "baseline_median_seconds": base_median,
                "candidate_median_seconds": cand_median,
                "ratio_candidate_over_baseline": ratio,
                "bar_met": faster,
                "enhancement_met": met,
                "delivery": "enhancement met on this single sample" if met else "crc32 goal not met",
                "sample_size": 21,
                "warmup_excluded": 1,
            }
        )
    finally:
        restore(original_open)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "enhancement_met": report.get("enhancement_met"),
        "ratio_candidate_over_baseline": report.get("ratio_candidate_over_baseline"),
        "correct": report.get("correct"),
        "delivery": report.get("delivery"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
