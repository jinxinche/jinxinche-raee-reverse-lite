"""Build pinned aklomp/base64 0.5.3 and seal stdin/stdout observations.

The same process chooses the inputs and writes the expected surfaces, so the
label is non-blind. Dev bytes are fixed below. Final bytes come from seed
20261126. Default `make` is the build. No AVX or OpenMP flag is added here.
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

TARBALL = ROOT / "targets" / "base64" / "dist" / "base64-0.5.3.tar.gz"
PIN_PATH = ROOT / "targets" / "base64" / "PIN.json"
SEAL_PATH = ROOT / "targets" / "base64" / "sealed_observations.json"
EVIDENCE_PATH = ROOT / "docs" / "evidence" / "base64_phase2.json"
SOURCE_URL = "https://github.com/aklomp/base64/archive/refs/tags/v0.5.3.tar.gz"
TARBALL_SHA256 = "74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42"

DEV_INPUTS = {
    "empty": b"",
    "abc": b"abc",
    "hello": b"hello",
    "nul": b"\x00\x01\xff",
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
    return run_sandboxed(
        ["./base64", *args],
        work_dir=work,
        stdin=stdin,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=2_000_000,
    )


def _prepare(binary: Path, parent: Path, name: str, file_bytes: bytes | None) -> Path:
    work = parent / name
    work.mkdir(parents=True)
    copy = work / "base64"
    copy.write_bytes(binary.read_bytes())
    copy.chmod(0o755)
    if file_bytes is not None:
        (work / "input.bin").write_bytes(file_bytes)
    return work


def _row(result: dict, stdin: bytes, file_sha: str | None, args: list[str]) -> dict:
    stdout = result["stdout"]
    stderr = result["stderr"]
    return {
        "args": args,
        "stdin_sha256": _sha(stdin),
        "file_sha256": file_sha,
        "exit_code": result["returncode"],
        "stdout_sha256": _sha(stdout),
        "stderr_sha256": _sha(stderr),
        "stdout_preview": stdout[:120].decode("utf-8", "replace"),
        "stderr_preview": stderr[:180].decode("utf-8", "replace"),
        "stdout_has_newline": b"\n" in stdout,
        "execution_result": result["execution_result"],
        "truncated": result["truncated"],
        "rlimits_applied": result["rlimits_applied"],
        "network_namespace": result["network_namespace"],
        "limitations": result["limitations"],
    }


def _encode(binary: Path, parent: Path, name: str, data: bytes, args: list[str], *, use_file: bool) -> dict:
    work = _prepare(binary, parent, name, data if use_file else None)
    if use_file:
        result = _run(work, [*args, "input.bin"], b"")
        stdin = b""
        file_sha = _sha(data)
    else:
        result = _run(work, args, data)
        stdin = data
        file_sha = None
    row = _row(result, stdin, file_sha, args if not use_file else [*args, "input.bin"])
    row["input_sha256"] = _sha(data)
    return row


def _decode(binary: Path, parent: Path, name: str, data: bytes, expected: bytes | None = None) -> dict:
    work = _prepare(binary, parent, name, None)
    result = _run(work, ["-d"], data)
    row = _row(result, data, None, ["-d"])
    row["input_sha256"] = _sha(data)
    if expected is not None:
        row["roundtrip_equals_input"] = (
            not result["truncated"] and result["returncode"] == 0 and result["stdout"] == expected
        )
    return row


def _final_inputs() -> dict[str, bytes]:
    rng = random.Random(20261126)
    lengths = (4, 7, 57, 58, 76, 120)
    return {f"len-{length}": bytes(rng.getrandbits(8) for _ in range(length)) for length in lengths}


def _compare(left: dict, right: dict) -> dict:
    names = ("exit_code", "stdout_sha256", "stderr_sha256", "stdout_has_newline")
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


def _public(row: dict) -> dict:
    copied = dict(row)
    copied.pop("stdout_preview", None)
    copied.pop("stderr_preview", None)
    return copied


def main() -> int:
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    blob = TARBALL.read_bytes()
    if _sha(blob) != TARBALL_SHA256 or pin["tarball_sha256"] != TARBALL_SHA256:
        raise SystemExit("tarball sha256 does not match the frozen pin")
    if pin["source_url"] != SOURCE_URL:
        raise SystemExit("source url does not match the frozen pin")
    with tempfile.TemporaryDirectory(prefix="rrl-base64-") as temporary:
        root = Path(temporary)
        with tarfile.open(TARBALL, "r:gz") as archive:
            _extract(archive, root)
        source = root / "base64-0.5.3"
        build = run_sandboxed(
            ["make", "-j4"],
            work_dir=source,
            timeout=180,
            cpu_seconds=120,
            fsize_bytes=80_000_000,
            max_output_bytes=4_000_000,
        )
        binary_path = source / "bin" / "base64"
        config_path = source / "lib" / "config.h"
        if build["returncode"] != 0 or build["truncated"] or not binary_path.is_file():
            tail = build["stderr"][-800:] + build["stdout"][-800:]
            raise SystemExit(f"base64 build failed exit={build['returncode']} truncated={build['truncated']} {tail!r}")
        binary = binary_path.read_bytes()
        config_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
        parent = root / "cases"
        observed: dict[str, dict] = {}
        for name, data in DEV_INPUTS.items():
            observed[f"dev:{name}"] = _encode(binary_path, parent, f"dev-{name}", data, [], use_file=False)
            observed[f"dev:{name}-nowrap"] = _encode(binary_path, parent, f"dev-{name}-nowrap", data, ["-w", "0"], use_file=False)
        observed["dev:abc-file"] = _encode(binary_path, parent, "dev-abc-file", DEV_INPUTS["abc"], [], use_file=True)
        for name, data in DEV_INPUTS.items():
            work = _prepare(binary_path, parent, f"enc2-{name}", None)
            encoded_run = _run(work, [], data)
            observed[f"dev:{name}"]["encode_repeat_matches"] = (
                not encoded_run["truncated"] and _sha(encoded_run["stdout"]) == observed[f"dev:{name}"]["stdout_sha256"]
            )
            observed[f"dev:{name}-decode"] = _decode(
                binary_path, parent, f"dec2-{name}", encoded_run["stdout"], expected=data
            )
        observed["dev:invalid-decode"] = _decode(binary_path, parent, "dev-invalid", b"!!!!")
        help_work = _prepare(binary_path, parent, "dev-help", None)
        observed["dev:help"] = _row(_run(help_work, ["-h"], b""), b"", None, ["-h"])
        unknown_work = _prepare(binary_path, parent, "dev-unknown", None)
        observed["dev:unknown-option"] = _row(_run(unknown_work, ["-z"], b""), b"", None, ["-z"])
        final_inputs = _final_inputs()
        for name, data in final_inputs.items():
            encoded = _encode(binary_path, parent, f"final-{name}", data, [], use_file=False)
            work = _prepare(binary_path, parent, f"final-enc-{name}", None)
            encoded_run = _run(work, [], data)
            encoded["encode_repeat_matches"] = (
                not encoded_run["truncated"] and _sha(encoded_run["stdout"]) == encoded["stdout_sha256"]
            )
            decoded = _decode(binary_path, parent, f"final-dec-{name}", encoded_run["stdout"], expected=data)
            encoded["roundtrip_equals_input"] = decoded["roundtrip_equals_input"]
            observed[f"final:{name}"] = encoded
        second = {}
        comparisons = {}
        second_parent = root / "second"
        for name, data in final_inputs.items():
            second[name] = _encode(binary_path, second_parent, f"final-{name}", data, [], use_file=False)
            comparisons[name] = _compare(observed[f"final:{name}"], second[name])
        rerun_match = all(item["compatible_on_collected_surfaces"] for item in comparisons.values())
        pin_out = {
            "project": "base64",
            "upstream": "aklomp/base64",
            "tag": "v0.5.3",
            "source_url": SOURCE_URL,
            "tarball_sha256": TARBALL_SHA256,
            "license": pin["license"],
            "tool": "bin/base64",
            "interface": pin["interface"],
            "kind": pin["kind"],
            "pinned_before_analysis": True,
            "base64_sha256": _sha(binary),
            "elf": _elf(binary),
            "codec_config": config_text,
            "build": {
                "command": "make -j4",
                "make_exit": build["returncode"],
                "extra_cflags": None,
                "sandbox": True,
                "rlimits_applied": bool(build["rlimits_applied"]),
                "network_namespace": bool(build["network_namespace"]),
                "truncated": bool(build["truncated"]),
            },
            "acceptance": "non-blind",
            "acceptance_reason": "the same agent generated the sealed outputs and can read them",
        }
        sealed = {
            "project": "base64",
            "tool": "bin/base64",
            "synthetic": False,
            "acceptance": "non-blind",
            "acceptance_reason": pin_out["acceptance_reason"],
            "final_seed": 20261126,
            "final_rule": "lengths 4, 7, 57, 58, 76, and 120 from Random(20261126) bytes",
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
            "kind": "base64-0.5.3-phase2",
            "synthetic": False,
            "acceptance": "non-blind",
            "pin": pin_out,
            "ghidra": sealed["ghidra"],
            "final_rerun_match": rerun_match,
            "codec_config": config_text,
            "dev_previews": {
                key: {
                    "exit_code": row["exit_code"],
                    "stdout_preview": row.get("stdout_preview", ""),
                    "stderr_preview": row.get("stderr_preview", ""),
                    "stdout_has_newline": row.get("stdout_has_newline"),
                    "roundtrip_equals_input": row.get("roundtrip_equals_input"),
                }
                for key, row in observed.items()
                if key.startswith("dev:")
            },
        }
    PIN_PATH.write_text(json.dumps(pin_out, indent=2) + "\n", encoding="utf-8")
    SEAL_PATH.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"final_rerun_match": rerun_match, "base64_sha256": pin_out["base64_sha256"], "elf": pin_out["elf"], "config": config_text}, indent=2))
    return 0 if rerun_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
