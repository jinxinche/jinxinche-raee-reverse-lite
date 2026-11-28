"""Build pinned aklomp/base64 0.5.3 and check the dev CLI cases.

This file does not read the sealed observation file.
The build is plain `make -j4`, with no SIMD codec flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = REPO / "targets" / "base64" / "dist" / "base64-0.5.3.tar.gz"
TARBALL_SHA256 = "74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract(dest: Path) -> Path:
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


def _run(work: Path, args: list[str], stdin: bytes = b"") -> dict:
    return run_sandboxed(
        ["./base64", *args],
        work_dir=work,
        stdin=stdin,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )


def _invoke(binary: Path, parent: Path, name: str, args: list[str], stdin: bytes, file_bytes: bytes | None) -> dict:
    work = parent / name
    work.mkdir(parents=True)
    copy = work / "base64"
    copy.write_bytes(binary.read_bytes())
    copy.chmod(0o755)
    if file_bytes is not None:
        (work / "input.bin").write_bytes(file_bytes)
    return _run(work, args, stdin)


def build(prefix: Path, work: Path) -> dict:
    source = _extract(work)
    make = run_sandboxed(
        ["make", "-j4"],
        work_dir=source,
        timeout=180,
        cpu_seconds=120,
        fsize_bytes=80_000_000,
        max_output_bytes=4_000_000,
    )
    binary = source / "bin" / "base64"
    config = source / "lib" / "config.h"
    if make["returncode"] != 0 or make["truncated"] or not binary.is_file():
        return {"build_ok": False, "make_exit": make["returncode"], "truncated": make["truncated"], "accepted_pass": False}
    config_text = config.read_text(encoding="utf-8")
    bindir = prefix / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    installed = bindir / "base64"
    shutil.copy2(binary, installed)
    installed.chmod(0o755)
    parent = work / "dev"
    specs = [
        ("empty", [], b"", None, 0, b""),
        ("abc", [], b"abc", None, 0, b"YWJj\n"),
        ("abc-nowrap", ["-w", "0"], b"abc", None, 0, b"YWJj"),
        ("hello", [], b"hello", None, 0, b"aGVsbG8=\n"),
        ("nul", [], b"\x00\x01\xff", None, 0, b"AAH/\n"),
        ("abc-file", ["input.bin"], b"", b"abc", 0, b"YWJj\n"),
        ("abc-decode", ["-d"], b"YWJj\n", None, 0, b"abc"),
        ("invalid", ["-d"], b"!!!!", None, 1, b""),
    ]
    checks = []
    for name, args, stdin, file_bytes, exit_code, stdout in specs:
        row = _invoke(installed, parent, name, args, stdin, file_bytes)
        ok = not row["truncated"] and row["returncode"] == exit_code and row["stdout"] == stdout
        if name == "invalid":
            ok = ok and b"decoding error" in row["stderr"]
        checks.append({"name": name, "ok": ok, "exit_code": row["returncode"]})
    return {
        "build_ok": True,
        "make_exit": 0,
        "simd_flags": None,
        "config_has_have_avx2_0": "HAVE_AVX2   0" in config_text,
        "base64_sha256": _sha(installed.read_bytes()),
        "checks": checks,
        "dev_ok": all(item["ok"] for item in checks),
        "accepted_pass": False,
        "opened_seal": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rrl-base64-base-") as temporary:
        report = build(args.prefix, Path(temporary))
    print(json.dumps(report, indent=2))
    return 0 if report.get("dev_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
