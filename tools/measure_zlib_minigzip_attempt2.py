"""Measure the frozen minigzip attempt-2 goal. One candidate. No flag shopping.

The bars are read from GOAL_MINIGZIP_ATTEMPT2.json and must stay 0.90 and 1.05.
This process refuses to open the held-out tree, the non-blind seal, and the
published acceptance tree. It does not edit the closed goal or its result.
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
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.path_guard import install, restore  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
GOAL = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT2.json"
CANDIDATE = REPO / "targets" / "zlib" / "candidate" / "crc32_pclmul.c"
BENCH = REPO / "targets" / "zlib" / "harness" / "crc32_bench.c"
PAYLOAD = bytes(i % 251 for i in range(4 * 1024 * 1024))
RUNS = 21
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
IDENTITY = {"empty": b"", "abc": b"abc", "hello": b"hello"}
SETVBUF = """    if (argc == 0) {
        static char rrl_stdin_buf[262144];
        static char rrl_stdout_buf[262144];
        setvbuf(stdin, rrl_stdin_buf, _IOFBF, sizeof rrl_stdin_buf);
        setvbuf(stdout, rrl_stdout_buf, _IOFBF, sizeof rrl_stdout_buf);
        SET_BINARY_MODE(stdin);
        SET_BINARY_MODE(stdout);
"""


def _load_goal() -> dict:
    goal = json.loads(GOAL.read_text(encoding="utf-8"))
    if goal.get("decompress_ratio_max") != 0.9 or goal.get("compress_ratio_max") != 1.05:
        raise SystemExit("refusing to measure a bar other than decompress 0.90 and compress 1.05")
    if goal.get("minigzip_buflen_to") != 262144 or goal.get("setvbuf_bytes") != 262144:
        raise SystemExit("refusing to measure a buffer size other than 262144")
    if goal.get("cflags_override") is not None or goal.get("ldflags_override") is not None:
        raise SystemExit("refusing a CFLAGS or LDFLAGS override")
    if goal.get("supersedes_closed_goal") is not False:
        raise SystemExit("this goal must not supersede the closed speed goal")
    if goal.get("stable_improvement_allowed_for_one_sample") is not False:
        raise SystemExit("one sample cannot be marked as a stable improvement")
    forbidden = set(goal.get("forbidden_flags") or [])
    if "-O3" not in forbidden or "-flto" not in forbidden:
        raise SystemExit("the frozen goal must keep forbidding -O3 and -flto")
    if goal.get("baseline_recipe") != ["./configure", "make"] or goal.get("candidate_recipe") != ["./configure", "make"]:
        raise SystemExit("the frozen recipe is ./configure && make")
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
    minigzip = (source / "test" / "minigzip.c").read_text(encoding="utf-8")
    needle = "#define BUFLEN      16384\n"
    if minigzip.count(needle) != 1:
        raise SystemExit("minigzip.c BUFLEN site count is not 1")
    anchor = "    if (argc == 0) {\n        SET_BINARY_MODE(stdin);\n        SET_BINARY_MODE(stdout);\n"
    if minigzip.count(anchor) != 1:
        raise SystemExit("minigzip.c stdin/stdout site count is not 1")
    minigzip = minigzip.replace(needle, "#define BUFLEN      262144\n", 1)
    minigzip = minigzip.replace(anchor, SETVBUF, 1)
    (source / "test" / "minigzip.c").write_text(minigzip, encoding="utf-8")
    text = (source / "crc32.c").read_text(encoding="utf-8")
    count = text.count(HOOK_FROM)
    if count != 2:
        raise SystemExit(f"crc32.c hook sites: {count}")
    (source / "crc32.c").write_text(text.replace(HOOK_FROM, HOOK_TO), encoding="utf-8")
    shutil.copyfile(CANDIDATE, source / "crc32_pclmul.c")
    makefile = source / "Makefile"
    body = makefile.read_text(encoding="utf-8")
    obj = "OBJZ = adler32.o crc32.o "
    pic = "PIC_OBJZ = adler32.lo crc32.lo "
    if obj not in body or pic not in body:
        raise SystemExit("Makefile is missing OBJZ")
    body = body.replace(obj, "OBJZ = adler32.o crc32.o crc32_pclmul.o ", 1)
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
        "recipe": ["./configure", "make"],
        "cflags_override": None,
        "ldflags_override": None,
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
    return completed.returncode == 0 and (source / "crc32_bench").is_file()


def _times(binary: Path, data: bytes, work: Path, args: list[str]) -> tuple[list[float], bytes, int]:
    samples = []
    last = b""
    code = 1
    for index in range(RUNS + 1):
        started = time.perf_counter()
        result = run_sandboxed(
            [str(binary), *args],
            work_dir=work / str(index),
            stdin=data,
            timeout=30,
            cpu_seconds=20,
            fsize_bytes=20_000_000,
            max_output_bytes=8_000_000,
        )
        elapsed = time.perf_counter() - started
        if index > 0:
            samples.append(elapsed)
        last = result["stdout"]
        code = result["returncode"] if result["returncode"] is not None else 1
        if result["execution_result"] != "passed":
            code = code or 1
    return samples, last, code


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


def _abc_crc(binary: Path) -> str | None:
    completed = subprocess.run([str(binary), "crc"], input=b"abc", capture_output=True, check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("ascii", "replace").strip()


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
        "os": platform.system(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
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
        "goal": "docs/phase4/GOAL_MINIGZIP_ATTEMPT2.json",
        "goal_sha256": hashlib.sha256(GOAL.read_bytes()).hexdigest(),
        "closed_goal_untouched": True,
        "supersedes_closed_goal": False,
        "decompress_bar": goal["decompress_ratio_max"],
        "compress_cap": goal["compress_ratio_max"],
        "payload_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "payload_bytes": len(PAYLOAD),
        "runs_per_median": RUNS,
        "warmup_excluded": 1,
        "baseline_recipe": "./configure && make",
        "candidate_recipe": "./configure && make",
        "cflags_override": None,
        "ldflags_override": None,
        "threads": 1,
        "environment": _environment(),
        "enhancement_met": False,
        "stable_improvement": False,
        "attempt_status": "not_measured",
    }
    try:
        baseline_src = _extract(work / "baseline")
        candidate_src = _extract(work / "candidate")
        base_build = _build(baseline_src, candidate=False)
        cand_build = _build(candidate_src, candidate=True)
        report["baseline_build"] = base_build
        report["candidate_build"] = cand_build
        built = base_build["minigzip"] and cand_build["minigzip"] and base_build["make_exit"] == 0 and cand_build["make_exit"] == 0
        if not built or not _compile_bench(candidate_src):
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "candidate or baseline build failed; attempt 2 closed as missed"
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"enhancement_met": False, "reason": "build failed"}))
            return 0
        base_comp, base_gzip, base_comp_code = _times(baseline_src / "minigzip", PAYLOAD, work / "base-comp", [])
        cand_comp, cand_gzip, cand_comp_code = _times(candidate_src / "minigzip", PAYLOAD, work / "cand-comp", [])
        base_dec, base_plain, base_dec_code = _times(baseline_src / "minigzip", base_gzip, work / "base-dec", ["-d"])
        cand_dec, cand_plain, cand_dec_code = _times(candidate_src / "minigzip", cand_gzip, work / "cand-dec", ["-d"])
        identity = {}
        identity_ok = True
        for name, data in IDENTITY.items():
            base_out = _minigzip(baseline_src / "minigzip", data, work / "id-base" / name)
            cand_out = _minigzip(candidate_src / "minigzip", data, work / "id-cand" / name)
            same = base_out is not None and base_out == cand_out
            identity[name] = {"same_stdout": same, "bytes": None if base_out is None else len(base_out)}
            identity_ok = identity_ok and same
        abc_gzip = _minigzip(candidate_src / "minigzip", b"abc", work / "abc-magic")
        magic_ok = bool(abc_gzip and abc_gzip[:2] == b"\x1f\x8b" and abc_gzip[4:8] == b"\x00\x00\x00\x00")
        abc_crc = _abc_crc(candidate_src / "crc32_bench")
        base_dec_median = statistics.median(base_dec)
        cand_dec_median = statistics.median(cand_dec)
        base_comp_median = statistics.median(base_comp)
        cand_comp_median = statistics.median(cand_comp)
        correct = (
            base_comp_code == 0
            and cand_comp_code == 0
            and base_dec_code == 0
            and cand_dec_code == 0
            and len(base_dec) == RUNS
            and len(cand_dec) == RUNS
            and base_plain == PAYLOAD
            and cand_plain == PAYLOAD
            and identity_ok
            and magic_ok
            and abc_crc == "352441c2"
        )
        dec_ratio = cand_dec_median / base_dec_median if base_dec_median else None
        comp_ratio = cand_comp_median / base_comp_median if base_comp_median else None
        faster = bool(dec_ratio is not None and dec_ratio <= 0.90)
        compress_ok = bool(comp_ratio is not None and comp_ratio <= 1.05)
        met = bool(correct and faster and compress_ok)
        report.update(
            {
                "correct": correct,
                "identity": identity,
                "gzip_magic_and_zero_mtime": magic_ok,
                "candidate_crc32_abc": abc_crc,
                "baseline_decompress_median_seconds": base_dec_median,
                "candidate_decompress_median_seconds": cand_dec_median,
                "decompress_ratio_candidate_over_baseline": dec_ratio,
                "baseline_compress_median_seconds": base_comp_median,
                "candidate_compress_median_seconds": cand_comp_median,
                "compress_ratio_candidate_over_baseline": comp_ratio,
                "decompress_bar_met": faster,
                "compress_cap_met": compress_ok,
                "enhancement_met": met,
                "stable_improvement": False,
                "sample_size": RUNS,
                "hosts": 1,
                "attempt_status": "closed_met_on_one_sample" if met else "closed_missed",
                "delivery": (
                    "met on this single sample; stable_improvement is false"
                    if met
                    else "attempt 2 closed as missed"
                ),
            }
        )
    finally:
        restore(original_open)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "enhancement_met",
        "attempt_status",
        "delivery",
        "decompress_ratio_candidate_over_baseline",
        "compress_ratio_candidate_over_baseline",
        "correct",
        "stable_improvement",
    )}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
