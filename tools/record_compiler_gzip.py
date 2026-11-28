"""Build zlib 1.4 minigzip with gcc and clang and compare gzip bytes."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.compiler_gzip import INPUTS, REQUESTED_CFLAGS, build_minigzip, compress_inputs, compare_outputs  # noqa: E402

TARBALL = ROOT / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
PIN = ROOT / "targets" / "zlib" / "PIN.json"
OUT = ROOT / "docs" / "evidence" / "compiler_gzip_bytes.json"


def _version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else f"exit {completed.returncode}"


def _public(rows: list[dict]) -> list[dict]:
    copied = []
    for row in rows:
        item = dict(row)
        item.pop("_stdout", None)
        copied.append(item)
    return copied


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    digest = hashlib.sha256(TARBALL.read_bytes()).hexdigest()
    if digest != pin["tarball_sha256"]:
        raise SystemExit("tarball sha256 does not match PIN.json")
    record = {
        "kind": "zlib-1.4-compiler-gzip",
        "accepted_pass": False,
        "tarball_sha256": digest,
        "requested_cflags": REQUESTED_CFLAGS,
        "host": {
            "system": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "gcc_version": _version("gcc"),
        "clang_version": _version("clang"),
        "inputs": [{"name": name, "sha256": hashlib.sha256(data).hexdigest(), "length": len(data)} for name, data in INPUTS],
        "builds": {},
        "outputs": {},
        "identical": None,
        "same_flags": None,
        "limitations": [
            "gzip bytes are the minigzip stdout from this host",
            "accepted_pass stays false; this file is not an enhancement goal",
        ],
    }
    if record["gcc_version"] is None or record["clang_version"] is None:
        record["limitations"].append("gcc or clang was not on PATH, so the byte comparison was not run")
        OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(OUT)
        return 1
    with tempfile.TemporaryDirectory(prefix="rrl-compiler-gzip-") as temporary:
        root = Path(temporary)
        builds = {}
        outputs = {}
        for compiler in ("gcc", "clang"):
            builds[compiler] = build_minigzip(root / compiler, compiler, TARBALL)
            binary = builds[compiler]["binary"]
            if builds[compiler]["make_exit"] != 0 or builds[compiler]["configure_exit"] != 0 or not binary:
                record["builds"] = builds
                record["limitations"].append(f"{compiler} build did not produce minigzip")
                OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
                print(OUT)
                return 1
            outputs[compiler] = compress_inputs(binary, root / compiler / "runs")
        comparison = compare_outputs(outputs["gcc"], outputs["clang"])
        record["builds"] = builds
        record["outputs"] = {name: _public(rows) for name, rows in outputs.items()}
        record["comparison"] = comparison
        record["identical"] = bool(comparison["identical"])
        record["same_flags"] = (
            builds["gcc"]["requested_cflags"] == builds["clang"]["requested_cflags"] == REQUESTED_CFLAGS
            and builds["gcc"]["compile_line_has_requested_cflags"]
            and builds["clang"]["compile_line_has_requested_cflags"]
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print("identical", record["identical"], "same_flags", record["same_flags"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
