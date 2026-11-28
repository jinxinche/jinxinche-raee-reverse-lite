"""The gcc/clang gzip record reports the bytes that were hashed."""

import json
from pathlib import Path

from raee_reverse.compiler_gzip import REQUESTED_CFLAGS, compare_outputs, first_mismatch

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs" / "evidence" / "compiler_gzip_bytes.json"


def test_first_mismatch_is_the_first_different_byte():
    assert first_mismatch(b"abc", b"abc") is None
    assert first_mismatch(b"abc", b"axc") == 1
    assert first_mismatch(b"ab", b"abc") == 2


def test_committed_compiler_gzip_record_matches_its_hashes():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["accepted_pass"] is False
    assert record["requested_cflags"] == REQUESTED_CFLAGS
    if record["identical"] is None:
        assert record["gcc_version"] is None or record["clang_version"] is None or record["builds"] == {}
        return
    assert record["builds"]["gcc"]["requested_cflags"] == record["builds"]["clang"]["requested_cflags"] == REQUESTED_CFLAGS
    left = record["outputs"]["gcc"]
    right = record["outputs"]["clang"]
    compared = compare_outputs(left, right)
    assert compared["identical"] is record["identical"]
    for row, stored in zip(compared["inputs"], record["comparison"]["inputs"], strict=True):
        assert row["equal"] is stored["equal"]
        assert row["stdout_sha256"] == stored["stdout_sha256"]
        assert len(row["stdout_sha256"]) == 64
    if record["identical"]:
        assert all(row["equal"] for row in record["comparison"]["inputs"])
    else:
        assert record["identical"] is False
        assert any(not row["equal"] for row in record["comparison"]["inputs"])


def test_optional_report_quotes_the_three_records():
    text = (REPO / "docs" / "optional" / "CHECKS.md").read_text(encoding="utf-8")
    network = json.loads((REPO / "docs" / "evidence" / "network_isolation.json").read_text(encoding="utf-8"))
    parity = json.loads((REPO / "docs" / "evidence" / "engine_parity_zlib.json").read_text(encoding="utf-8"))
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    isolated = "true" if network["network_isolated"] else "false"
    assert f"`network_isolated` is {isolated}." in text
    if network["network_isolated"]:
        assert str(network["network_probe"]["mechanism"]) in text
        assert "CONNECT_FAIL" in text
    assert f"`identical` is {record['identical']}." in text
    assert f"`identical` is {parity['identical']}." in text
    assert record["requested_cflags"] in text
    if record.get("comparison"):
        for row in record["comparison"]["inputs"]:
            assert row["stdout_sha256"] in text
            assert row["other_sha256"] in text
    if parity.get("disagreements"):
        counts = parity["disagreements"]["counts"]
        assert f"only_ghidra={counts['only_ghidra']}" in text
        assert f"only_backup={counts['only_backup']}" in text
        assert f"entry_disagreements={counts['entry_disagreements']}" in text
        base = parity["disagreements"].get("address_base")
        if base:
            assert str(base["ghidra_minus_backup"]) in text
