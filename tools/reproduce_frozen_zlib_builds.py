"""Reproduce the frozen stock zlib 1.4 and attempt-2 trees.

The recipe is the one already recorded in tools/measure_zlib_minigzip_attempt2.py:
./configure && make, with the attempt-2 patch applied only in the temporary
tree and only through that module's _build(candidate=True). This script does
not edit repository sources, does not pass -O3 or -flto, and does not write
the closed goal results.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "targets" / "zlib" / "blind_acceptance" / "crc32_stdin.c"
MEASURE = REPO / "tools" / "measure_zlib_minigzip_attempt2.py"


def _load_measure():
    spec = importlib.util.spec_from_file_location("frozen_minigzip_attempt2", MEASURE)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load the frozen build recipe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compile_crc(source: Path) -> dict:
    completed = subprocess.run(
        ["gcc", "-O2", "-I.", "-o", "crc32_stdin", str(HARNESS), "libz.a"],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    binary = source / "crc32_stdin"
    return {
        "command": ["gcc", "-O2", "-I.", "-o", "crc32_stdin", str(HARNESS), "libz.a"],
        "exit": completed.returncode,
        "stderr_tail": completed.stderr[-400:],
        "present": binary.is_file(),
        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest() if binary.is_file() else None,
    }


def _one(module, dest: Path, *, candidate: bool) -> dict:
    source = module._extract(dest)
    build = module._build(source, candidate=candidate)
    crc = _compile_crc(source)
    minigzip = source / "minigzip"
    libz = source / "libz.a"
    return {
        "candidate_patch": candidate,
        "source": str(source),
        "configure_exit": build["configure_exit"],
        "make_exit": build["make_exit"],
        "recipe": build["recipe"],
        "cflags_override": build["cflags_override"],
        "ldflags_override": build["ldflags_override"],
        "configure_stderr_tail": build["configure_stderr_tail"],
        "make_stderr_tail": build["make_stderr_tail"],
        "minigzip": str(minigzip) if minigzip.is_file() else None,
        "minigzip_sha256": hashlib.sha256(minigzip.read_bytes()).hexdigest() if minigzip.is_file() else None,
        "libz_sha256": hashlib.sha256(libz.read_bytes()).hexdigest() if libz.is_file() else None,
        "crc_stdin": crc,
    }


def main() -> int:
    if os.environ.get("CFLAGS") or os.environ.get("LDFLAGS") or os.environ.get("CC"):
        raise SystemExit("refusing to build with CFLAGS, LDFLAGS, or CC set")
    dest = Path(sys.argv[1]).resolve()
    repo = REPO.resolve()
    if dest == repo or repo in dest.parents:
        raise SystemExit("refusing to build inside the repository")
    dest.mkdir(parents=True, exist_ok=True)
    module = _load_measure()
    if module.TARBALL != REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz":
        raise SystemExit("frozen tarball path changed")
    gcc = subprocess.run(["gcc", "-dumpversion"], capture_output=True, text=True, check=False)
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False)
    report = {
        "source_commit": head.stdout.strip(),
        "recipe": ["./configure", "make"],
        "cflags_override": None,
        "ldflags_override": None,
        "forbidden_flags_not_passed": ["-O3", "-flto"],
        "environment": {
            "os": platform.system(),
            "python": platform.python_version(),
            "gcc": gcc.stdout.strip(),
            "uname": uname.stdout.strip(),
            "cflags": os.environ.get("CFLAGS"),
            "ldflags": os.environ.get("LDFLAGS"),
            "cc": os.environ.get("CC"),
        },
        "stock": _one(module, dest / "baseline", candidate=False),
        "attempt2": _one(module, dest / "candidate", candidate=True),
    }
    out = dest / "build.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"build_json": str(out), "source_commit": report["source_commit"]}))
    stock_ok = report["stock"]["make_exit"] == 0 and report["stock"]["crc_stdin"]["exit"] == 0
    attempt_ok = report["attempt2"]["make_exit"] == 0 and report["attempt2"]["crc_stdin"]["exit"] == 0
    return 0 if stock_ok and attempt_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
