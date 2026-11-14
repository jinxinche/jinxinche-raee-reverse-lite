"""Measure the one pre-registered zlib candidate.

The goal in docs/phase4/GOAL.md is the threshold. This script does not edit it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
PAYLOAD = bytes(i % 251 for i in range(4 * 1024 * 1024))
RUNS = 21


def _extract(dest: Path) -> Path:
    root = dest.resolve()
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(member.name)
            archive.extract(member, root)
    return root / "zlib-1.4"


def _build_lto(work: Path) -> Path | None:
    source = _extract(work)
    env_prefix = 'CFLAGS="-O3 -flto" LDFLAGS="-flto" '
    # The sandbox runner does not take a custom environment merge for CFLAGS.
    # Run configure and make with an explicit shell so the frozen flags are the candidate.
    configure = subprocess.run(
        ["bash", "-lc", f'{env_prefix}./configure'],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    make = subprocess.run(["make", "-j4"], cwd=source, capture_output=True, text=True, check=False)
    binary = source / "minigzip"
    note = {
        "configure_exit": configure.returncode,
        "make_exit": make.returncode,
        "configure_stderr_tail": configure.stderr[-500:],
        "make_stderr_tail": make.stderr[-500:],
    }
    note["built"] = configure.returncode == 0 and make.returncode == 0 and binary.is_file()
    (work / "build_note.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    if not note["built"]:
        return None
    return binary


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
    return samples, last, code


def main() -> int:
    baseline = Path(sys.argv[1])
    work = Path(sys.argv[2])
    out = Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    candidate = _build_lto(work / "lto-src")
    report: dict = {
        "goal": "docs/phase4/GOAL.md",
        "payload_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        "payload_bytes": len(PAYLOAD),
        "runs_per_median": RUNS,
        "warmup_excluded": 1,
        "candidate": "zlib 1.4 CFLAGS=-O3 -flto LDFLAGS=-flto",
        "acceptance": "non-blind",
        "used_final_acceptance_inputs": False,
    }
    if candidate is None:
        note = json.loads((work / "lto-src" / "build_note.json").read_text(encoding="utf-8")) if (work / "lto-src" / "build_note.json").is_file() else {}
        report.update({"enhancement_met": False, "delivery": "compatible baseline done, enhancement not met", "build": note})
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"enhancement_met": False, "reason": "candidate build failed"}))
        return 0
    base_comp, base_gzip, base_comp_code = _times(baseline, PAYLOAD, work / "base-comp", [])
    cand_comp, cand_gzip, cand_comp_code = _times(candidate, PAYLOAD, work / "cand-comp", [])
    base_dec, base_plain, base_dec_code = _times(baseline, base_gzip, work / "base-dec", ["-d"])
    cand_dec, cand_plain, cand_dec_code = _times(candidate, cand_gzip, work / "cand-dec", ["-d"])
    base_dec_median = statistics.median(base_dec)
    cand_dec_median = statistics.median(cand_dec)
    base_comp_median = statistics.median(base_comp)
    cand_comp_median = statistics.median(cand_comp)
    correct = (
        base_comp_code == 0
        and cand_comp_code == 0
        and base_dec_code == 0
        and cand_dec_code == 0
        and base_plain == PAYLOAD
        and cand_plain == PAYLOAD
    )
    faster = cand_dec_median <= 0.90 * base_dec_median
    compress_ok = cand_comp_median <= 1.05 * base_comp_median
    met = bool(correct and faster and compress_ok)
    report.update(
        {
            "correct": correct,
            "baseline_decompress_median_seconds": base_dec_median,
            "candidate_decompress_median_seconds": cand_dec_median,
            "decompress_ratio_candidate_over_baseline": cand_dec_median / base_dec_median if base_dec_median else None,
            "baseline_compress_median_seconds": base_comp_median,
            "candidate_compress_median_seconds": cand_comp_median,
            "compress_ratio_candidate_over_baseline": cand_comp_median / base_comp_median if base_comp_median else None,
            "decompress_bar_met": faster,
            "compress_cap_met": compress_ok,
            "enhancement_met": met,
            "delivery": "enhancement met on this single sample" if met else "compatible baseline done, enhancement not met",
            "stable_improvement": False,
            "sample_size": RUNS,
        }
    )
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "enhancement_met", "delivery", "decompress_ratio_candidate_over_baseline",
        "compress_ratio_candidate_over_baseline", "correct", "stable_improvement",
    )}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
