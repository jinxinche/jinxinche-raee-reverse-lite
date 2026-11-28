"""Build pinned Lua 5.4.9 and seal luac -p observations.

The same process chooses the inputs and writes the expected surfaces, so the
label is non-blind. Dev bytes are fixed below. Final bytes come from seed
20261126. This script does not read an existing sealed file to choose inputs.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.sandbox import run_sandboxed  # noqa: E402

TARBALL = ROOT / "targets" / "lua" / "dist" / "lua-5.4.9.tar.gz"
PIN_PATH = ROOT / "targets" / "lua" / "PIN.json"
SEAL_PATH = ROOT / "targets" / "lua" / "sealed_observations.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "lua_phase2.json"
SOURCE_URL = "https://www.lua.org/ftp/lua-5.4.9.tar.gz"
TARBALL_SHA256 = "2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6"

DEV_FILES = {
    "empty": b"",
    "return1": b"return 1\n",
    "print_abc": b'print("abc")\n',
    "syntax_error": b"local =\n",
}
TUNE_FILES = {
    "tune-locals": "".join(f"local v{i} = {i}\n" for i in range(40)).encode(),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract(archive: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise SystemExit(f"tarball path escapes the work directory: {member.name}")
        archive.extract(member, root)


def _elf(data: bytes) -> dict:
    if len(data) < 20 or data[:4] != b"\x7fELF":
        return {"elf": False}
    return {
        "elf": True,
        "class": data[4],
        "endian": data[5],
        "type": int.from_bytes(data[16:18], "little"),
        "machine": int.from_bytes(data[18:20], "little"),
        "class_name": "ELF64" if data[4] == 2 else "other",
        "machine_name": "x86-64" if int.from_bytes(data[18:20], "little") == 62 else "other",
    }


def _run(work: Path, args: list[str], stdin: bytes = b"") -> dict:
    # A relative Path stringifies to "luac" and prlimit then misses the work-dir copy.
    return run_sandboxed(
        ["./luac", *args],
        work_dir=work,
        stdin=stdin,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )


def _case(binary: Path, parent: Path, name: str, data: bytes | None, args: list[str], stdin: bytes = b"") -> dict:
    work = parent / name
    work.mkdir(parents=True)
    binary_copy = work / "luac"
    binary_copy.write_bytes(binary.read_bytes())
    binary_copy.chmod(0o755)
    if data is not None:
        (work / "chunk.lua").write_bytes(data)
    result = _run(work, args, stdin)
    output = work / "luac.out"
    stdout = result["stdout"]
    stderr = result["stderr"]
    return {
        "args": args,
        "stdin_sha256": _sha(stdin),
        "input_sha256": None if data is None else _sha(data),
        "exit_code": result["returncode"],
        "stdout_sha256": _sha(stdout),
        "stderr_sha256": _sha(stderr),
        "stdout_preview": stdout[:180].decode("utf-8", "replace"),
        "stderr_preview": stderr[:180].decode("utf-8", "replace"),
        "output_file_exists": output.exists(),
        "output_file_sha256": _sha(output.read_bytes()) if output.exists() else None,
        "execution_result": result["execution_result"],
        "truncated": result["truncated"],
        "rlimits_applied": result["rlimits_applied"],
        "network_namespace": result["network_namespace"],
        "limitations": result["limitations"],
    }


def _public(row: dict) -> dict:
    return dict(row)


def _final_files() -> dict[str, bytes]:
    rng = random.Random(20261126)
    files: dict[str, bytes] = {}
    for index in range(4):
        count = rng.randint(1, 5)
        body = "".join(f"local v{j} = {rng.randint(0, 999)}\n" for j in range(count))
        files[f"valid-{index}"] = body.encode()
    files["invalid-0"] = b"local =\n"
    files["invalid-1"] = b"return =\n"
    return files


def _compare(left: dict, right: dict) -> dict:
    names = (
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "output_file_exists",
        "output_file_sha256",
    )
    surfaces = {}
    for name in names:
        if left.get("truncated") or right.get("truncated"):
            surfaces[name] = "not_compared"
        elif left.get(name) == right.get(name):
            surfaces[name] = "match"
        else:
            surfaces[name] = "mismatch"
    return {
        "surfaces": surfaces,
        "compatible_on_collected_surfaces": all(item == "match" for item in surfaces.values()),
        "universal": False,
        "accepted_pass": False,
    }


def main() -> int:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    blob = TARBALL.read_bytes()
    if _sha(blob) != TARBALL_SHA256 or pin["tarball_sha256"] != TARBALL_SHA256:
        raise SystemExit("tarball sha256 does not match the frozen pin")
    if pin["source_url"] != SOURCE_URL:
        raise SystemExit("source url does not match the frozen pin")
    with tempfile.TemporaryDirectory(prefix="rrl-lua-") as temporary:
        root = Path(temporary)
        with tarfile.open(TARBALL, "r:gz") as archive:
            _extract(archive, root)
        source = root / "lua-5.4.9"
        build = run_sandboxed(
            ["make", "linux"],
            work_dir=source,
            timeout=180,
            cpu_seconds=120,
            fsize_bytes=80_000_000,
            max_output_bytes=4_000_000,
        )
        luac = source / "src" / "luac"
        if build["returncode"] != 0 or build["truncated"] or not luac.is_file():
            tail = build["stderr"][-500:] + build["stdout"][-500:]
            raise SystemExit(f"lua build failed exit={build['returncode']} truncated={build['truncated']} {tail!r}")
        binary = luac.read_bytes()
        cases_parent = root / "cases"
        observed: dict[str, dict] = {}
        for name, data in DEV_FILES.items():
            observed[f"dev:{name}"] = _case(luac, cases_parent, f"dev-{name}", data, ["-p", "chunk.lua"])
        observed["dev:return1-stdin"] = _case(luac, cases_parent, "dev-stdin", None, ["-p", "-"], DEV_FILES["return1"])
        observed["dev:return1-dump"] = _case(luac, cases_parent, "dev-dump", DEV_FILES["return1"], ["chunk.lua"])
        observed["dev:version"] = _case(luac, cases_parent, "dev-version", None, ["-v"])
        observed["dev:missing"] = _case(luac, cases_parent, "dev-missing", None, ["-p", "chunk.lua"])
        observed["dev:unknown-option"] = _case(luac, cases_parent, "dev-unknown", None, ["-z"])
        for name, data in TUNE_FILES.items():
            observed[f"tune:{name}"] = _case(luac, cases_parent, f"tune-{name}", data, ["-p", "chunk.lua"])
        final_files = _final_files()
        for name, data in final_files.items():
            observed[f"final:{name}"] = _case(luac, cases_parent, f"final-{name}", data, ["-p", "chunk.lua"])
        second_parent = root / "second"
        second = {}
        comparisons = {}
        for name, data in final_files.items():
            second[name] = _case(luac, second_parent, f"final-{name}", data, ["-p", "chunk.lua"])
            comparisons[name] = _compare(observed[f"final:{name}"], second[name])
        rerun_match = all(item["compatible_on_collected_surfaces"] for item in comparisons.values())
        pin_out = {
            "project": "lua",
            "tag": "5.4.9",
            "source_url": SOURCE_URL,
            "tarball_sha256": TARBALL_SHA256,
            "license": pin["license"],
            "tool": "luac",
            "interface": pin["interface"],
            "kind": pin["kind"],
            "pinned_before_analysis": True,
            "luac_sha256": _sha(binary),
            "elf": _elf(binary),
            "build": {
                "command": "make linux",
                "make_exit": build["returncode"],
                "sandbox": True,
                "rlimits_applied": bool(build["rlimits_applied"]),
                "network_namespace": bool(build["network_namespace"]),
                "truncated": bool(build["truncated"]),
            },
            "acceptance": "non-blind",
            "acceptance_reason": "the same agent generated the sealed outputs and can read them",
        }
        sealed = {
            "project": "lua",
            "tool": "luac -p",
            "synthetic": False,
            "acceptance": "non-blind",
            "acceptance_reason": pin_out["acceptance_reason"],
            "final_seed": 20261126,
            "final_rule": "four valid chunks of 1 to 5 locals, plus the two invalid chunks local = and return =",
            "ghidra": {
                "executed": False,
                "accepted_pass": False,
                "reason": "Ghidra is not installed. Static decompilation was not run. That is not a pass.",
            },
            "cases": {key: _public(row) for key, row in observed.items()},
            "final_rerun": comparisons,
            "final_rerun_match": rerun_match,
        }
        evidence = {
            "kind": "lua-5.4.9-luac-p-phase2",
            "synthetic": False,
            "acceptance": "non-blind",
            "pin": pin_out,
            "ghidra": sealed["ghidra"],
            "final_rerun_match": rerun_match,
            "dev": {key: _public(row) for key, row in observed.items() if key.startswith("dev:")},
            "behavior": _behavior(observed),
        }
    PIN_PATH.write_text(json.dumps(pin_out, indent=2) + "\n", encoding="utf-8")
    SEAL_PATH.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"final_rerun_match": rerun_match, "luac_sha256": pin_out["luac_sha256"], "elf": pin_out["elf"]}, indent=2))
    return 0 if rerun_match else 1


def _behavior(observed: dict) -> dict:
    parse_ok = observed["dev:return1"]
    parse_bad = observed["dev:syntax_error"]
    dumped = observed["dev:return1-dump"]
    version = observed["dev:version"]
    stdin_row = observed["dev:return1-stdin"]
    return {
        "parse_only_exit_0_on_return1": parse_ok["exit_code"] == 0 and parse_ok["execution_result"] == "passed",
        "parse_only_writes_no_output_file_on_return1": parse_ok["output_file_exists"] is False,
        "syntax_error_exit": parse_bad["exit_code"],
        "syntax_error_stderr_nonempty": bool(parse_bad["stderr_preview"]),
        "dump_without_p_writes_output_file": dumped["output_file_exists"] is True and dumped["exit_code"] == 0,
        "stdin_matches_file_on_return1": (
            stdin_row["exit_code"] == parse_ok["exit_code"]
            and stdin_row["stdout_sha256"] == parse_ok["stdout_sha256"]
            and stdin_row["output_file_exists"] == parse_ok["output_file_exists"]
        ),
        "version_exit": version["exit_code"],
        "version_preview": version["stdout_preview"],
        "missing_exit": observed["dev:missing"]["exit_code"],
        "missing_stderr_preview": observed["dev:missing"]["stderr_preview"],
        "unknown_option_exit": observed["dev:unknown-option"]["exit_code"],
        "unknown_option_stderr_preview": observed["dev:unknown-option"]["stderr_preview"],
        "syntax_error_stderr_preview": parse_bad["stderr_preview"],
        "return1_stderr_preview": parse_ok["stderr_preview"],
        "empty_exit": observed["dev:empty"]["exit_code"],
        "empty_stderr_preview": observed["dev:empty"]["stderr_preview"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
