"""The committed enwik8 runs must agree with their own rows. A pass flag cannot hide a failed row."""

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEAL = "f3a79dce276c4919936ef06be8eba56ad91f7c5c"


def _load(name: str) -> dict:
    return json.loads((REPO / "docs" / "evidence" / name).read_text(encoding="utf-8"))


def _row_and_control_ok(report: dict) -> bool:
    rows = report["rows"]
    negative = report["negative_control"]
    rows_ok = bool(rows) and all(
        row["judge"]["pass"] is True
        and row["crc_exit"] == 0
        and row["minigzip_exit"] == 0
        and row["gzip_external_match"] is True
        and row["python_zlib_decompress_match"] is True
        and row["observed_crc32"] == row["python_crc32"]
        and row["observed_crc32"] != "00000000"
        and "gzip_bytes" not in row
        for row in rows
    )
    control = negative["corrupted_gzip"]
    control_ok = (
        negative["injected_crc"] == "00000000"
        and negative["judge_pass"] is False
        and negative["failed_as_required"] is True
        and control["rejected"] is True
        and control["gzip_external_accepted_original"] is False
        and control["python_zlib_accepted_original"] is False
    )
    return (
        report["executed"] is True
        and report["seal_match"] is True
        and report["checker_match"] is True
        and report["inputs_match_manifest"] is True
        and report["sample_size"] == len(rows) == 1
        and report["unfinished"] == []
        and rows_ok
        and control_ok
    )


def test_recorded_enwik8_runs_match_their_rows_and_the_seal_commit():
    stock = _load("blind_acceptance_stock.json")
    attempt = _load("blind_acceptance_attempt2.json")
    pin = json.loads((REPO / "targets" / "zlib" / "PIN.json").read_text(encoding="utf-8"))
    for report in (stock, attempt):
        assert report["pass"] is _row_and_control_ok(report)
        assert report["blind"] is True
        assert report["inputs_invented_for_this_candidate"] is False
        assert report["tuned_on_this_set"] is False
        assert report["expected_gzip_stored"] is False
        assert report["source_commit"] == SEAL
        assert report["starting_ref"] == "8a06e96fffff1cfe6958010babaea5a9308d4961"
        assert report["set_author"]["agent"] != report["candidate_authors"]["agent"]
        assert report["reproduction"]["cflags_override"] is None
        assert report["reproduction"]["ldflags_override"] is None
        assert report["reproduction"]["recipe"] == ["./configure", "make"]
        assert report["rows"][0]["name"] == "enwik8"
        assert report["rows"][0]["length"] == 100_000_000
    assert stock["reproduction"]["candidate_patch"] is False
    assert attempt["reproduction"]["candidate_patch"] is True
    assert stock["minigzip_sha256"] == pin["minigzip_sha256"]
    assert stock["reproduction"]["libz_sha256"] == pin["libz_a_sha256"]
    assert stock["minigzip_sha256"] != attempt["minigzip_sha256"]
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SEAL, "HEAD"],
        cwd=REPO,
        check=False,
    )
    assert ancestor.returncode == 0
