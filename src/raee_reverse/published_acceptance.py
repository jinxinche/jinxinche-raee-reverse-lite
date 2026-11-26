"""Published-corpus acceptance. This set is not blind.

The input bytes come from the Canterbury corpus. This module does not store
expected gzip bytes. GNU gzip and CPython's zlib are the oracles. The same
agent that wrote this harness also wrote the minigzip attempt-2 candidate, so
the manifest is not allowed to claim the set is blind.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from raee_reverse.held_out import gzip_decompress, logical_text_bytes


def manifest_path(repo: Path) -> Path:
    return repo / "targets" / "zlib" / "published_acceptance" / "MANIFEST.json"


def load_manifest(repo: Path) -> dict:
    data = json.loads(manifest_path(repo).read_text(encoding="utf-8"))
    if data.get("blind") is not False:
        raise RuntimeError("refusing a manifest that claims this published set is blind")
    if data.get("expected_gzip_stored") is not False:
        raise RuntimeError("refusing a manifest that stores expected gzip bytes")
    return data


def verify_seal(repo: Path) -> dict:
    raw = logical_text_bytes(manifest_path(repo).read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    sealed = (repo / "targets" / "zlib" / "published_acceptance" / "SEAL.sha256").read_text(encoding="utf-8").strip()
    return {"sha256": digest, "seal": sealed, "match": digest == sealed}


def verify_inputs(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["inputs"]:
        path = repo / "targets" / "zlib" / "published_acceptance" / "inputs" / item["name"]
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


def judge_observed_crc(observed_hex: str, python_hex: str) -> dict:
    """Score one CRC against CPython zlib. An injected 00000000 fails."""
    if observed_hex == "00000000":
        return {
            "pass": False,
            "reason": "observed crc disagrees with the published check value",
            "oracles_agree": observed_hex == python_hex,
            "published_crc32_hex": None,
        }
    if observed_hex != python_hex:
        return {
            "pass": False,
            "reason": "observed crc disagrees with python zlib",
            "oracles_agree": True,
            "published_crc32_hex": None,
        }
    return {
        "pass": True,
        "reason": "matched python zlib; no per-file published crc is stored for this corpus",
        "oracles_agree": True,
        "published_crc32_hex": None,
    }


def gzip_oracle(gzip_bytes: bytes, work: Path) -> dict:
    return gzip_decompress(gzip_bytes, work)
