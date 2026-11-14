import json
from pathlib import Path

from raee_reverse.compare import UNCOLLECTED_SURFACES, compare_surfaces
from raee_reverse.experiments import select_experiment
from raee_reverse.mcp_server import _handle, _read, _write
from raee_reverse.report_html import render_html
from raee_reverse.shrink import shrink_bytes
from tests.helpers import add_claim, add_observation, support

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence" / "zlib_phase2.json"
PIN = ROOT / "targets" / "zlib" / "PIN.json"


def _surfaces(**overrides):
    base = {
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "exit_code": 0,
        "roundtrip_equals_input": True,
        "crc32_hex": "352441c2",
    }
    base.update(overrides)
    return base


def test_match_mismatch_and_uncollected_surfaces():
    same = compare_surfaces(_surfaces(), _surfaces())
    assert same["compatible_on_collected_surfaces"] is True
    assert same["universal"] is False
    assert same["accepted_pass"] is False
    for name in UNCOLLECTED_SURFACES:
        assert same["surfaces"][name] == "not_compared"
    mismatch = compare_surfaces(_surfaces(exit_code=1), _surfaces())
    assert mismatch["compatible_on_collected_surfaces"] is False
    assert mismatch["mismatches"] == ["exit_code"]
    missing = compare_surfaces({}, _surfaces())
    assert missing["compatible_on_collected_surfaces"] is False
    assert "stdout_sha256" in missing["not_compared"]


def test_shrink_keeps_the_predicate_and_is_not_global():
    seed = b"xxBUGyyyy"

    def fails(data: bytes) -> bool:
        return b"BUG" in data

    result = shrink_bytes(seed, fails)
    assert result["predicate_held"] is True
    assert fails(result["reduced"])
    assert len(result["reduced"]) < len(seed)
    assert result["global_minimum"] is False
    assert result["reduced"] == b"BUG"


def test_experiment_selection_ignores_confidence():
    choice = select_experiment(
        [{"name": "same"}, {"name": "different"}],
        [
            {"name": "expensive", "cost": 9, "predictions": {"same": "a", "different": "b"}},
            {"name": "cheap", "cost": 1, "predictions": {"same": "a", "different": "b"}},
            {"name": "useless", "cost": 0, "predictions": {"same": "a", "different": "a"}},
        ],
    )
    assert choice["experiment"] == "cheap"
    assert choice["used_model_confidence"] is False


def test_html_report_escapes_and_keeps_a_failed_gate(store):
    claim = add_claim(store, statement="<script>alert(1)</script>")
    page = render_html(store)
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "accepted_pass" in page
    assert "not a universal pass" in page
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    evidence = add_observation(store)
    support(store, evidence, claim)
    passed = render_html(store)
    assert "True" in passed
    assert "not a universal pass" in passed


def test_mcp_status_and_gate(store):
    claim = add_claim(store)
    init = _handle(store, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "raee-reverse-lite"
    listed = _handle(store, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {"ledger_status", "gate_claim"}
    called = _handle(
        store,
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "gate_claim", "arguments": {"claim_id": claim}}},
    )
    body = json.loads(called["result"]["content"][0]["text"])
    assert body["accepted_pass"] is False
    assert called["result"]["isError"] is False
    import io

    buffer = io.BytesIO()
    _write(buffer, {"jsonrpc": "2.0", "id": 1, "result": {}})
    buffer.seek(0)
    assert _read(buffer)["id"] == 1


def test_committed_zlib_evidence_is_explicit():
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert pin["tag"] == "v1.4"
    assert pin["tarball_sha256"] == "02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584"
    assert pin["acceptance"] == "non-blind"
    assert pin["build"]["configure_exit"] == 0
    assert pin["build"]["make_exit"] == 0
    assert pin["build"]["network_namespace"] is False
    assert evidence["ledger"]["accepted_pass"] is True
    assert evidence["ledger"]["not_universal"] is True
    assert evidence["ledger"]["non_blind"] is True
    assert evidence["ledger"]["final_self_check_all_match"] is True
    assert evidence["ledger"]["final_count"] == 8
    assert evidence["dev_abc"]["crc32_hex"] == "352441c2"
    assert evidence["dev_abc"]["roundtrip_equals_input"] is True
    assert evidence["ghidra"]["executed"] is True
    assert evidence["ghidra"]["simulated"] is False
    assert evidence["ghidra"]["accepted_pass"] is False
    assert "function\tcrc32\t" in evidence["ghidra"]["export_text"]
    assert "decompiled=true\tcrc32" in evidence["ghidra"]["export_text"]
    assert evidence["level_experiment"]["surviving_hypothesis"] == "level-9-differs"
    assert evidence["level_experiment"]["used_final_acceptance_set"] is False
    assert evidence["shrink"]["global_minimum"] is False
    assert evidence["shrink"]["predicate_held"] is True
    assert "compression_level_9" in evidence["uncollected_surfaces"]
