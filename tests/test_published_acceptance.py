"""The published corpus is sealed and not blind. A known bad CRC must fail."""

import hashlib
from pathlib import Path

from raee_reverse.held_out import logical_text_bytes
from raee_reverse.path_guard import SealViolation, install, restore
from raee_reverse.published_acceptance import (
    judge_observed_crc,
    load_manifest,
    verify_inputs,
    verify_seal,
)

REPO = Path(__file__).resolve().parents[1]


def test_published_manifest_is_not_blind_and_the_seal_matches():
    manifest = load_manifest(REPO)
    assert manifest["blind"] is False
    assert manifest["expected_gzip_stored"] is False
    assert manifest["inputs_invented_for_this_candidate"] is False
    assert "same agent" in manifest["blind_reason"]
    assert "canterbury" in manifest["origin_url"]
    seal = verify_seal(REPO)
    assert seal["match"] is True
    inputs = verify_inputs(REPO)
    assert len(inputs) == 11
    assert all(item["matches_manifest"] for item in inputs)


def test_crlf_published_manifest_still_matches_the_lf_seal():
    raw = (REPO / "targets" / "zlib" / "published_acceptance" / "MANIFEST.json").read_bytes()
    crlf = raw.replace(b"\n", b"\r\n")
    assert hashlib.sha256(logical_text_bytes(crlf)).hexdigest() == hashlib.sha256(logical_text_bytes(raw)).hexdigest()


def test_injected_crc_fails_and_the_guard_refuses_the_published_tree():
    bad = judge_observed_crc("00000000", "cbf43926")
    assert bad["pass"] is False
    assert bad["reason"] == "observed crc disagrees with the published check value"
    mismatch = judge_observed_crc("11111111", "cbf43926")
    assert mismatch["pass"] is False
    good = judge_observed_crc("cbf43926", "cbf43926")
    assert good["pass"] is True
    original = install(REPO)
    try:
        raised = False
        try:
            open(REPO / "targets" / "zlib" / "published_acceptance" / "MANIFEST.json", encoding="utf-8")
        except SealViolation:
            raised = True
        assert raised is True
    finally:
        restore(original)


def test_measure_scripts_do_not_name_the_sealed_trees():
    for name in (
        "tools/measure_zlib_crc32.py",
        "tools/measure_zlib_minigzip_attempt2.py",
        "tools/measure_zlib_minigzip_attempt3.py",
    ):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "install(REPO)" in text
        assert "held_out" not in text
        assert "sealed_observations" not in text
        assert "published_acceptance" not in text
    attempt = (REPO / "tools" / "measure_zlib_minigzip_attempt2.py").read_text(encoding="utf-8")
    assert "0.90" in attempt
    assert "1.05" in attempt
    assert '"-flto"' in attempt or "-flto" in attempt
