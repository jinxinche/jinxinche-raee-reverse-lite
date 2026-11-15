"""Held-out zlib checks. This set is not blind.

One agent wrote the inputs, this checker, and the candidate. Expected gzip
bytes are not stored. The published CRC of the ASCII bytes 123456789 is an
external check value, not an agent-measured expected file.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

PUBLISHED_CRC32 = {
    "itu-123456789": {
        "crc32_hex": "cbf43926",
        "source": "ISO-HDLC CRC-32 check value for the ASCII bytes 123456789, the value zlib's crc32 test uses",
    }
}


def manifest_path(repo: Path) -> Path:
    return repo / "targets" / "zlib" / "held_out" / "MANIFEST.json"


def load_manifest(repo: Path) -> dict:
    data = json.loads(manifest_path(repo).read_text(encoding="utf-8"))
    if data.get("blind") is not False:
        raise RuntimeError("refusing a manifest that claims this set is blind")
    return data


def logical_text_bytes(data: bytes) -> bytes:
    """Hash text after turning CRLF into LF. Binary input is left alone.

    Windows checkout rewrites text files. The seal is of the LF manifest.
    """
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def verify_seal(repo: Path) -> dict:
    raw = logical_text_bytes(manifest_path(repo).read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    sealed = (repo / "targets" / "zlib" / "held_out" / "SEAL.sha256").read_text(encoding="utf-8").strip()
    return {"sha256": digest, "seal": sealed, "match": digest == sealed}


def verify_inputs(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["inputs"]:
        path = repo / "targets" / "zlib" / "held_out" / "inputs" / item["name"]
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        found.append(
            {
                "name": item["name"],
                "sha256": digest,
                "length": len(data),
                "matches_manifest": digest == item["sha256"] and len(data) == item["length"],
            }
        )
    return found


def judge_crc(name: str, observed_hex: str, python_hex: str) -> dict:
    """Score one CRC. A mismatched published value fails. Oracles that disagree fail."""
    published = PUBLISHED_CRC32.get(name)
    published_hex = published["crc32_hex"] if published else None
    if published_hex is not None and python_hex != published_hex:
        return {
            "pass": False,
            "reason": "python zlib disagrees with the published check value",
            "oracles_agree": False,
            "published_crc32_hex": published_hex,
        }
    if published_hex is not None and observed_hex != published_hex:
        return {
            "pass": False,
            "reason": "observed crc disagrees with the published check value",
            "oracles_agree": True,
            "published_crc32_hex": published_hex,
        }
    if observed_hex != python_hex:
        return {
            "pass": False,
            "reason": "observed crc disagrees with python zlib",
            "oracles_agree": True,
            "published_crc32_hex": published_hex,
        }
    return {
        "pass": True,
        "reason": "matched the crc checks that apply to this input",
        "oracles_agree": True,
        "published_crc32_hex": published_hex,
    }


def gzip_decompress(gzip_bytes: bytes, work: Path) -> dict:
    """Ask the system gzip to decompress. Missing gzip is not a pass."""
    binary = shutil.which("gzip")
    if binary is None:
        return {"ran": False, "reason": "gzip executable not found", "matched_input": None}
    work.mkdir(parents=True, exist_ok=True)
    target = work / "payload.gz"
    target.write_bytes(gzip_bytes)
    completed = subprocess.run(
        [binary, "-dc", str(target)],
        capture_output=True,
        check=False,
    )
    return {
        "ran": True,
        "gzip": binary,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-200:],
    }
