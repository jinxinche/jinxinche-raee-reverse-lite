"""Blind acceptance for the frozen zlib minigzip candidates.

The input is the published enwik8 prefix. Expected gzip bytes are not stored.
GNU gzip and CPython zlib are the oracles. The set author is not the agent
that wrote the candidates, and the candidates were already frozen at
``STARTING_REF`` before this manifest existed.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from raee_reverse.held_out import gzip_decompress, logical_text_bytes

STARTING_REF = "8a06e96fffff1cfe6958010babaea5a9308d4961"
SET_AGENT = "bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4"
CANDIDATE_AGENT = "bc-641141af-3ffd-5b16-acb9-663777242042"
CANTERBURY_TAR_SHA256 = "f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb"
PUBLISHED_MD5 = "a1fa5ffddb56f4953e226637dabbb36a"
PUBLISHED_SHA1 = "57b8363b814821dc9d47aa4d41f58733519076b2"
PUBLISHED_LENGTH = 100_000_000
TREE = Path("targets") / "zlib" / "blind_acceptance"


def tree(repo: Path) -> Path:
    return repo / TREE


def manifest_path(repo: Path) -> Path:
    return tree(repo) / "MANIFEST.json"


def load_manifest(repo: Path) -> dict:
    data = json.loads(manifest_path(repo).read_text(encoding="utf-8"))
    if data.get("expected_gzip_stored") is not False:
        raise RuntimeError("refusing a manifest that stores expected gzip bytes")
    if data.get("inputs_invented_for_this_candidate") is not False:
        raise RuntimeError("refusing inputs invented for this candidate")
    if data.get("tuned_on_this_set") is not False:
        raise RuntimeError("refusing a manifest that was tuned on this set")
    if data.get("blind") is not True or data.get("blind_claim") is not True:
        raise RuntimeError("this sealed set is the blind enwik8 check")
    if data.get("candidates_frozen_before_seal") is not True:
        raise RuntimeError("candidates were not recorded as frozen before the seal")
    if data.get("starting_ref") != STARTING_REF:
        raise RuntimeError("starting_ref is not the frozen tip")
    set_author = data.get("set_author") or {}
    candidate_authors = data.get("candidate_authors") or {}
    if set_author.get("agent") != SET_AGENT:
        raise RuntimeError("set author does not match this checker run")
    if candidate_authors.get("agent") != CANDIDATE_AGENT:
        raise RuntimeError("candidate author does not match the earlier agent")
    if set_author.get("agent") == candidate_authors.get("agent"):
        raise RuntimeError("set author and candidate author are the same agent")
    if data.get("origin_zip_sha256") == CANTERBURY_TAR_SHA256:
        raise RuntimeError("refusing the already-used Canterbury tarball")
    inputs = data.get("inputs") or []
    if len(inputs) != 1 or inputs[0].get("name") != "enwik8":
        raise RuntimeError("the sealed corpus is the single published enwik8 member")
    item = inputs[0]
    if item.get("md5") != PUBLISHED_MD5 or item.get("sha1") != PUBLISHED_SHA1:
        raise RuntimeError("manifest does not carry the published enwik8 checksums")
    if item.get("length") != PUBLISHED_LENGTH:
        raise RuntimeError("manifest length is not the published enwik8 length")
    return data


def verify_seal(repo: Path) -> dict:
    raw = logical_text_bytes(manifest_path(repo).read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    sealed = (tree(repo) / "SEAL.sha256").read_text(encoding="utf-8").strip()
    return {"sha256": digest, "seal": sealed, "match": digest == sealed}


def verify_checker_files(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["checker_files"]:
        path = repo / item["path"]
        digest = hashlib.sha256(logical_text_bytes(path.read_bytes())).hexdigest()
        found.append({"path": item["path"], "sha256": digest, "matches_manifest": digest == item["sha256"]})
    return found


def read_member(repo: Path, item: dict) -> tuple[bytes, bytes]:
    container = (tree(repo) / item["container"]).read_bytes()
    with zipfile.ZipFile(io.BytesIO(container)) as archive:
        data = archive.read(item["container_member"])
    return container, data


def verify_inputs(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["inputs"]:
        container, data = read_member(repo, item)
        sha256 = hashlib.sha256(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        container_sha = hashlib.sha256(container).hexdigest()
        found.append(
            {
                "name": item["name"],
                "sha256": sha256,
                "md5": md5,
                "sha1": sha1,
                "length": len(data),
                "container_sha256": container_sha,
                "matches_manifest": (
                    sha256 == item["sha256"]
                    and md5 == item["md5"]
                    and sha1 == item["sha1"]
                    and len(data) == item["length"]
                    and container_sha == item["container_sha256"]
                    and md5 == PUBLISHED_MD5
                    and sha1 == PUBLISHED_SHA1
                    and len(data) == PUBLISHED_LENGTH
                ),
            }
        )
    return found


def judge_observed_crc(observed_hex: str, python_hex: str) -> dict:
    """Score one CRC against CPython zlib. An injected 00000000 fails."""
    if observed_hex == "00000000":
        return {
            "pass": False,
            "reason": "observed crc is the injected 00000000 value",
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
        "reason": "matched python zlib; no expected crc or gzip bytes are stored",
        "oracles_agree": True,
        "published_crc32_hex": None,
    }


def gzip_oracle(gzip_bytes: bytes, work: Path) -> dict:
    return gzip_decompress(gzip_bytes, work)
