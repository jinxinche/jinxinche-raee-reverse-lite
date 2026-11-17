"""The held-out set is sealed and not blind. A known bad CRC must fail."""

from pathlib import Path

import hashlib

from raee_reverse.held_out import gzip_decompress, judge_crc, load_manifest, logical_text_bytes, verify_inputs, verify_seal
from raee_reverse.path_guard import SealViolation, install, restore

REPO = Path(__file__).resolve().parents[1]


def test_manifest_is_not_blind_and_the_seal_matches():
    manifest = load_manifest(REPO)
    assert manifest["blind"] is False
    assert "single agent" in manifest["blind_reason"]
    seal = verify_seal(REPO)
    assert seal["match"] is True
    inputs = verify_inputs(REPO)
    assert inputs
    assert all(item["matches_manifest"] for item in inputs)


def test_crlf_manifest_still_matches_the_lf_seal():
    raw = (REPO / "targets" / "zlib" / "held_out" / "MANIFEST.json").read_bytes()
    crlf = raw.replace(b"\n", b"\r\n")
    assert hashlib.sha256(logical_text_bytes(crlf)).hexdigest() == hashlib.sha256(logical_text_bytes(raw)).hexdigest()


def test_published_crc_rejects_an_injected_wrong_value():
    bad = judge_crc("itu-123456789", "00000000", "cbf43926")
    assert bad["pass"] is False
    assert bad["reason"] == "observed crc disagrees with the published check value"
    good = judge_crc("itu-123456789", "cbf43926", "cbf43926")
    assert good["pass"] is True
    disagree = judge_crc("itu-123456789", "cbf43926", "00000000")
    assert disagree["pass"] is False
    assert disagree["oracles_agree"] is False


def test_guard_refuses_the_seal_and_the_measure_script_does_not_name_it():
    original = install(REPO)
    try:
        try:
            open(REPO / "targets" / "zlib" / "sealed_observations.json", encoding="utf-8")
            raised = False
        except SealViolation:
            raised = True
        assert raised is True
        try:
            open(REPO / "targets" / "zlib" / "held_out" / "MANIFEST.json", encoding="utf-8")
            raised_held = False
        except SealViolation:
            raised_held = True
        assert raised_held is True
    finally:
        restore(original)
    text = (REPO / "tools" / "measure_zlib_crc32.py").read_text(encoding="utf-8")
    assert "install(REPO)" in text
    assert "sealed_observations" not in text
    assert "held_out" not in text
    assert "0.90" in text


def test_gzip_decompress_round_trip_of_its_own_output(tmp_path):
    import gzip
    payload = b"held-out-external"
    result = gzip_decompress(gzip.compress(payload), tmp_path)
    if result["ran"]:
        assert result["returncode"] == 0
        assert result["stdout"] == payload
    else:
        assert result["matched_input"] is None
