"""The Lua and base64 targets stay real, non-blind, and separate from zlib."""

import hashlib
import json
from pathlib import Path

from raee_reverse.cli_contract import (
    BASE64_COLLECTED,
    BASE64_UNCOLLECTED,
    LUA_COLLECTED,
    LUA_UNCOLLECTED,
    base64_final_inputs,
    cli_verdict,
    lua_final_files,
)

REPO = Path(__file__).resolve().parents[1]
LUA_SHA = "2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6"
BASE64_SHA = "74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_pins_match_the_vendored_tarballs_and_name_urls():
    lua = json.loads((REPO / "targets" / "lua" / "PIN.json").read_text(encoding="utf-8"))
    base64 = json.loads((REPO / "targets" / "base64" / "PIN.json").read_text(encoding="utf-8"))
    assert lua["source_url"] == "https://www.lua.org/ftp/lua-5.4.9.tar.gz"
    assert lua["tarball_sha256"] == LUA_SHA
    assert _sha((REPO / "targets" / "lua" / "dist" / "lua-5.4.9.tar.gz").read_bytes()) == LUA_SHA
    assert base64["source_url"] == "https://github.com/aklomp/base64/archive/refs/tags/v0.5.3.tar.gz"
    assert base64["tarball_sha256"] == BASE64_SHA
    assert _sha((REPO / "targets" / "base64" / "dist" / "base64-0.5.3.tar.gz").read_bytes()) == BASE64_SHA
    assert "MIT" in lua["license"]
    assert "BSD-2-Clause" in base64["license"]


def test_choice_record_keeps_the_closed_alternates():
    text = (REPO / "docs" / "phase0" / "MORE_TARGETS.md").read_text(encoding="utf-8")
    assert "does not change" in text
    assert "jq 1.x" in text
    assert "Lua 5.5.1" in text
    assert "checksum_cli.c" in text
    assert LUA_SHA in text
    assert BASE64_SHA in text


def test_real_observations_are_not_the_synthetic_sample_and_ghidra_is_not_a_pass():
    for name in ("lua_phase2.json", "base64_phase2.json"):
        report = json.loads((REPO / "docs" / "evidence" / name).read_text(encoding="utf-8"))
        assert report["synthetic"] is False
        assert report["acceptance"] == "non-blind"
        assert report["ghidra"]["executed"] is False
        assert report["ghidra"]["accepted_pass"] is False
        assert report["final_rerun_match"] is True
    lua = json.loads((REPO / "targets" / "lua" / "sealed_observations.json").read_text(encoding="utf-8"))
    base64 = json.loads((REPO / "targets" / "base64" / "sealed_observations.json").read_text(encoding="utf-8"))
    assert lua["cases"]["dev:return1"]["exit_code"] == 0
    assert lua["cases"]["dev:return1"]["output_file_exists"] is False
    assert lua["cases"]["dev:syntax_error"]["exit_code"] == 1
    assert lua["cases"]["dev:return1-dump"]["output_file_exists"] is True
    assert base64["cases"]["dev:abc-decode"]["roundtrip_equals_input"] is True
    assert base64["cases"]["dev:invalid-decode"]["exit_code"] == 1
    pin = json.loads((REPO / "targets" / "base64" / "PIN.json").read_text(encoding="utf-8"))
    assert "HAVE_AVX2   0" in pin["codec_config"]
    assert pin["build"]["extra_cflags"] is None


def test_generators_match_the_sealed_inputs():
    lua = json.loads((REPO / "targets" / "lua" / "sealed_observations.json").read_text(encoding="utf-8"))
    for name, data in lua_final_files().items():
        assert lua["cases"][f"final:{name}"]["input_sha256"] == _sha(data)
    base64 = json.loads((REPO / "targets" / "base64" / "sealed_observations.json").read_text(encoding="utf-8"))
    for name, data in base64_final_inputs().items():
        assert base64["cases"][f"final:{name}"]["input_sha256"] == _sha(data)


def test_uncollected_behavior_is_not_a_match_and_a_mismatch_is_not_compatible():
    expected = {
        "exit_code": 0,
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "output_file_exists": False,
        "output_file_sha256": None,
        "executes_chunk": True,
    }
    observed = dict(expected)
    verdict = cli_verdict(observed, expected, collected=LUA_COLLECTED, uncollected=LUA_UNCOLLECTED)
    assert verdict["compatible_on_collected_surfaces"] is True
    assert verdict["accepted_pass"] is False
    assert verdict["universal"] is False
    assert verdict["surfaces"]["executes_chunk"] == "not_compared"
    observed["exit_code"] = 1
    mismatch = cli_verdict(observed, expected, collected=LUA_COLLECTED, uncollected=LUA_UNCOLLECTED)
    assert mismatch["compatible_on_collected_surfaces"] is False
    assert "exit_code" in mismatch["mismatches"]
    truncated = cli_verdict({**expected, "truncated": True}, expected, collected=LUA_COLLECTED, uncollected=LUA_UNCOLLECTED)
    assert truncated["compatible_on_collected_surfaces"] is False


def test_base64_roundtrip_stays_not_compared_until_it_is_collected():
    expected = {
        "exit_code": 0,
        "stdout_sha256": "a" * 64,
        "stderr_sha256": "b" * 64,
        "stdout_has_newline": True,
    }
    observed = dict(expected)
    verdict = cli_verdict(observed, expected, collected=BASE64_COLLECTED, uncollected=BASE64_UNCOLLECTED)
    assert verdict["compatible_on_collected_surfaces"] is True
    assert verdict["surfaces"]["roundtrip_equals_input"] == "not_compared"
    assert verdict["surfaces"]["ignore_garbage"] == "not_compared"
    assert verdict["accepted_pass"] is False


def test_baseline_recipes_do_not_read_the_sealed_files():
    for path in (
        REPO / "generated" / "lua-baseline" / "build_and_check.py",
        REPO / "generated" / "base64-baseline" / "build_and_check.py",
    ):
        text = path.read_text(encoding="utf-8")
        assert "sealed_observations" not in text
        assert "run_sandboxed" in text
    lua_accept = (REPO / "generated" / "lua-baseline" / "accept.py").read_text(encoding="utf-8")
    base64_accept = (REPO / "generated" / "base64-baseline" / "accept.py").read_text(encoding="utf-8")
    assert "sealed_observations.json" in lua_accept
    assert "sealed_observations.json" in base64_accept
    assert "targets/zlib" not in lua_accept
    assert "targets/zlib" not in base64_accept
