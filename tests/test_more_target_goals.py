"""The new goals stay frozen, and the recorded ratios keep their own verdicts."""

import hashlib
import json
import statistics
from pathlib import Path

from raee_reverse.path_guard_targets import SealViolation, install, restore

REPO = Path(__file__).resolve().parents[1]

GOAL_LUA_MD = "e65dd23b78079951234d9805fc1cc9fdbd04438c7b9f3189b7d13f139bd21298"
GOAL_LUA_JSON = "d96acfbcf9bad2dfa0678c33c28a82934658b29c377d14e5103be1d566e7b6ea"
GOAL_BASE64_MD = "7710848bb37bd91d0e49c462e945de78e530f3da2a7041b35a71018570d5087b"
GOAL_BASE64_JSON = "841d6db591e47787a2530a1c711a436200020929d9bbd31541df38aa9c64db48"


def _logical(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def _load(name: str) -> dict:
    return json.loads((REPO / "docs" / "evidence" / name).read_text(encoding="utf-8"))


def test_new_goals_do_not_replace_the_closed_zlib_goal():
    pairs = {
        "docs/phase4/GOAL_LUA.md": GOAL_LUA_MD,
        "docs/phase4/GOAL_LUA.json": GOAL_LUA_JSON,
        "docs/phase4/GOAL_BASE64.md": GOAL_BASE64_MD,
        "docs/phase4/GOAL_BASE64.json": GOAL_BASE64_JSON,
    }
    for name, digest in pairs.items():
        assert hashlib.sha256(_logical((REPO / name).read_bytes())).hexdigest() == digest
    lua = (REPO / "docs" / "phase4" / "GOAL_LUA.json").read_text(encoding="utf-8")
    base64 = (REPO / "docs" / "phase4" / "GOAL_BASE64.json").read_text(encoding="utf-8")
    assert '"supersedes_closed_goal": false' in lua
    assert '"supersedes_closed_goal": false' in base64
    assert '"ratio_max": 0.9' in lua
    assert '"ratio_max": 0.9' in base64
    assert '"source_edit": false' in lua
    assert '"source_edit": false' in base64
    assert '"avx512": false' in base64
    assert "MYCFLAGS=-O3" in lua
    assert "AVX512" not in (REPO / "docs" / "phase4" / "GOAL_BASE64.md").read_text(encoding="utf-8").split("No `AVX512_CFLAGS`")[0] or "No `AVX512_CFLAGS`" in (
        REPO / "docs" / "phase4" / "GOAL_BASE64.md"
    ).read_text(encoding="utf-8")


def test_measurement_scripts_keep_the_bar_and_do_not_open_seals():
    for name in ("measure_lua_parse.py", "measure_base64_encode.py"):
        text = (REPO / "tools" / name).read_text(encoding="utf-8")
        assert "sealed_observations" not in text
        assert "held_out" not in text
        assert "targets/zlib" not in text
        assert "BAR = 0.90" in text
        assert "install(REPO)" in text
        assert '"stable_improvement": False' in text


def test_lua_miss_and_base64_sample_follow_the_frozen_rule():
    lua = _load("lua_parse_goal.json")
    base64 = _load("base64_encode_goal.json")
    assert lua["synthetic"] is False and base64["synthetic"] is False
    assert lua["stable_improvement"] is False and base64["stable_improvement"] is False
    assert statistics.median(lua["baseline_samples_ns"]) == lua["baseline_median_ns"]
    assert statistics.median(lua["candidate_samples_ns"]) == lua["candidate_median_ns"]
    assert len(lua["baseline_samples_ns"]) == 21
    assert lua["candidate_median_ns"] / lua["baseline_median_ns"] == lua["ratio_candidate_over_baseline"]
    assert lua["ratio_candidate_over_baseline"] > 0.9
    assert lua["correct"] is True
    assert lua["enhancement_met"] is False
    assert lua["attempt_status"] == "closed_missed"
    assert statistics.median(base64["baseline_samples_ns"]) == base64["baseline_median_ns"]
    assert statistics.median(base64["candidate_samples_ns"]) == base64["candidate_median_ns"]
    assert base64["candidate_median_ns"] / base64["baseline_median_ns"] == base64["ratio_candidate_over_baseline"]
    assert base64["ratio_candidate_over_baseline"] <= 0.9
    assert base64["correct"] is True
    assert base64["same_encoded_bytes"] is True
    assert base64["enhancement_met"] is True
    assert base64["attempt_status"] == "closed_met"
    assert base64["candidate_binary_bytes"] > base64["baseline_binary_bytes"]
    assert base64["binary_size_is_a_bar"] is False


def test_seal_guard_still_refuses_zlib_and_also_refuses_the_new_seals():
    original = install(REPO)
    try:
        for relative in (
            "targets/zlib/sealed_observations.json",
            "targets/lua/sealed_observations.json",
            "targets/base64/sealed_observations.json",
        ):
            try:
                open(REPO / relative, encoding="utf-8")
            except SealViolation:
                continue
            raise AssertionError(relative)
    finally:
        restore(original)
