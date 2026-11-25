"""The enwik8 corpus is sealed before any candidate run. A known bad CRC must fail."""

import hashlib
from pathlib import Path

from raee_reverse.blind_acceptance import (
    CANTERBURY_TAR_SHA256,
    PUBLISHED_LENGTH,
    PUBLISHED_MD5,
    PUBLISHED_SHA1,
    judge_observed_crc,
    load_manifest,
    verify_checker_files,
    verify_inputs,
    verify_seal,
)
from raee_reverse.held_out import logical_text_bytes
from raee_reverse.path_guard import SealViolation, install, restore

REPO = Path(__file__).resolve().parents[1]


def test_enwik8_manifest_is_blind_sealed_and_not_canterbury():
    manifest = load_manifest(REPO)
    assert manifest["blind"] is True
    assert manifest["expected_gzip_stored"] is False
    assert manifest["inputs_invented_for_this_candidate"] is False
    assert manifest["tuned_on_this_set"] is False
    assert manifest["candidates_frozen_before_seal"] is True
    assert manifest["starting_ref"] == "8a06e96fffff1cfe6958010babaea5a9308d4961"
    assert manifest["set_author"]["agent"] != manifest["candidate_authors"]["agent"]
    assert manifest["origin_zip_sha256"] != CANTERBURY_TAR_SHA256
    assert "mattmahoney.net" in manifest["origin_url"]
    assert "did not author" in manifest["blind_reason"]
    seal = verify_seal(REPO)
    assert seal["match"] is True
    inputs = verify_inputs(REPO)
    assert len(inputs) == 1
    assert inputs[0]["matches_manifest"] is True
    assert inputs[0]["md5"] == PUBLISHED_MD5
    assert inputs[0]["sha1"] == PUBLISHED_SHA1
    assert inputs[0]["length"] == PUBLISHED_LENGTH
    checkers = verify_checker_files(REPO)
    assert checkers
    assert all(item["matches_manifest"] for item in checkers)


def test_crlf_blind_manifest_still_matches_the_lf_seal():
    raw = (REPO / "targets" / "zlib" / "blind_acceptance" / "MANIFEST.json").read_bytes()
    crlf = raw.replace(b"\n", b"\r\n")
    assert hashlib.sha256(logical_text_bytes(crlf)).hexdigest() == hashlib.sha256(logical_text_bytes(raw)).hexdigest()


def test_injected_crc_fails_and_the_guard_refuses_the_blind_tree():
    bad = judge_observed_crc("00000000", "cbf43926")
    assert bad["pass"] is False
    assert bad["reason"] == "observed crc is the injected 00000000 value"
    mismatch = judge_observed_crc("11111111", "cbf43926")
    assert mismatch["pass"] is False
    good = judge_observed_crc("cbf43926", "cbf43926")
    assert good["pass"] is True
    original = install(REPO)
    try:
        raised = False
        try:
            open(REPO / "targets" / "zlib" / "blind_acceptance" / "MANIFEST.json", encoding="utf-8")
        except SealViolation:
            raised = True
        assert raised is True
    finally:
        restore(original)
    for name in ("tools/measure_zlib_crc32.py", "tools/measure_zlib_minigzip_attempt2.py"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "blind_acceptance" not in text


def test_reproduce_script_uses_the_frozen_recipe_and_refuses_flag_overrides():
    text = (REPO / "tools" / "reproduce_frozen_zlib_builds.py").read_text(encoding="utf-8")
    assert "candidate=False" in text
    assert "candidate=True" in text
    assert '["-O3", "-flto"]' in text
    assert "CFLAGS" in text
    assert "zlib_minigzip_attempt2.json" not in text
    assert "docs/phase4/GOAL.md" not in text
