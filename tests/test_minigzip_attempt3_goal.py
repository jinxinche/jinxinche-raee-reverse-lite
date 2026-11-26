"""The third minigzip goal stays at least as strict as the closed one."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GOAL_MD = "18c6f8437fc29242a650d327f7a764c276f11a26b56486fa9ecc15bc2c513319"
GOAL_JSON = "9c37508874c48dac08bcd0da73a7ed0effc9ae6c2f30e9f2ece91dafa38ed901"


def _logical(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def test_attempt3_goal_is_not_weaker_and_is_not_the_earlier_misses():
    markdown = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT3.md"
    payload = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT3.json"
    assert hashlib.sha256(_logical(markdown.read_bytes())).hexdigest() == GOAL_MD
    assert hashlib.sha256(_logical(payload.read_bytes())).hexdigest() == GOAL_JSON
    text = markdown.read_text(encoding="utf-8")
    body = payload.read_text(encoding="utf-8")
    assert "0.9956544893408726" in text
    assert "1.003810222421081" in text
    assert "does not change" in text
    assert '"decompress_ratio_max": 0.9' in body
    assert '"compress_ratio_max": 1.05' in body
    assert '"supersedes_closed_goal": false' in body
    assert '"supersedes_attempt2": false' in body
    assert '"stable_improvement_allowed_for_one_sample": false' in body
    assert '"floor_samples_decide_enhancement": false' in body
    assert '"cflags_override": null' in body
    assert '"minigzip_buflen": 16384' in body
    assert '"setvbuf_added": false' in body
    assert '"crc32_hook": null' in body
    assert '"copy_width_bytes": 16' in body
    assert '"-O3"' in body and '"-flto"' in body
    assert "./configure && make" in text
    script = (REPO / "tools" / "measure_zlib_minigzip_attempt3.py").read_text(encoding="utf-8")
    assert "install(REPO)" in script
    assert "held_out" not in script
    assert "sealed_observations" not in script
    assert "published_acceptance" not in script
    assert "0.90" in script
    assert "1.05" in script
    assert "262144" not in script
    assert "refusing a crc32 hook" in script
    assert "_mm_loadu_si128" in script
    assert '"stable_improvement": False' in script
