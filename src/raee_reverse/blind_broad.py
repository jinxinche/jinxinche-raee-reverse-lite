"""Blind acceptance for a second sealed corpus set.

The inputs are published files chosen after the stock, attempt-2, and
attempt-3 candidates were frozen. Expected gzip bytes are not stored.
GNU gzip and CPython zlib are the oracles. This set author is not the
enwik8 set author and is not either candidate author.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from raee_reverse.held_out import gzip_decompress, logical_text_bytes

STARTING_REF = "d538cb64feb965d3d849759ec0ffdb4086dff1af"
SET_AGENT = "bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d"
ENWIK8_SET_AGENT = "bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4"
ATTEMPT2_AGENT = "bc-641141af-3ffd-5b16-acb9-663777242042"
ATTEMPT3_AGENT = "bc-cfef56ea-f25b-5590-a266-7684b5589b8e"
CANTERBURY_TAR_SHA256 = "f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb"
ENWIK8_ZIP_SHA256 = "547994d9980ebed1288380d652999f38a14fe291a6247c157c3d33d4932534bc"
SILESIA_NAMES = ("mozilla", "x-ray", "sao")
TREE = Path("targets") / "zlib" / "blind_broad"
ASCII_BIT_NAMES = ("data.e", "data.pi", "data.sqrt2", "data.sqrt3")
BINARY_RANDOM_NAMES = ("BBS.dat", "data.bad_rng", "data.sha1")
CHECKER_PATHS = (
    "src/raee_reverse/blind_broad.py",
    "src/raee_reverse/path_guard.py",
    "tools/check_blind_broad.py",
    "tools/reproduce_frozen_zlib_attempt3.py",
    "tools/run_blind_broad.py",
)
FROZEN_DEPENDENCIES = (
    {
        "path": "src/raee_reverse/blind_acceptance.py",
        "sha256": "7545a3cdc3c97f2989a7a75e5e075259e5a4deae9f6a4aa9b1fc83d95f798df3",
    },
    {
        "path": "tools/check_blind_acceptance.py",
        "sha256": "ac0e813ae671c34f34cf642dd2c31e9d16b233c84a865e429724cb0a66573da5",
    },
    {
        "path": "tools/reproduce_frozen_zlib_builds.py",
        "sha256": "25723f237bf9334d4643e8f75ce73d057beb8eced724e273e632430fe831374e",
    },
    {
        "path": "targets/zlib/blind_acceptance/crc32_stdin.c",
        "sha256": "20ecf8b1fcd9ab9aee3928239597095a718c28087f71771b833a7298ce6efda4",
    },
)
SET_AUTHOR = {
    "role": "set_author",
    "agent": SET_AGENT,
    "run_url": "https://cursor.com/agents/bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d",
}
CANDIDATE_AUTHORS = [
    {
        "role": "candidate_author",
        "agent": ATTEMPT2_AGENT,
        "candidates": ["stock zlib 1.4 minigzip", "attempt 2"],
        "commits": [
            "52d4a9e8b4918f75653b2912602a23d1cf510088",
            "a912990a978ee37a595b82ae11ae6b0e4cb6ab81",
            "dce39956bc96275342517d9aa307be2ffc743435",
        ],
        "frozen_at": "8a06e96fffff1cfe6958010babaea5a9308d4961",
        "run_url": "https://cursor.com/agents/bc-641141af-3ffd-5b16-acb9-663777242042",
    },
    {
        "role": "candidate_author",
        "agent": ATTEMPT3_AGENT,
        "candidates": ["attempt 3"],
        "commits": [
            "1130d45dfdd04c46784b14e6974294c437c91eba",
            "c1680fcad53b9a76bdcc40f640f1962392244dd9",
        ],
        "frozen_at": "d538cb64feb965d3d849759ec0ffdb4086dff1af",
        "run_url": "https://cursor.com/agents/bc-cfef56ea-f25b-5590-a266-7684b5589b8e",
    },
]
SQLITE_ZIP = "sqlite-tools-linux-x64-3540100.zip"
SQLITE_SHA256 = "a21062b333c7d66d7d8c42054c0fab1c1899729185289ad14bd4f25f9f576d14"
SQLITE_SHA3_256 = "555635de98534d87a67ee2e6e1b0d79f494b1b33b223477d3e7a8ea0c66e416f"
SQLITE_BYTES = 4_324_601
NIST_ZIP = "sts-2_1_2.zip"
NIST_SHA256 = "0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157"
NIST_BYTES = 43_915_127
NIST_MEMBER_PREFIX = "sts-2.1.2/sts-2.1.2/data/"
LABELS = ("stock", "attempt2", "attempt3")
BLIND_REASON = (
    "The set author is bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d. "
    "This agent did not author the stock zlib 1.4 minigzip, the attempt-2 candidate, "
    "or the attempt-3 candidate. Those candidates were already frozen at starting_ref "
    "d538cb64feb965d3d849759ec0ffdb4086dff1af before this manifest was written. "
    "The attempt-2 candidate author is bc-641141af-3ffd-5b16-acb9-663777242042. "
    "The attempt-3 candidate author is bc-cfef56ea-f25b-5590-a266-7684b5589b8e. "
    "The enwik8 set author is bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4. "
    "The inputs are the published SQLite 3.54.1 Linux x64 command-line tools and the "
    "data files shipped in NIST STS 2.1.2. They were not invented for these candidates. "
    "Expected gzip bytes are not stored. The set was not used to tune the candidates."
)

INPUTS = (
    {
        "name": "sqlite3",
        "corpus": "sqlite-tools-linux-x64-3.54.1",
        "kind": "executable",
        "container": SQLITE_ZIP,
        "container_member": "sqlite3",
        "container_sha256": SQLITE_SHA256,
        "sha256": "c9daa875c28379f0d61a833d47928c6e43b352d98638cd824ec405f23c99d870",
        "md5": "d6cb8930060909a8b74edeba8671d3ca",
        "sha1": "a65ebcee469736358b8f2f2d7a9287901fcac0fe",
        "length": 2_037_360,
    },
    {
        "name": "sqldiff",
        "corpus": "sqlite-tools-linux-x64-3.54.1",
        "kind": "executable",
        "container": SQLITE_ZIP,
        "container_member": "sqldiff",
        "container_sha256": SQLITE_SHA256,
        "sha256": "62b3014603bbf427eeaba2767f32ffc4c88ea261d5960dfff6683c26bf50d56b",
        "md5": "7d61893b9407b8704d6acc5cf2cfd732",
        "sha1": "9df36c07cf21b5a19102860594579a8d111ba853",
        "length": 1_596_160,
    },
    {
        "name": "sqlite3_analyzer",
        "corpus": "sqlite-tools-linux-x64-3.54.1",
        "kind": "executable",
        "container": SQLITE_ZIP,
        "container_member": "sqlite3_analyzer",
        "container_sha256": SQLITE_SHA256,
        "sha256": "e2ffb7e4471e17dfa2f0b1829350b30a36a46cdafb9ecb870891781df6b1fbd3",
        "md5": "32b470f4ed9ea8336bcab28c5536abfd",
        "sha1": "4f72fd1490713e3c962fcf1f845dd6efa8711cd1",
        "length": 3_334_360,
    },
    {
        "name": "sqlite3_rsync",
        "corpus": "sqlite-tools-linux-x64-3.54.1",
        "kind": "executable",
        "container": SQLITE_ZIP,
        "container_member": "sqlite3_rsync",
        "container_sha256": SQLITE_SHA256,
        "sha256": "5203304e7ce33b872eea14ad3888d557d86f6860cf3643a6d03fa987e8d980fa",
        "md5": "4d644bae2924702d0f38f3645a6b8483",
        "sha1": "9a17d734181acda55e335b79ce2a2d35217d5ed1",
        "length": 1_559_168,
    },
    {
        "name": "BBS.dat",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "BBS.dat",
        "container_sha256": NIST_SHA256,
        "sha256": "8b808e72e5b9e50893f5714a948d3a87c3a014fc8b8e0be3f64e3da07ad8ed6c",
        "md5": "28db13aecb917e6b367ebaf25de3cbaf",
        "sha1": "b314cdf9f051af25d687470ec0e0211b2a5da3a7",
        "length": 37_500_000,
    },
    {
        "name": "data.bad_rng",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.bad_rng",
        "container_sha256": NIST_SHA256,
        "sha256": "4a596370fcb4263c99f4fddcbd5c766c4abf5cfaab645bef1d3611d86f1c3e60",
        "md5": "8fe4cf7434ca8704c5ee240af15dd0ba",
        "sha1": "4c9fc61f0b89534a133a5a3c8f7d41916a98af8d",
        "length": 1_572_864,
    },
    {
        "name": "data.e",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.e",
        "container_sha256": NIST_SHA256,
        "sha256": "b4b49e2987dacdbd5fe75a8ad767f4139e7be7d8f0ff9ddfb23e6081a5feed2d",
        "md5": "4302cf4dde510c45a9caeab8f5cb43bb",
        "sha1": "2f6e9e1b309698e381e5d70be921983e29231889",
        "length": 1_165_666,
    },
    {
        "name": "data.pi",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.pi",
        "container_sha256": NIST_SHA256,
        "sha256": "8efe68d864d53540de7a7a3c54743cb0f47ffcd28b2950992519068474498823",
        "md5": "979c03cca4849a36e174703673da9a56",
        "sha1": "9bc7e4fb6b5f2bb9276bddf6f00a4a4a8a856ce0",
        "length": 1_165_666,
    },
    {
        "name": "data.sha1",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.sha1",
        "container_sha256": NIST_SHA256,
        "sha256": "dcc306053a40b5f0c94508425660620b932a1803aadc7207a1b669eb4e3bd6a3",
        "md5": "f53e0568b6ab7658468be1ef504875fb",
        "sha1": "83afe955854a80e1a1a904d3210e668af104c963",
        "length": 125_000,
    },
    {
        "name": "data.sqrt2",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.sqrt2",
        "container_sha256": NIST_SHA256,
        "sha256": "66e6fd40d1e7b14613801cdb8af67ee6b4fde988f348e0a09e7be84257ee3ed3",
        "md5": "61cffd1b32b0aeff012785c520f52d5f",
        "sha1": "bf01ca6bb82b4ef1ac9a0ccaf254c85ce402574b",
        "length": 1_165_667,
    },
    {
        "name": "data.sqrt3",
        "corpus": "nist-sts-2.1.2-data",
        "kind": "random-like",
        "container": NIST_ZIP,
        "container_member": NIST_MEMBER_PREFIX + "data.sqrt3",
        "container_sha256": NIST_SHA256,
        "sha256": "6b1fc9f59f701b4c75d013cb3854bcc545f971da057d8140a8d7600bd34850e0",
        "md5": "bd3262d164bb0b2eb279e497ae0412ef",
        "sha1": "71b40e2490510240b5aa68b1cb70112838d6038a",
        "length": 1_165_667,
    },
)


def tree(repo: Path) -> Path:
    return repo / TREE


def manifest_path(repo: Path) -> Path:
    return tree(repo) / "MANIFEST.json"


def published_inputs() -> list[dict]:
    return [dict(item) for item in INPUTS]


def load_manifest(repo: Path) -> dict:
    data = json.loads(manifest_path(repo).read_text(encoding="utf-8"))
    if data.get("expected_gzip_stored") is not False:
        raise RuntimeError("refusing a manifest that stores expected gzip bytes")
    if data.get("inputs_invented_for_this_candidate") is not False:
        raise RuntimeError("refusing inputs invented for this candidate")
    if data.get("tuned_on_this_set") is not False:
        raise RuntimeError("refusing a manifest that was tuned on this set")
    if data.get("blind") is not True or data.get("blind_claim") is not True:
        raise RuntimeError("this sealed set is a blind check")
    if data.get("candidates_frozen_before_seal") is not True:
        raise RuntimeError("candidates were not recorded as frozen before the seal")
    if data.get("starting_ref") != STARTING_REF:
        raise RuntimeError("starting_ref is not the frozen tip")
    if data.get("set_author") != SET_AUTHOR:
        raise RuntimeError("set author does not match this checker")
    if data.get("candidate_authors") != CANDIDATE_AUTHORS:
        raise RuntimeError("candidate authors do not match the frozen candidates")
    authors = {item["agent"] for item in CANDIDATE_AUTHORS}
    if SET_AGENT in authors or SET_AGENT == ENWIK8_SET_AGENT:
        raise RuntimeError("set author is a candidate author or the enwik8 set author")
    if len(authors) != 2:
        raise RuntimeError("the two candidate authors must be distinct")
    if data.get("blind_reason") != BLIND_REASON:
        raise RuntimeError("blind_reason does not match this set author")
    if data.get("excluded_canterbury_tar_sha256") != CANTERBURY_TAR_SHA256:
        raise RuntimeError("the Canterbury tarball hash is not recorded as excluded")
    if data.get("excluded_enwik8_zip_sha256") != ENWIK8_ZIP_SHA256:
        raise RuntimeError("the enwik8 zip hash is not recorded as excluded")
    containers = {item.get("container_sha256") for item in data.get("inputs") or []}
    if CANTERBURY_TAR_SHA256 in containers or ENWIK8_ZIP_SHA256 in containers:
        raise RuntimeError("refusing the Canterbury tarball or the enwik8 zip as an input")
    if data.get("inputs") != published_inputs():
        raise RuntimeError("manifest inputs are not the sealed SQLite and NIST files")
    names = [item["name"] for item in data["inputs"]]
    if any(name in names for name in SILESIA_NAMES):
        raise RuntimeError("refusing a Silesia file whose license was not clear")
    kinds = {item["kind"] for item in data["inputs"]}
    if kinds != {"executable", "random-like"}:
        raise RuntimeError("the sealed inputs must include executable and random-like files")
    paths = [item.get("path") for item in data.get("checker_files") or []]
    if paths != list(CHECKER_PATHS):
        raise RuntimeError("checker file list does not match this set")
    frozen = data.get("frozen_dependencies")
    if frozen != [dict(item) for item in FROZEN_DEPENDENCIES]:
        raise RuntimeError("frozen dependency hashes do not match the enwik8 seal")
    if data.get("sqlite_sha3_256") != SQLITE_SHA3_256:
        raise RuntimeError("sqlite container is not the published SHA3-256")
    if data.get("nist_sha256") != NIST_SHA256 or data.get("sqlite_sha256") != SQLITE_SHA256:
        raise RuntimeError("container hash does not match the downloaded zip")
    return data


def verify_seal(repo: Path) -> dict:
    raw = logical_text_bytes(manifest_path(repo).read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    sealed = (tree(repo) / "SEAL.sha256").read_text(encoding="utf-8").strip()
    return {"sha256": digest, "seal": sealed, "match": digest == sealed}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(logical_text_bytes(path.read_bytes())).hexdigest()


def verify_checker_files(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["checker_files"]:
        digest = _file_sha256(repo / item["path"])
        found.append({"path": item["path"], "sha256": digest, "matches_manifest": digest == item["sha256"]})
    return found


def verify_frozen_dependencies(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["frozen_dependencies"]:
        digest = _file_sha256(repo / item["path"])
        found.append({"path": item["path"], "sha256": digest, "matches_manifest": digest == item["sha256"]})
    return found


def read_member(repo: Path, item: dict) -> tuple[bytes, bytes]:
    container = (tree(repo) / item["container"]).read_bytes()
    with zipfile.ZipFile(io.BytesIO(container)) as archive:
        data = archive.read(item["container_member"])
    return container, data


def _kind_bytes_ok(item: dict, data: bytes) -> bool:
    if item["kind"] == "executable":
        return data[:4] == b"\x7fELF"
    if item["name"] in ASCII_BIT_NAMES:
        return all(byte in (10, 32, 48, 49) for byte in data)
    if item["name"] in BINARY_RANDOM_NAMES:
        return b"\0" in data[:4096] and data[:4] != b"\x7fELF"
    return False


def verify_inputs(repo: Path) -> list[dict]:
    manifest = load_manifest(repo)
    found = []
    for item in manifest["inputs"]:
        container, data = read_member(repo, item)
        sha256 = hashlib.sha256(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()
        sha1 = hashlib.sha1(data).hexdigest()
        container_sha = hashlib.sha256(container).hexdigest()
        container_sha3 = hashlib.sha3_256(container).hexdigest()
        sha3_ok = True
        if item["container"] == SQLITE_ZIP:
            sha3_ok = container_sha3 == SQLITE_SHA3_256 and len(container) == SQLITE_BYTES
        if item["container"] == NIST_ZIP:
            sha3_ok = len(container) == NIST_BYTES
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
                    and sha3_ok
                    and _kind_bytes_ok(item, data)
                ),
            }
        )
    return found


def gzip_oracle(gzip_bytes: bytes, work: Path) -> dict:
    return gzip_decompress(gzip_bytes, work)
