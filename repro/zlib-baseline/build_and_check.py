"""Build frozen zlib 1.4 and check dev inputs.

This file does not read targets/zlib/sealed_observations.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
TARBALL_SHA256 = "02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584"
HARNESS = REPO / "targets" / "zlib" / "harness" / "crc32_cli.c"
DEV_INPUTS = {"empty": b"", "abc": b"abc", "hello": b"hello"}
ABC_CRC32 = "352441c2"


def _extract(dest: Path) -> Path:
    blob = TARBALL.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != TARBALL_SHA256:
        raise SystemExit(f"tarball sha256 is {digest}, frozen pin is {TARBALL_SHA256}")
    root = dest.resolve()
    with tarfile.open(TARBALL, "r:gz") as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(f"tarball path escapes the work directory: {member.name}")
            archive.extract(member, root)
    return root / "zlib-1.4"


def _sandbox(argv: list[str], work: Path, data: bytes = b"", args: list[str] | None = None) -> dict:
    return run_sandboxed(
        [str(argv[0]), *argv[1:], *(args or [])],
        work_dir=work,
        stdin=data,
        timeout=180,
        cpu_seconds=120,
        fsize_bytes=80_000_000,
        max_output_bytes=2_000_000,
    )


def build(prefix: Path, work: Path) -> dict:
    source = _extract(work)
    configure = _sandbox(["./configure"], source)
    make = _sandbox(["make", "-j4"], source)
    if configure["returncode"] != 0 or make["returncode"] != 0:
        return {
            "executed": True,
            "build_ok": False,
            "configure_exit": configure["returncode"],
            "make_exit": make["returncode"],
            "configure_stderr": configure["stderr"].decode("utf-8", "replace")[-1000:],
            "make_stderr": make["stderr"].decode("utf-8", "replace")[-1000:],
            "accepted_pass": False,
        }
    prefix.mkdir(parents=True, exist_ok=True)
    bindir = prefix / "bin"
    bindir.mkdir(exist_ok=True)
    minigzip = bindir / "minigzip"
    shutil.copy2(source / "minigzip", minigzip)
    minigzip.chmod(0o755)
    crc_bin = bindir / "crc32_cli"
    compiled = subprocess.run(
        ["gcc", "-O2", "-o", str(crc_bin), str(HARNESS), f"-I{source}", str(source / "libz.a")],
        capture_output=True,
        text=True,
        check=False,
    )
    if compiled.returncode != 0:
        return {"executed": True, "build_ok": False, "harness_stderr": compiled.stderr[-1000:], "accepted_pass": False}
    return {
        "executed": True,
        "build_ok": True,
        "configure_exit": 0,
        "make_exit": 0,
        "prefix": str(prefix),
        "minigzip": str(minigzip),
        "crc32_cli": str(crc_bin),
        "source": str(source),
        "network_namespace": bool(make["network_namespace"]),
        "rlimits_applied": bool(make["rlimits_applied"]),
        "accepted_pass": False,
    }


def check_dev(prefix: Path, work: Path) -> dict:
    minigzip = prefix / "bin" / "minigzip"
    crc_bin = prefix / "bin" / "crc32_cli"
    outside = work / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, data in DEV_INPUTS.items():
        compressed = run_sandboxed(
            [str(minigzip)], work_dir=outside / name, stdin=data, timeout=20, cpu_seconds=10, fsize_bytes=5_000_000
        )
        decompressed = run_sandboxed(
            [str(minigzip), "-d"],
            work_dir=outside / f"{name}-dec",
            stdin=compressed["stdout"],
            timeout=20,
            cpu_seconds=10,
            fsize_bytes=5_000_000,
        )
        crc = run_sandboxed(
            [str(crc_bin)], work_dir=outside / f"{name}-crc", stdin=data, timeout=20, cpu_seconds=10
        )
        stdout = compressed["stdout"]
        magic_ok = stdout[:2] == b"\x1f\x8b" and stdout[4:8] == b"\x00\x00\x00\x00"
        roundtrip = decompressed["returncode"] == 0 and decompressed["stdout"] == data
        crc_text = crc["stdout"].decode("ascii", "replace").strip()
        row = {
            "name": name,
            "exit_code": compressed["returncode"],
            "roundtrip_equals_input": roundtrip,
            "gzip_magic_and_zero_mtime": magic_ok,
            "crc32_hex": crc_text,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(compressed["stderr"]).hexdigest(),
        }
        rows.append(row)
    abc = next(row for row in rows if row["name"] == "abc")
    ok = (
        all(row["exit_code"] == 0 and row["roundtrip_equals_input"] and row["gzip_magic_and_zero_mtime"] for row in rows)
        and abc["crc32_hex"] == ABC_CRC32
    )
    # The installed binary is invoked with a working directory that is not the zlib source tree.
    ran_outside = subprocess.run(
        [str(minigzip), "-d"],
        input=run_sandboxed([str(minigzip)], work_dir=outside / "install", stdin=b"abc", timeout=20)["stdout"],
        capture_output=True,
        cwd=outside,
        check=False,
    )
    return {
        "dev_ok": ok and ran_outside.returncode == 0 and ran_outside.stdout == b"abc",
        "rows": rows,
        "installed_binary_roundtrip_outside_source_tree": ran_outside.returncode == 0 and ran_outside.stdout == b"abc",
        "accepted_pass": False,
        "scope": "dev inputs empty, abc, and hello only",
        "read_final_acceptance_file": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    prefix = Path(args.prefix)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    if not TARBALL.is_file() or shutil.which("gcc") is None or shutil.which("make") is None:
        report = {
            "executed": False,
            "reason": "baseline build needs the vendored tarball, gcc, and make",
            "accepted_pass": False,
            "read_final_acceptance_file": False,
        }
        Path(args.result).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0
    built = build(prefix, work / "src")
    if not built.get("build_ok"):
        built["read_final_acceptance_file"] = False
        Path(args.result).write_text(json.dumps(built, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: built[k] for k in built if k in ("executed", "build_ok", "accepted_pass")}))
        return 1
    checked = check_dev(prefix, work / "check")
    report = {"build": {k: v for k, v in built.items() if k != "source"}, "dev": checked}
    Path(args.result).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"build_ok": True, "dev_ok": checked["dev_ok"], "read_final_acceptance_file": False}))
    return 0 if checked["dev_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
