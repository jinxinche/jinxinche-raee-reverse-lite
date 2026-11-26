"""Backup-engine parity keeps disagreements and does not invent a Ghidra rerun."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from raee_reverse.backup_engine import analyze_backup, locate_backend
from raee_reverse.compiler_gzip import REQUESTED_CFLAGS, build_minigzip
from raee_reverse.engine_parity import compare_catalogs, parse_ghidra_export, program_entry_from_name

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs" / "evidence" / "engine_parity_zlib.json"
GHIDRA = REPO / "docs" / "evidence" / "zlib_phase2.json"
TARBALL = REPO / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
PIN = REPO / "targets" / "zlib" / "PIN.json"


def test_compare_keeps_name_and_entry_disagreements():
    ghidra = [{"name": "main", "entry": 0x10}, {"name": "crc32", "entry": 0x20}, {"name": "free", "entry": 0x30}]
    backup = [
        {"name": "sym.main", "entry": 0x10},
        {"name": "sym.extra", "entry": 0x40},
        {"name": "sym.imp.free", "entry": 0x31},
    ]
    result = compare_catalogs(ghidra, backup, ghidra_entry=0x10, backup_entry=0x10)
    assert result["only_ghidra"] == ["crc32"]
    assert result["only_backup"] == ["extra"]
    assert result["entry_disagreements"] == [{"name": "free", "ghidra": [0x30], "backup": [0x31]}]
    assert result["identical"] is False
    assert result["counts"]["only_ghidra"] == 1
    assert result["counts"]["entry_disagreements"] == 1
    assert "free" not in result["only_ghidra"]
    assert "free" not in result["only_backup"]


def test_missing_backup_engine_is_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.setattr("raee_reverse.backup_engine.shutil.which", lambda _name: None)
    result = analyze_backup(tmp_path / "missing.elf")
    assert result["installed"] is False
    assert result["execution_result"] == "not_executed"
    assert result["accepted_pass"] is False
    assert result["observations"] == []
    assert result["simulated"] is False
    assert result["angr_selected"] is False


def test_committed_parity_record_recomputes_its_disagreements():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    evidence = json.loads(GHIDRA.read_text(encoding="utf-8"))
    export = evidence["ghidra"]["export_text"]
    parsed = parse_ghidra_export(export)
    assert parsed == record["ghidra"]["functions"]
    assert record["ghidra"]["export_sha256"] == hashlib.sha256(export.encode("utf-8")).hexdigest()
    assert record["ghidra"]["executed_this_run"] is False
    assert record["accepted_pass"] is False
    assert record["backup"]["angr_selected"] is False
    assert record["same_binary"] is (record["ghidra"]["binary_sha256"] == record["backup"].get("binary_sha256"))
    if not record["parity_executed"]:
        assert record["identical"] is None
        assert record["disagreements"] is None
        assert record["backup"]["installed"] is False or "not" in " ".join(record["limitations"]).lower()
        return
    again = compare_catalogs(
        parsed,
        record["backup"]["functions"],
        ghidra_entry=record["ghidra"]["program_entry"],
        backup_entry=record["backup"]["analysis"]["program_entry"],
    )
    assert again["only_ghidra"] == record["disagreements"]["only_ghidra"]
    assert again["only_backup"] == record["disagreements"]["only_backup"]
    assert again["entry_disagreements"] == record["disagreements"]["entry_disagreements"]
    assert again["identical"] is record["identical"]
    assert again.get("address_base") == record["disagreements"].get("address_base")
    assert record["identical"] is again["identical"]
    if again["only_ghidra"] or again["only_backup"] or again["entry_disagreements"] or again["program_entry_disagreement"]:
        assert record["identical"] is False


def test_live_zlib_parity_when_the_engine_and_compiler_exist(tmp_path):
    located = locate_backend()
    if not located["installed"] or shutil.which("gcc") is None or shutil.which("make") is None or sys.platform != "linux":
        missing = analyze_backup(tmp_path / "absent.elf")
        assert missing["accepted_pass"] is False
        if not located["installed"]:
            assert missing["execution_result"] == "not_executed"
        return
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    assert hashlib.sha256(TARBALL.read_bytes()).hexdigest() == pin["tarball_sha256"]
    built = build_minigzip(tmp_path / "zlib", "gcc", TARBALL, cflags=REQUESTED_CFLAGS)
    assert built["make_exit"] == 0, built["make_stderr_tail"]
    assert built["binary"]
    analysis = analyze_backup(Path(built["binary"]), budget={"timeout": 180})
    assert analysis["accepted_pass"] is False
    assert analysis["execution_result"] == "passed", analysis.get("limitations")
    assert analysis["interface"] == "r2pipe"
    names = {item["name"] for item in analysis["functions"]}
    assert len(analysis["functions"]) >= 20, sorted(names)[:30]
    tokens = ("main", "crc32", "deflate", "inflate")
    assert any(token in name.lower() for name in names for token in tokens), sorted(names)[:30]
    evidence = json.loads(GHIDRA.read_text(encoding="utf-8"))
    ghidra_functions = parse_ghidra_export(evidence["ghidra"]["export_text"])
    compared = compare_catalogs(
        ghidra_functions,
        analysis["functions"],
        ghidra_entry=program_entry_from_name(ghidra_functions, "_start"),
        backup_entry=analysis["program_entry"],
    )
    assert compared["identical"] is (
        not compared["only_ghidra"]
        and not compared["only_backup"]
        and not compared["entry_disagreements"]
        and compared["program_entry_disagreement"] is None
    )
    assert "only_ghidra" in compared and "only_backup" in compared and "entry_disagreements" in compared
    assert isinstance(compared["identical"], bool)
