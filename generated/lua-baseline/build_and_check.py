"""Build pinned Lua 5.4.9 and check the dev luac cases.

This file does not read the sealed observation file.
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

TARBALL = REPO / "targets" / "lua" / "dist" / "lua-5.4.9.tar.gz"
TARBALL_SHA256 = "2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6"
VERSION_STDOUT = b"Lua 5.4.9  Copyright (C) 1994-2026 Lua.org, PUC-Rio\n"
SYNTAX_STDERR = b"./luac: chunk.lua:1: <name> expected near '='\n"
MISSING_STDERR = b"./luac: cannot open chunk.lua: No such file or directory\n"


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
    return root / "lua-5.4.9"


def _run(work: Path, args: list[str], stdin: bytes = b"") -> dict:
    return run_sandboxed(
        ["./luac", *args],
        work_dir=work,
        stdin=stdin,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )


def _invoke(binary: Path, parent: Path, name: str, args: list[str], data: bytes | None, stdin: bytes) -> dict:
    work = parent / name
    work.mkdir(parents=True)
    copy = work / "luac"
    copy.write_bytes(binary.read_bytes())
    copy.chmod(0o755)
    if data is not None:
        (work / "chunk.lua").write_bytes(data)
    result = _run(work, args, stdin)
    output = work / "luac.out"
    return {
        "exit_code": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "truncated": result["truncated"],
        "output_exists": output.exists(),
        "output_bytes": output.read_bytes() if output.exists() else b"",
        "execution_result": result["execution_result"],
    }


def build(prefix: Path, work: Path) -> dict:
    source = _extract(work)
    make = run_sandboxed(
        ["make", "linux"],
        work_dir=source,
        timeout=180,
        cpu_seconds=120,
        fsize_bytes=80_000_000,
        max_output_bytes=4_000_000,
    )
    luac = source / "src" / "luac"
    if make["returncode"] != 0 or make["truncated"] or not luac.is_file():
        return {"build_ok": False, "make_exit": make["returncode"], "truncated": make["truncated"], "accepted_pass": False}
    bindir = prefix / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    installed = bindir / "luac"
    shutil.copy2(luac, installed)
    installed.chmod(0o755)
    parent = work / "dev"
    checks = []

    def add(name: str, args: list[str], *, data: bytes | None, stdin: bytes, exit_code: int, stdout: bytes, stderr: bytes | None, output: bool, prefix_ok: bytes | None = None) -> None:
        row = _invoke(installed, parent, name, args, data, stdin)
        ok = (
            not row["truncated"]
            and row["exit_code"] == exit_code
            and row["stdout"] == stdout
            and row["output_exists"] is output
        )
        if stderr is not None:
            ok = ok and row["stderr"] == stderr
        if prefix_ok is not None:
            ok = ok and row["output_bytes"].startswith(prefix_ok)
        checks.append({"name": name, "ok": ok, "exit_code": row["exit_code"]})

    add("empty", ["-p", "chunk.lua"], data=b"", stdin=b"", exit_code=0, stdout=b"", stderr=b"", output=False)
    add("return1", ["-p", "chunk.lua"], data=b"return 1\n", stdin=b"", exit_code=0, stdout=b"", stderr=b"", output=False)
    add("print_abc", ["-p", "chunk.lua"], data=b'print("abc")\n', stdin=b"", exit_code=0, stdout=b"", stderr=b"", output=False)
    add("syntax", ["-p", "chunk.lua"], data=b"local =\n", stdin=b"", exit_code=1, stdout=b"", stderr=SYNTAX_STDERR, output=False)
    add("stdin", ["-p", "-"], data=None, stdin=b"return 1\n", exit_code=0, stdout=b"", stderr=b"", output=False)
    add("version", ["-v"], data=None, stdin=b"", exit_code=0, stdout=VERSION_STDOUT, stderr=b"", output=False)
    add("missing", ["-p", "chunk.lua"], data=None, stdin=b"", exit_code=1, stdout=b"", stderr=MISSING_STDERR, output=False)
    add("dump", ["chunk.lua"], data=b"return 1\n", stdin=b"", exit_code=0, stdout=b"", stderr=b"", output=True, prefix_ok=b"\x1bLua")
    passed = all(item["ok"] for item in checks)
    return {
        "build_ok": True,
        "make_exit": 0,
        "luac_sha256": _sha(installed.read_bytes()),
        "checks": checks,
        "dev_ok": passed,
        "accepted_pass": False,
        "opened_seal": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rrl-lua-base-") as temporary:
        report = build(args.prefix, Path(temporary))
    print(json.dumps(report, indent=2))
    return 0 if report.get("dev_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
