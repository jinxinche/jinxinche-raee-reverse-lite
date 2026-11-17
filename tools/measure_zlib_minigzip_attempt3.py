"""Measure the frozen minigzip attempt-3 goal. One candidate. No flag shopping.

The bars are read from GOAL_MINIGZIP_ATTEMPT3.json and must stay 0.90 and 1.05.
This process refuses to open the held-out tree, the non-blind seal, and the
published acceptance tree. It does not edit the closed goal or attempt 2.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
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
GOAL = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT3.json"
BENCH = REPO / "targets" / "zlib" / "harness" / "crc32_bench.c"
PAYLOAD = bytes(i % 251 for i in range(4 * 1024 * 1024))
RUNS = 21
IDENTITY = {"empty": b"", "abc": b"abc", "hello": b"hello"}
INCLUDE_FROM = '#include "inffast.h"\n'
INCLUDE_TO = '#include "inffast.h"\n#if defined(__x86_64__)\n#include <emmintrin.h>\n#endif\n'
HELPER = """
#if defined(__x86_64__)
/* Direct-match copy. Distance >= 16: 16-byte SSE2 chunks, which do not overlap.
   Distance < 16, and any short tail: zlib 1.4's three-byte loop. */
static unsigned char FAR *rrl_copy_direct(unsigned char FAR *out, unsigned dist, unsigned len)
{
    unsigned char FAR *from = out - dist;
    if (dist >= 16) {
        while (len >= 16) {
            _mm_storeu_si128((__m128i *)out, _mm_loadu_si128((const __m128i *)from));
            out += 16;
            from += 16;
            len -= 16;
        }
    }
    while (len > 2) {
        *out++ = *from++;
        *out++ = *from++;
        *out++ = *from++;
        len -= 3;
    }
    if (len) {
        *out++ = *from++;
        if (len > 1)
            *out++ = *from++;
    }
    return out;
}
#endif

"""
DIRECT_FROM = """                else {
                    from = out - dist;          /* copy direct from output */
                    do {                        /* minimum length is three */
                        *out++ = *from++;
                        *out++ = *from++;
                        *out++ = *from++;
                        len -= 3;
                    } while (len > 2);
                    if (len) {
                        *out++ = *from++;
                        if (len > 1)
                            *out++ = *from++;
                    }
                }
"""
DIRECT_TO = """                else {
#if defined(__x86_64__)
                    out = rrl_copy_direct(out, dist, len);
#else
                    from = out - dist;          /* copy direct from output */
                    do {                        /* minimum length is three */
                        *out++ = *from++;
                        *out++ = *from++;
                        *out++ = *from++;
                        len -= 3;
                    } while (len > 2);
                    if (len) {
                        *out++ = *from++;
                        if (len > 1)
                            *out++ = *from++;
                    }
#endif
                }
