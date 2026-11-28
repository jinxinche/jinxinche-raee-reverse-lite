"""The committed broad-corpus runs must agree with their own rows."""

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEAL = "3b6e405f70129bf075cc7f654dfbfea74d8ceae5"
RECORDS = (
    "blind_broad_stock.json",
    "blind_broad_attempt2.json",
    "blind_broad_attempt3.json",
)


def _load(name: str) -> dict:
    return json.loads((REPO / "docs" / "evidence" / name).read_text(encoding="utf-8"))


def _controls_ok(report: dict) -> bool:
    rows = report["rows"]
    controls = report["negative_controls"]
    if controls != [row["negative_control"] for row in rows]:
        return False
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
    controls_ok = all(
        control["injected_crc"] == "00000000"
        and control["judge_pass"] is False
        and control["failed_as_required"] is True
        and control["corrupted_gzip"]["rejected"] is True
        and control["corrupted_gzip"]["gzip_external_accepted_original"] is False
        and control["corrupted_gzip"]["python_zlib_accepted_original"] is False
        for control in controls
    )
    return rows_ok and controls_ok


def test_recorded_broad_runs_match_their_rows_and_the_seal_commit():
    reports = [_load(name) for name in RECORDS]
    pin = json.loads((REPO / "targets" / "zlib" / "PIN.json").read_text(encoding="utf-8"))
    enwik8_attempt = _load("blind_acceptance_attempt2.json")
    names = [row["name"] for row in reports[0]["rows"]]
    assert len(names) == 11
    assert len(set(names)) == 11
    for report in reports:
        assert report["pass"] is True
        assert report["pass"] is (
            report["executed"] is True
            and report["seal_match"] is True
            and report["checker_match"] is True
            and report["frozen_dependency_match"] is True
            and report["inputs_match_manifest"] is True
            and report["sample_size"] == len(report["rows"]) == 11
            and report["unfinished"] == []
            and _controls_ok(report)
        )
        assert report["blind"] is True
        assert report["inputs_invented_for_this_candidate"] is False
        assert report["tuned_on_this_set"] is False
        assert report["expected_gzip_stored"] is False
        assert report["source_commit"] == SEAL
        assert report["starting_ref"] == "d538cb64feb965d3d849759ec0ffdb4086dff1af"
        assert report["set_author"]["agent"] == "bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d"
        assert report["set_author"]["agent"] not in {item["agent"] for item in report["candidate_authors"]}
        assert report["reproduction"]["cflags_override"] is None
        assert report["reproduction"]["ldflags_override"] is None
        assert report["reproduction"]["recipe"] == ["./configure", "make"]
        assert [row["name"] for row in report["rows"]] == names
        assert '"gzip_bytes"' not in json.dumps(report)
    assert reports[0]["reproduction"]["candidate_patch"] is False
    assert reports[1]["reproduction"]["candidate_patch"] is True
    assert reports[2]["reproduction"]["candidate_patch"] is True
    assert reports[2]["reproduction"]["candidate"] == "attempt3"
    assert reports[0]["minigzip_sha256"] == pin["minigzip_sha256"]
    assert reports[0]["reproduction"]["libz_sha256"] == pin["libz_a_sha256"]
    assert reports[1]["minigzip_sha256"] == enwik8_attempt["minigzip_sha256"]
    assert len({report["minigzip_sha256"] for report in reports}) == 3
    for left, right in zip(reports[0]["rows"], reports[1]["rows"]):
        assert left["observed_crc32"] == right["observed_crc32"]
        assert left["minigzip_stdout_bytes"] == right["minigzip_stdout_bytes"]
    for left, right in zip(reports[0]["rows"], reports[2]["rows"]):
        assert left["observed_crc32"] == right["observed_crc32"]
        assert left["minigzip_stdout_bytes"] == right["minigzip_stdout_bytes"]
    assert reports[0]["uname"] == reports[1]["uname"] == reports[2]["uname"]
    _require_seal_ancestor()
    _require_records_added_after_seal()


def test_workflow_runs_ubuntu_and_macos_as_separate_hosts():
    text = (REPO / ".github" / "workflows" / "blind-broad.yml").read_text(encoding="utf-8")
    assert "ubuntu-latest" in text
    assert "macos-latest" in text
    assert "windows-latest" not in text
    assert "tools/run_blind_broad.py" in text
    assert text.count("os:") >= 1


def _commit_present(sha: str) -> bool:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


def _deepen_checked_out_commit(head_sha: str) -> subprocess.CompletedProcess[str]:
    attempts = (
        ["git", "fetch", "--deepen=20", "origin", head_sha],
        ["git", "fetch", "--deepen=20", "origin"],
    )
    last: subprocess.CompletedProcess[str] | None = None
    for command in attempts:
        last = subprocess.run(command, cwd=REPO, capture_output=True, text=True, check=False)
        if last.returncode == 0:
            return last
    assert last is not None
    return last


def _ancestor_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", SEAL, "HEAD"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_seal_ancestor() -> None:
    ancestor = _ancestor_check()
    if ancestor.returncode == 0:
        return
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if shallow.returncode != 0 or shallow.stdout.strip() != "true":
        if not _commit_present(SEAL):
            raise AssertionError(f"seal commit {SEAL} is absent and this clone is not shallow")
        raise AssertionError((ancestor.stderr or ancestor.stdout or "seal commit is not an ancestor of HEAD").strip())
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False)
    head_sha = head.stdout.strip()
    if head.returncode != 0 or len(head_sha) != 40:
        raise AssertionError("cannot resolve HEAD in order to deepen the clone")
    for _ in range(4):
        deepened = _deepen_checked_out_commit(head_sha)
        if deepened.returncode != 0:
            detail = (deepened.stderr or deepened.stdout or "git fetch failed").strip()
            raise AssertionError(f"shallow clone could not fetch the seal commit: {detail}")
        ancestor = _ancestor_check()
        if ancestor.returncode == 0:
            return
    if not _commit_present(SEAL):
        raise AssertionError(f"seal commit {SEAL} is still absent after deepening")
    raise AssertionError((ancestor.stderr or ancestor.stdout or "seal commit is not an ancestor of HEAD").strip())


def _require_records_added_after_seal() -> None:
    _require_seal_ancestor()
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", SEAL],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        raise AssertionError((listed.stderr or "cannot list the seal tree").strip())
    names = set(listed.stdout.splitlines())
    for name in RECORDS:
        assert f"docs/evidence/{name}" not in names
    added = subprocess.run(
        ["git", "log", "--diff-filter=A", "--format=%H", "--", f"docs/evidence/{RECORDS[0]}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0 or not added.stdout.strip():
        raise AssertionError("the broad run record has no adding commit")
    sha = added.stdout.splitlines()[0].strip()
    parent = subprocess.run(
        ["git", "rev-parse", f"{sha}^"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert parent.stdout.strip() == SEAL
