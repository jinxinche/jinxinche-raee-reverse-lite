"""Check frozen minigzip binaries on the sealed SQLite and NIST inputs.

Expected gzip bytes are not read from the tree. GNU gzip and CPython zlib are
the oracles. An injected CRC of 00000000 must fail, and a one-byte corruption
of each gzip stream must be rejected by both oracles. A seal or checker-hash
mismatch does not run the candidate and is not a pass.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.blind_acceptance import judge_observed_crc  # noqa: E402
from raee_reverse.blind_broad import (  # noqa: E402
    LABELS,
    gzip_oracle,
    load_manifest,
    read_member,
    verify_checker_files,
    verify_frozen_dependencies,
    verify_inputs,
    verify_seal,
)


def _gnu_gzip_version() -> str | None:
    binary = shutil.which("gzip")
    if not binary:
        return None
    probed = subprocess.run([binary, "--version"], capture_output=True, text=True, check=False)
    text = probed.stdout or probed.stderr or ""
    line = text.splitlines()[0].strip() if text else ""
    if re.match(r"^gzip \d", line) is None:
        return None
    return line


def _python_decompress(gzip_bytes: bytes) -> tuple[bool, bytes]:
    try:
        plain = zlib.decompress(gzip_bytes, wbits=16 + zlib.MAX_WBITS)
    except zlib.error:
        return False, b""
    return True, plain


def _corrupt_rejected(gzip_bytes: bytes, data: bytes) -> dict:
    if len(gzip_bytes) < 16:
        return {"ran": False, "rejected": False, "reason": "gzip stream too short to corrupt"}
    corrupted = bytearray(gzip_bytes)
    index = len(corrupted) // 2
    corrupted[index] ^= 0xFF
    payload = bytes(corrupted)
    with tempfile.TemporaryDirectory(prefix="rrl-broad-bad-") as tmp:
        external = gzip_oracle(payload, Path(tmp) / "bad")
    external_match = bool(external.get("ran") and external.get("returncode") == 0 and external.get("stdout") == data)
    decoded, plain = _python_decompress(payload)
    python_match = bool(decoded and plain == data)
    rejected = bool(external.get("ran") and not external_match and not python_match)
    return {
        "ran": True,
        "byte_index": index,
        "gzip_external_ran": external.get("ran"),
        "gzip_external_accepted_original": external_match,
        "python_zlib_accepted_original": python_match,
        "rejected": rejected,
    }


def _write(out: Path, report: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    label = sys.argv[1]
    minigzip = Path(sys.argv[2])
    crc_bin = Path(sys.argv[3])
    out = Path(sys.argv[4])
    build_path = Path(sys.argv[5]) if len(sys.argv) > 5 else None
    if label not in LABELS:
        raise SystemExit("label must be stock, attempt2, or attempt3")
    manifest = load_manifest(REPO)
    seal = verify_seal(REPO)
    checkers = verify_checker_files(REPO)
    frozen = verify_frozen_dependencies(REPO)
    inputs = verify_inputs(REPO)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False)
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    reproduction = None
    if build_path is not None and build_path.is_file():
        reproduction = json.loads(build_path.read_text(encoding="utf-8")).get(label)
    report = {
        "label": label,
        "executed": False,
        "pass": False,
        "blind": True,
        "blind_claim": True,
        "blind_reason": manifest["blind_reason"],
        "inputs_invented_for_this_candidate": False,
        "tuned_on_this_set": False,
        "expected_gzip_stored": False,
        "starting_ref": manifest["starting_ref"],
        "candidates_frozen_before_seal": True,
        "set_author": manifest["set_author"],
        "candidate_authors": manifest["candidate_authors"],
        "seal_time": manifest["seal_time"],
        "source_commit": head.stdout.strip(),
        "seal_match": seal["match"],
        "checker_match": all(item["matches_manifest"] for item in checkers),
        "frozen_dependency_match": all(item["matches_manifest"] for item in frozen),
        "inputs_match_manifest": all(item["matches_manifest"] for item in inputs),
        "oracle": "GNU gzip and CPython zlib",
        "gzip": _gnu_gzip_version(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_zlib": zlib.ZLIB_VERSION,
        "uname": uname.stdout.strip(),
        "machine": platform.machine(),
        "minigzip": str(minigzip),
        "minigzip_sha256": hashlib.sha256(minigzip.read_bytes()).hexdigest() if minigzip.is_file() else None,
        "crc_stdin": str(crc_bin),
        "crc_stdin_sha256": hashlib.sha256(crc_bin.read_bytes()).hexdigest() if crc_bin.is_file() else None,
        "reproduction": reproduction,
        "rows": [],
        "negative_controls": [],
        "unverified": [
            "Expected gzip bytes are not stored and are not compared across candidates.",
            "This report is the host that ran this process. Another host is a separate run.",
            "Wall time is not measured.",
            "The Canterbury corpus stays non-blind. The enwik8 records are not rewritten.",
        ],
        "unfinished": [],
    }
    ready = (
        seal["match"]
        and report["checker_match"]
        and report["frozen_dependency_match"]
        and report["inputs_match_manifest"]
        and minigzip.is_file()
        and crc_bin.is_file()
        and report["gzip"] is not None
    )
    if not ready:
        if not seal["match"] or not report["checker_match"] or not report["frozen_dependency_match"]:
            report["unfinished"].append("seal or checker hash mismatch; the candidate was not run")
        if not report["inputs_match_manifest"]:
            report["unfinished"].append("input bytes do not match the sealed manifest; the candidate was not run")
        if not minigzip.is_file() or not crc_bin.is_file():
            report["unfinished"].append("frozen binary or crc harness is missing")
        if report["gzip"] is None:
            report["unfinished"].append("GNU gzip is not on PATH; a missing oracle is not a pass")
        _write(out, report)
        print(json.dumps({"pass": False, "executed": False, "label": label}))
        return 1

    rows = []
    controls = []
    ok = True
    for item in manifest["inputs"]:
        _container, data = read_member(REPO, item)
        try:
            crc_run = subprocess.run([str(crc_bin)], input=data, capture_output=True, check=False, timeout=300)
            gzip_run = subprocess.run([str(minigzip)], input=data, capture_output=True, check=False, timeout=300)
        except subprocess.TimeoutExpired as exc:
            rows.append({"name": item["name"], "error": "timeout", "timeout_seconds": 300, "command": exc.cmd})
            ok = False
            report["unfinished"].append(f"{item['name']} timed out at 300 seconds")
            continue
        observed = crc_run.stdout.decode("ascii", "replace").strip()
        python_hex = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
        verdict = judge_observed_crc(observed, python_hex)
        with tempfile.TemporaryDirectory(prefix="rrl-broad-gzip-") as tmp:
            external = gzip_oracle(gzip_run.stdout, Path(tmp) / item["name"])
        external_match = bool(
            gzip_run.returncode == 0
            and external.get("ran")
            and external.get("returncode") == 0
            and external.get("stdout") == data
        )
        decoded, plain = _python_decompress(gzip_run.stdout) if gzip_run.returncode == 0 else (False, b"")
        python_match = bool(decoded and plain == data)
        injected = judge_observed_crc("00000000", python_hex)
        corrupt = _corrupt_rejected(gzip_run.stdout, data) if gzip_run.returncode == 0 else {
            "ran": False,
            "rejected": False,
            "reason": "minigzip did not produce a stream to corrupt",
        }
        control = {
            "name": item["name"],
            "injected_crc": "00000000",
            "python_crc32": python_hex,
            "judge_pass": injected["pass"],
            "judge_reason": injected["reason"],
            "failed_as_required": injected["pass"] is False,
            "corrupted_gzip": corrupt,
        }
        row = {
            "name": item["name"],
            "corpus": item["corpus"],
            "kind": item["kind"],
            "length": len(data),
            "sha256": item["sha256"],
            "crc_exit": crc_run.returncode,
            "observed_crc32": observed,
            "python_crc32": python_hex,
            "judge": verdict,
            "minigzip_exit": gzip_run.returncode,
            "minigzip_stdout_bytes": len(gzip_run.stdout),
            "gzip_external_ran": external.get("ran"),
            "gzip_external_match": external_match,
            "python_zlib_decompress_match": python_match,
            "negative_control": control,
        }
        rows.append(row)
        controls.append(control)
        ok = (
            ok
            and verdict["pass"]
            and crc_run.returncode == 0
            and gzip_run.returncode == 0
            and external_match
            and python_match
            and injected["pass"] is False
            and corrupt.get("rejected") is True
        )
    report["executed"] = True
    report["rows"] = rows
    report["negative_controls"] = controls
    report["sample_size"] = len(rows)
    report["pass"] = bool(ok and len(rows) == len(manifest["inputs"]) and len(controls) == len(rows))
    _write(out, report)
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "executed": True,
                "blind": True,
                "label": label,
                "sample_size": len(rows),
            }
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
