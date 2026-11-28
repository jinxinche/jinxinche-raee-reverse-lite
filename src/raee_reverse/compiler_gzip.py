"""Build zlib 1.4 minigzip with two compilers at one CFLAGS string.

The gzip bytes are whatever the binaries emit. A difference is recorded.
This module does not rewrite a header to force the outputs to match.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from raee_reverse.sandbox import run_sandboxed

REQUESTED_CFLAGS = "-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN"
INPUTS = (
    ("empty", b""),
    ("abc", b"abc"),
    ("hello", b"hello"),
    ("range4096", bytes(index % 251 for index in range(4096))),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_tarball(tarball: Path, dest: Path) -> Path:
    root = dest.resolve()
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"tarball path escapes the work directory: {member.name}")
        try:
            archive.extractall(root, filter="data")
        except TypeError:
            archive.extractall(root)
    source = root / "zlib-1.4"
    if not (source / "configure").is_file():
        raise ValueError("tarball did not contain zlib-1.4/configure")
    return source


def _makefile_value(text: str, name: str) -> str | None:
    prefix = name + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def build_minigzip(dest: Path, compiler: str, tarball: Path, *, cflags: str = REQUESTED_CFLAGS) -> dict:
    """Configure and make one tree. A non-zero exit is returned, not hidden."""
    dest.mkdir(parents=True, exist_ok=True)
    source = extract_tarball(tarball, dest)
    env = os.environ.copy()
    env["CC"] = compiler
    env["CFLAGS"] = cflags
    configure = subprocess.run(
        ["sh", "./configure"],
        cwd=source,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    makefile_text = (source / "Makefile").read_text(encoding="utf-8", errors="replace") if (source / "Makefile").is_file() else ""
    make = subprocess.run(
        ["make", "-j4", f"CC={compiler}", f"CFLAGS={cflags}"],
        cwd=source,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    binary = source / "minigzip"
    compile_lines = [line.strip() for line in make.stdout.splitlines() if cflags in line and ".c" in line]
    preferred = [line for line in compile_lines if any(token in line for token in ("deflate.c", "crc32.c", "minigzip.c"))]
    sample = preferred[0] if preferred else (compile_lines[0] if compile_lines else "")
    link = next((line.strip() for line in make.stdout.splitlines() if "-o minigzip" in line or "-o minigzip.exe" in line), "")
    return {
        "compiler": compiler,
        "compiler_path": shutil.which(compiler),
        "requested_cflags": cflags,
        "makefile_cflags": _makefile_value(makefile_text, "CFLAGS"),
        "makefile_cc": _makefile_value(makefile_text, "CC"),
        "configure_exit": configure.returncode,
        "make_exit": make.returncode,
        "binary": str(binary) if binary.is_file() else None,
        "binary_sha256": sha256(binary.read_bytes()) if binary.is_file() else None,
        "compile_line": sample,
        "link_line": link,
        "compile_line_has_requested_cflags": bool(sample),
        "configure_stderr_tail": configure.stderr[-1500:],
        "make_stderr_tail": make.stderr[-1500:],
    }


def compress_inputs(binary: str, work: Path) -> list[dict]:
    rows = []
    for name, data in INPUTS:
        compressed = run_sandboxed(
            [binary],
            work_dir=work / name / "comp",
            stdin=data,
            timeout=30,
            cpu_seconds=15,
            fsize_bytes=8_000_000,
            max_output_bytes=2_000_000,
        )
        stdout = compressed["stdout"]
        row = {
            "name": name,
            "input_sha256": sha256(data),
            "input_length": len(data),
            "returncode": compressed["returncode"],
            "execution_result": compressed["execution_result"],
            "truncated": compressed["truncated"],
            "stdout_sha256": sha256(stdout),
            "stdout_length": len(stdout),
            "prefix_hex": stdout[:16].hex(),
            "network_isolated": compressed["network_isolated"],
            "network_namespace": compressed["network_namespace"],
            "network_mechanism": (compressed.get("network_probe") or {}).get("mechanism"),
            "roundtrip_equals_input": False,
            "_stdout": stdout,
        }
        if compressed["returncode"] == 0 and not compressed["truncated"]:
            decompressed = run_sandboxed(
                [binary, "-d"],
                work_dir=work / name / "dec",
                stdin=stdout,
                timeout=30,
                cpu_seconds=15,
                fsize_bytes=8_000_000,
                max_output_bytes=2_000_000,
            )
            row["decompress_returncode"] = decompressed["returncode"]
            row["roundtrip_equals_input"] = (
                decompressed["returncode"] == 0 and not decompressed["truncated"] and decompressed["stdout"] == data
            )
        rows.append(row)
    return rows


def first_mismatch(left: bytes, right: bytes) -> int | None:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    if len(left) != len(right):
        return limit
    return None


def compare_outputs(left: list[dict], right: list[dict]) -> dict:
    by_right = {row["name"]: row for row in right}
    rows = []
    identical = True
    for row in left:
        other = by_right.get(row["name"])
        if other is None:
            identical = False
            rows.append({"name": row["name"], "equal": False, "reason": "missing from the other compiler"})
            continue
        equal = (
            row["stdout_sha256"] == other["stdout_sha256"]
            and row["stdout_length"] == other["stdout_length"]
            and row["returncode"] == 0
            and other["returncode"] == 0
            and not row["truncated"]
            and not other["truncated"]
        )
        if not equal:
            identical = False
        mismatch = None
        if "_stdout" in row and "_stdout" in other:
            mismatch = first_mismatch(row["_stdout"], other["_stdout"])
        rows.append(
            {
                "name": row["name"],
                "equal": equal,
                "stdout_sha256": row["stdout_sha256"],
                "other_sha256": other["stdout_sha256"],
                "stdout_length": row["stdout_length"],
                "other_length": other["stdout_length"],
                "first_mismatch_offset": mismatch,
                "roundtrip_equals_input": bool(row["roundtrip_equals_input"] and other["roundtrip_equals_input"]),
            }
        )
    if len(left) != len(right):
        identical = False
    return {"identical": identical, "inputs": rows}
