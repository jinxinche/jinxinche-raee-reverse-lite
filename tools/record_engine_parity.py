"""Compare radare2/rizin function lists with the committed Ghidra export of minigzip."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.backup_engine import analyze_backup, locate_backend  # noqa: E402
from raee_reverse.compiler_gzip import REQUESTED_CFLAGS, build_minigzip  # noqa: E402
from raee_reverse.engine_parity import compare_catalogs, parse_ghidra_export, program_entry_from_name  # noqa: E402

TARBALL = ROOT / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
PIN = ROOT / "targets" / "zlib" / "PIN.json"
GHIDRA = ROOT / "docs" / "evidence" / "zlib_phase2.json"
OUT = ROOT / "docs" / "evidence" / "engine_parity_zlib.json"


def elf_entry(path: Path) -> int | None:
    data = path.read_bytes()
    if len(data) < 32 or data[:4] != b"\x7fELF":
        return None
    endian = "<" if data[5] == 1 else ">"
    if data[4] == 2:
        return struct.unpack_from(endian + "Q", data, 24)[0]
    if data[4] == 1:
        return struct.unpack_from(endian + "I", data, 24)[0]
    return None


def _apt(package: str) -> str:
    if shutil.which("apt-cache") is None:
        return "apt-cache is not installed"
    try:
        policy = subprocess.run(
            ["apt-cache", "policy", package],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        shown = subprocess.run(
            ["apt-cache", "show", package],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    text = (policy.stdout or "").strip()
    if not text:
        err = (shown.stderr or shown.stdout or policy.stderr or "").strip()
        text = f"apt-cache policy {package} exited {policy.returncode} with empty output; apt-cache show exited {shown.returncode}: {err or 'no text'}"
    return text[:500]


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    evidence = json.loads(GHIDRA.read_text(encoding="utf-8"))
    export = evidence["ghidra"]["export_text"]
    ghidra_functions = parse_ghidra_export(export)
    ghidra_entry = program_entry_from_name(ghidra_functions, "_start")
    located = locate_backend()
    record = {
        "kind": "zlib-1.4-engine-parity",
        "accepted_pass": False,
        "host": {"system": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
        "ghidra": {
            "executed_this_run": False,
            "source": "docs/evidence/zlib_phase2.json",
            "export_sha256": hashlib.sha256(export.encode("utf-8")).hexdigest(),
            "binary_sha256": pin["minigzip_sha256"],
            "functions": ghidra_functions,
            "program_entry": ghidra_entry,
            "program_entry_name": "_start",
        },
        "backup": {
            "installed": located["installed"],
            "locate": located,
            "rizin_apt_policy": _apt("rizin"),
            "radare2_apt_policy": _apt("radare2"),
            "angr_installed": importlib.util.find_spec("angr") is not None,
            "angr_selected": False,
            "angr_note": "angr was not selected; r2pipe is the lighter interface and angr was not imported",
        },
        "same_binary": False,
        "parity_executed": False,
        "identical": None,
        "disagreements": None,
        "limitations": [
            "Ghidra was not executed in this run; its function list is the committed export",
            "accepted_pass stays false; a disagreement list is not a behavior proof",
        ],
    }
    if not located["installed"]:
        record["limitations"].append("the backup engine could not be started: " + json.dumps(located))
        OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(OUT)
        return 1
    if shutil.which("gcc") is None or shutil.which("make") is None:
        record["limitations"].append("gcc or make was not on PATH, so minigzip was not rebuilt for this comparison")
        OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(OUT)
        return 1
    digest = hashlib.sha256(TARBALL.read_bytes()).hexdigest()
    if digest != pin["tarball_sha256"]:
        raise SystemExit("tarball sha256 does not match PIN.json")
    with tempfile.TemporaryDirectory(prefix="rrl-engine-parity-") as temporary:
        built = build_minigzip(Path(temporary), "gcc", TARBALL, cflags=REQUESTED_CFLAGS)
        record["build"] = {key: value for key, value in built.items() if key not in {"configure_stderr_tail", "make_stderr_tail"}}
        record["build"]["configure_exit"] = built["configure_exit"]
        record["build"]["make_exit"] = built["make_exit"]
        if built["make_exit"] != 0 or not built["binary"]:
            record["build"]["make_stderr_tail"] = built["make_stderr_tail"]
            record["limitations"].append("minigzip did not build, so the backup engine was not run on it")
            OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(OUT)
            return 1
        binary = Path(built["binary"])
        analysis = analyze_backup(binary, budget={"timeout": 180})
        record["backup"]["analysis"] = {key: value for key, value in analysis.items() if key != "functions"}
        record["backup"]["functions"] = analysis.get("functions") or []
        record["backup"]["binary_sha256"] = built["binary_sha256"]
        record["backup"]["elf_entry"] = elf_entry(binary)
        record["same_binary"] = built["binary_sha256"] == pin["minigzip_sha256"]
        if analysis.get("execution_result") != "passed":
            record["limitations"].append("the backup engine did not return a function list")
            OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(OUT)
            return 1
        disagreements = compare_catalogs(
            ghidra_functions,
            record["backup"]["functions"],
            ghidra_entry=ghidra_entry,
            backup_entry=analysis.get("program_entry"),
        )
        record["disagreements"] = disagreements
        record["identical"] = disagreements["identical"]
        record["parity_executed"] = True
        if not record["same_binary"]:
            record["limitations"].append(
                "the rebuilt minigzip sha256 differs from the pinned Ghidra binary, so entry points are still listed and are not the same image"
            )
        backup_entry = analysis.get("program_entry")
        elf = record["backup"]["elf_entry"]
        record["backup_entry_matches_elf"] = backup_entry == elf if backup_entry is not None and elf is not None else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print(
        "parity_executed",
        record["parity_executed"],
        "identical",
        record["identical"],
        "same_binary",
        record["same_binary"],
        "counts",
        record["disagreements"]["counts"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
