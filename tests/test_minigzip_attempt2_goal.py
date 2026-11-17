"""The second minigzip goal stays at least as strict as the closed one."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GOAL_MD = "d1ae14d67bf28a6bd4cf95cd2cd535d593308f5de185fff0a816c38e3e2349eb"
GOAL_JSON = "635460b32fdc6c381ff807f6199ce854f4b3c09de9716425a6ee5c0d38050dc8"


def _logical(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def test_attempt2_goal_is_not_weaker_than_the_closed_goal():
    markdown = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT2.md"
    payload = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT2.json"
    assert hashlib.sha256(_logical(markdown.read_bytes())).hexdigest() == GOAL_MD
    assert hashlib.sha256(_logical(payload.read_bytes())).hexdigest() == GOAL_JSON
    text = markdown.read_text(encoding="utf-8")
    body = payload.read_text(encoding="utf-8")
    assert "0.9956544893408726" in text
    assert "does not change" in text
    assert '"decompress_ratio_max": 0.9' in body
    assert '"compress_ratio_max": 1.05' in body
    assert '"supersedes_closed_goal": false' in body
    assert '"stable_improvement_allowed_for_one_sample": false' in body
    assert '"cflags_override": null' in body
    assert '"-O3"' in body and '"-flto"' in body
    assert "./configure && make" in text
