"""The committed Phase 2 file is a record of one Linux run, not a CI rerun of Ghidra."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "phase2_dev_sample.json"
SOURCE = Path(__file__).resolve().parents[1] / "samples" / "dev" / "checksum_cli.c"


def test_committed_dev_sample_chain_is_explicit():
    report = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert report["synthetic"] is True
    assert report["analysis_chain_executed"] is True
    assert "zlib" in report["real_target"]
    assert report["runs"]["abc"]["stdout"] == "count=3 sum=294\n"
    assert report["runs"]["abc"]["returncode"] == 0
    assert report["runs"]["fail"]["execution_result"] == "failed"
    assert report["runs"]["fail"]["returncode"] == 3
    assert report["runs"]["abc"]["network_namespace"] is False
    ghidra = report["ghidra"]
    assert ghidra["executed"] is True
    assert ghidra["simulated"] is False
    assert ghidra["accepted_pass"] is False
    assert ghidra["decompiled_main"] is True
    assert "function\tchecksum\t" in ghidra["export_text"]
    assert "0xfff1" in ghidra["export_text"]
    assert ghidra["tool_version_hint"] == "ghidra_12.2_PUBLIC"
    assert report["ledger"]["accepted_pass"] is True
    assert report["ledger"]["not_universal"] is True
    assert report["ledger"]["independent_support_count"] == 1
    assert report["host"]["system"] == "Linux"
    assert report["host"]["python"] == "3.12.3"


def test_fresh_linux_build_matches_the_recorded_stdout(tmp_path):
    if sys.platform != "linux" or platform.machine() != "x86_64" or shutil.which("gcc") is None:
        assert sys.platform != "linux" or platform.machine() != "x86_64" or shutil.which("gcc") is None
        return
    binary = tmp_path / "checksum_cli"
    compiled = subprocess.run(
        ["gcc", "-O0", "-g", "-o", str(binary), str(SOURCE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stderr
    ran = subprocess.run([str(binary)], input=b"abc", capture_output=True, check=False)
    assert ran.returncode == 0
    assert ran.stdout == b"count=3 sum=294\n"
    failed = subprocess.run([str(binary), "--fail"], input=b"abc", capture_output=True, check=False)
    assert failed.returncode == 3
    assert failed.stdout == b"count=3 sum=294\n"