"""


def _extra_inputs() -> dict[str, bytes]:
    rng = random.Random(20261117)
    return {
        "zeros-10000": bytes(10000),
        "period-3": bytes(i % 3 for i in range(20000)),
        "period-15": bytes(i % 15 for i in range(20000)),
        "period-16": bytes(i % 16 for i in range(20000)),
        "period-17": bytes(i % 17 for i in range(20000)),
        "abc-repeat": b"abc" * 5000,
        "fixed-seed-8000": rng.randbytes(8000),
    }


def _load_goal() -> dict:
    goal = json.loads(GOAL.read_text(encoding="utf-8"))
    if goal.get("decompress_ratio_max") != 0.9 or goal.get("compress_ratio_max") != 1.05:
        raise SystemExit("refusing to measure a bar other than decompress 0.90 and compress 1.05")
    if goal.get("minigzip_buflen") != 16384 or goal.get("setvbuf_added") is not False:
        raise SystemExit("refusing a minigzip buffer edit")
    if goal.get("crc32_hook") is not None or goal.get("forbidden_sources") != ["crc32_pclmul.c"]:
        raise SystemExit("refusing a crc32 hook")
    if goal.get("copy_width_bytes") != 16:
        raise SystemExit("refusing a copy width other than 16")
    if goal.get("cflags_override") is not None or goal.get("ldflags_override") is not None:
        raise SystemExit("refusing a CFLAGS or LDFLAGS override")
    if goal.get("supersedes_closed_goal") is not False or goal.get("supersedes_attempt2") is not False:
        raise SystemExit("this goal must not supersede the closed goal or attempt 2")
    if goal.get("stable_improvement_allowed_for_one_sample") is not False:
        raise SystemExit("one sample cannot be marked as a stable improvement")
    if goal.get("floor_samples_decide_enhancement") is not False:
        raise SystemExit("floor samples must not decide the enhancement")
    forbidden = set(goal.get("forbidden_flags") or [])
    if "-O3" not in forbidden or "-flto" not in forbidden:
        raise SystemExit("the frozen goal must keep forbidding -O3 and -flto")
    if goal.get("baseline_recipe") != ["./configure", "make"] or goal.get("candidate_recipe") != ["./configure", "make"]:
        raise SystemExit("the frozen recipe is ./configure && make")
    if goal.get("intrinsics") != ["_mm_loadu_si128", "_mm_storeu_si128"]:
        raise SystemExit("refusing a different copy intrinsic")
    if os.environ.get("CFLAGS") or os.environ.get("LDFLAGS"):
        raise SystemExit("refusing to measure with CFLAGS or LDFLAGS set in the environment")
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


def _cflags_line(source: Path) -> str | None:
    for line in (source / "Makefile").read_text(encoding="utf-8").splitlines():
        if line.startswith("CFLAGS="):
            return line
    return None


def _patch(source: Path) -> None:
    minigzip = (source / "test" / "minigzip.c").read_text(encoding="utf-8")
    if minigzip.count("#define BUFLEN      16384\n") != 1:
        raise RuntimeError("minigzip.c no longer has BUFLEN 16384")
    if "setvbuf" in minigzip:
        raise RuntimeError("minigzip.c already calls setvbuf")
    crc = (source / "crc32.c").read_text(encoding="utf-8")
    if "crc32_z_pclmul_try" in crc or "crc32_pclmul" in crc:
        raise RuntimeError("crc32.c already has a pclmul hook")
    text = (source / "inffast.c").read_text(encoding="utf-8")
    if text.count(INCLUDE_FROM) != 1 or text.count(DIRECT_FROM) != 1:
        raise RuntimeError("inffast.c direct-copy site count is not 1")
    if "rrl_copy_direct" in text:
        raise RuntimeError("inffast.c already contains the attempt-3 helper")
    text = text.replace(INCLUDE_FROM, INCLUDE_TO, 1)
    marker = "void ZLIB_INTERNAL inflate_fast(z_streamp strm, unsigned start) {\n"
    if text.count(marker) != 1:
        raise RuntimeError("inflate_fast signature count is not 1")
    text = text.replace(marker, HELPER + marker, 1)
    text = text.replace(DIRECT_FROM, DIRECT_TO, 1)
    if text.count("rrl_copy_direct") != 2 or text.count("_mm_loadu_si128") != 1:
        raise RuntimeError("attempt-3 helper did not land once")
    (source / "inffast.c").write_text(text, encoding="utf-8")


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
        "makefile_cflags": _cflags_line(source),
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


def _minigzip(binary: Path, data: bytes, work: Path, args: list[str] | None = None) -> bytes | None:
    result = run_sandboxed(
        [str(binary), *(args or [])],
        work_dir=work,
        stdin=data,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=20_000_000,
        max_output_bytes=8_000_000,
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
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "uname": uname.stdout.strip(),
        "gcc": gcc.stdout.strip(),
        "cpu": cpu,
        "nproc": os.cpu_count(),
        "kernel": platform.release(),
    }


def _floor(binary: Path, empty_gzip: bytes | None, work: Path) -> dict:
    true_bin = Path("/bin/true")
    report: dict = {"decides_enhancement": False, "true_present": true_bin.is_file()}
    if true_bin.is_file():
        samples, _, code = _times(true_bin, b"", work / "true", [])
        report["true_exit"] = code
        report["true_median_seconds"] = statistics.median(samples) if samples else None
        report["true_runs"] = len(samples)
    if empty_gzip is None:
        report["empty_decompress_median_seconds"] = None
        return report
    samples, plain, code = _times(binary, empty_gzip, work / "empty-dec", ["-d"])
    report["empty_decompress_exit"] = code
    report["empty_decompress_stdout_empty"] = plain == b""
    report["empty_decompress_median_seconds"] = statistics.median(samples) if samples else None
    report["empty_decompress_runs"] = len(samples)
    return report


def main() -> int:
    goal = _load_goal()
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work.mkdir(parents=True, exist_ok=True)
    original_open = install(REPO)
    report: dict = {
        "goal": "docs/phase4/GOAL_MINIGZIP_ATTEMPT3.json",
        "goal_sha256": hashlib.sha256(GOAL.read_bytes()).hexdigest(),
        "closed_goal_untouched": True,
        "attempt2_untouched": True,
        "supersedes_closed_goal": False,
        "supersedes_attempt2": False,
        "candidate": "inflate_fast direct-match 16-byte SSE2 copy when distance >= 16",
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
        if platform.machine() != "x86_64":
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "attempt 3 requires x86_64; this host is not that machine"
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"enhancement_met": False, "reason": "not x86_64"}))
            return 0
        baseline_src = _extract(work / "baseline")
        candidate_src = _extract(work / "candidate")
        try:
            base_build = _build(baseline_src, candidate=False)
            cand_build = _build(candidate_src, candidate=True)
        except RuntimeError as exc:
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "attempt 3 closed as missed"
            report["patch_error"] = str(exc)
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"enhancement_met": False, "reason": str(exc)}))
            return 0
        report["baseline_build"] = base_build
        report["candidate_build"] = cand_build
        same_flags = (
            base_build["makefile_cflags"] is not None
            and base_build["makefile_cflags"] == cand_build["makefile_cflags"]
        )
        report["makefile_cflags_identical"] = same_flags
        built = (
            base_build["minigzip"]
            and cand_build["minigzip"]
            and base_build["make_exit"] == 0
            and cand_build["make_exit"] == 0
            and same_flags
        )
        if not built or not _compile_bench(candidate_src):
            report["attempt_status"] = "closed_missed"
            report["delivery"] = "candidate or baseline build failed; attempt 3 closed as missed"
            out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"enhancement_met": False, "reason": "build failed"}))
            return 0
        base_comp, base_gzip, base_comp_code = _times(baseline_src / "minigzip", PAYLOAD, work / "base-comp", [])
        cand_comp, cand_gzip, cand_comp_code = _times(candidate_src / "minigzip", PAYLOAD, work / "cand-comp", [])
        base_dec, base_plain, base_dec_code = _times(baseline_src / "minigzip", base_gzip, work / "base-dec", ["-d"])
        cand_dec, cand_plain, cand_dec_code = _times(candidate_src / "minigzip", cand_gzip, work / "cand-dec", ["-d"])
        cross_plain = _minigzip(candidate_src / "minigzip", base_gzip, work / "cross-dec", ["-d"])
        identity = {}
        identity_ok = True
        for name, data in IDENTITY.items():
            base_out = _minigzip(baseline_src / "minigzip", data, work / "id-base" / name)
            cand_out = _minigzip(candidate_src / "minigzip", data, work / "id-cand" / name)
            same = base_out is not None and base_out == cand_out
            identity[name] = {"same_stdout": same, "bytes": None if base_out is None else len(base_out)}
            identity_ok = identity_ok and same
        extra = {}
        extra_ok = True
        for name, data in _extra_inputs().items():
            base_out = _minigzip(baseline_src / "minigzip", data, work / "extra-base" / name)
            cand_out = _minigzip(candidate_src / "minigzip", data, work / "extra-cand" / name)
            base_back = None if base_out is None else _minigzip(baseline_src / "minigzip", base_out, work / "extra-base-dec" / name, ["-d"])
            cand_back = None if cand_out is None else _minigzip(candidate_src / "minigzip", cand_out, work / "extra-cand-dec" / name, ["-d"])
            same = base_out is not None and base_out == cand_out and base_back == data and cand_back == data
            extra[name] = {"same_gzip_and_round_trip": same, "bytes": None if base_out is None else len(base_out)}
            extra_ok = extra_ok and same
        abc_gzip = _minigzip(candidate_src / "minigzip", b"abc", work / "abc-magic")
        magic_ok = bool(abc_gzip and abc_gzip[:2] == b"\x1f\x8b" and abc_gzip[4:8] == b"\x00\x00\x00\x00")
        abc_crc = _abc_crc(candidate_src / "crc32_bench")
        empty_gzip = _minigzip(baseline_src / "minigzip", b"", work / "empty-gzip")
        floor = _floor(baseline_src / "minigzip", empty_gzip, work / "floor")
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
            and base_gzip == cand_gzip
            and cross_plain == PAYLOAD
            and identity_ok
            and extra_ok
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
                "extra_identity": extra,
                "gzip_bytes_identical_on_payload": base_gzip == cand_gzip,
                "candidate_decompresses_baseline_gzip": cross_plain == PAYLOAD,
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
                "floor": floor,
                "enhancement_met": met,
                "stable_improvement": False,
                "sample_size": RUNS,
                "hosts": 1,
                "attempt_status": "closed_met_on_one_sample" if met else "closed_missed",
                "delivery": (
                    "met on this single sample; stable_improvement is false"
                    if met
                    else "attempt 3 closed as missed"
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
    ) if k in report}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
