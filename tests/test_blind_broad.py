"""The SQLite and NIST corpora are sealed before any candidate run."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from raee_reverse.blind_acceptance import judge_observed_crc
from raee_reverse.blind_broad import (
    ATTEMPT2_AGENT,
    ATTEMPT3_AGENT,
    CANTERBURY_TAR_SHA256,
    ENWIK8_SET_AGENT,
    ENWIK8_ZIP_SHA256,
    SET_AGENT,
    SILESIA_NAMES,
    load_manifest,
    read_member,
    verify_checker_files,
    verify_frozen_dependencies,
    verify_inputs,
    verify_seal,
)
from raee_reverse.held_out import logical_text_bytes
from raee_reverse.path_guard import DENIED, SealViolation, install, restore

REPO = Path(__file__).resolve().parents[1]


def test_broad_manifest_is_blind_and_not_the_earlier_corpora():
    manifest = load_manifest(REPO)
    assert manifest["blind"] is True
    assert manifest["expected_gzip_stored"] is False
    assert manifest["inputs_invented_for_this_candidate"] is False
    assert manifest["tuned_on_this_set"] is False
    assert manifest["candidates_frozen_before_seal"] is True
    assert manifest["starting_ref"] == "d538cb64feb965d3d849759ec0ffdb4086dff1af"
    assert manifest["set_author"]["role"] == "set_author"
    assert manifest["set_author"]["agent"] == SET_AGENT
    assert manifest["set_author"]["agent"] != ENWIK8_SET_AGENT
    agents = [item["agent"] for item in manifest["candidate_authors"]]
    assert agents == [ATTEMPT2_AGENT, ATTEMPT3_AGENT]
    assert SET_AGENT not in agents
    assert manifest["excluded_canterbury_tar_sha256"] == CANTERBURY_TAR_SHA256
    assert manifest["excluded_enwik8_zip_sha256"] == ENWIK8_ZIP_SHA256
    assert "did not author" in manifest["blind_reason"]
    assert "not invented" in manifest["blind_reason"]
    seal = verify_seal(REPO)
    assert seal["match"] is True
    inputs = verify_inputs(REPO)
    assert len(inputs) == 11
    assert all(item["matches_manifest"] for item in inputs)
    kinds = {item["kind"] for item in manifest["inputs"]}
    assert kinds == {"executable", "random-like"}
    assert [item["name"] for item in manifest["inputs"] if item["kind"] == "executable"] == [
        "sqlite3",
        "sqldiff",
        "sqlite3_analyzer",
        "sqlite3_rsync",
    ]
    checkers = verify_checker_files(REPO)
    assert checkers
    assert all(item["matches_manifest"] for item in checkers)
    frozen = verify_frozen_dependencies(REPO)
    assert frozen
    assert all(item["matches_manifest"] for item in frozen)


def test_crlf_broad_manifest_still_matches_the_lf_seal():
    raw = (REPO / "targets" / "zlib" / "blind_broad" / "MANIFEST.json").read_bytes()
    crlf = raw.replace(b"\n", b"\r\n")
    assert hashlib.sha256(logical_text_bytes(crlf)).hexdigest() == hashlib.sha256(logical_text_bytes(raw)).hexdigest()


def test_executables_are_elf_and_constant_files_are_ascii_bits():
    manifest = load_manifest(REPO)
    for item in manifest["inputs"]:
        _container, data = read_member(REPO, item)
        if item["kind"] == "executable":
            assert data[:4] == b"\x7fELF"
        if item["name"] in {"data.pi", "data.e", "data.sqrt2", "data.sqrt3"}:
            assert set(data) <= {10, 32, 48, 49}
    names = {path.name for path in (REPO / "targets" / "zlib" / "blind_broad").iterdir()}
    for silesia in SILESIA_NAMES:
        assert silesia not in names


def test_injected_crc_fails_and_the_guard_refuses_both_blind_trees():
    bad = judge_observed_crc("00000000", "cbf43926")
    assert bad["pass"] is False
    assert bad["reason"] == "observed crc is the injected 00000000 value"
    mismatch = judge_observed_crc("11111111", "cbf43926")
    assert mismatch["pass"] is False
    good = judge_observed_crc("cbf43926", "cbf43926")
    assert good["pass"] is True
    assert "targets/zlib/held_out" in DENIED
    assert "targets/zlib/sealed_observations.json" in DENIED
    assert "targets/zlib/published_acceptance" in DENIED
    assert "targets/zlib/blind_acceptance" in DENIED
    assert "targets/zlib/blind_broad" in DENIED
    original = install(REPO)
    try:
        for relative in (
            "targets/zlib/blind_broad/MANIFEST.json",
            "targets/zlib/blind_acceptance/MANIFEST.json",
            "targets/zlib/blind_broad/sts-2_1_2.zip",
        ):
            raised = False
            try:
                open(REPO / relative, "rb")
            except SealViolation:
                raised = True
            assert raised is True
    finally:
        restore(original)


def test_measure_scripts_do_not_name_the_broad_tree():
    for name in (
        "tools/measure_zlib_crc32.py",
        "tools/measure_zlib_minigzip_attempt2.py",
        "tools/measure_zlib_minigzip_attempt3.py",
    ):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "blind_broad" not in text
        assert "install(REPO)" in text


def test_broad_checker_does_not_store_gzip_bytes_and_keeps_three_labels():
    text = (REPO / "tools" / "check_blind_broad.py").read_text(encoding="utf-8")
    assert '"gzip_bytes"' not in text
    assert "expected_gzip_stored" in text
    assert "00000000" in text
    assert "judge_observed_crc" in text
    runner = (REPO / "tools" / "run_blind_broad.py").read_text(encoding="utf-8")
    assert "reproduce_frozen_zlib_builds.py" in runner
    assert "reproduce_frozen_zlib_attempt3.py" in runner
    assert "check_blind_broad.py" in runner
    assert "check_blind_acceptance.py" in runner
    assert "msse4.2" in runner
    for label in ("stock", "attempt2", "attempt3"):
        assert label in runner
    attempt3 = (REPO / "tools" / "reproduce_frozen_zlib_attempt3.py").read_text(encoding="utf-8")
    assert "candidate=True" in attempt3
    assert "CFLAGS" in attempt3
    assert '["-O3", "-flto"]' in attempt3
    assert "docs/phase4/GOAL.md" not in attempt3
    old = (REPO / "tools" / "check_blind_acceptance.py").read_text(encoding="utf-8")
    assert 'label not in {"stock", "attempt2"}' in old


def test_runner_and_attempt3_script_refuse_flag_overrides(tmp_path):
    env = os.environ.copy()
    env["CFLAGS"] = "-O3"
    for script in ("tools/run_blind_broad.py", "tools/reproduce_frozen_zlib_attempt3.py"):
        completed = subprocess.run(
            [sys.executable, str(REPO / script), str(tmp_path / script)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert completed.returncode != 0
        assert "CFLAGS" in (completed.stderr + completed.stdout)
