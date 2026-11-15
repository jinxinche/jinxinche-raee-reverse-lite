"""Previous failure records stay. Checkout newline conversion is not a rewrite."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FROZEN = {
    "docs/phase4/GOAL.md": "d20552ca4b56fb3db6c2ca8e498e0cde1fd0712d0f3700b791793650998bf2eb",
    "docs/evidence/zlib_enhancement.json": "e18e7ce925d6beb907c78324b5f8a2c8969432133c3ad57367dc9748c76f201b",
    "docs/a18/routing_comparison.json": "61b8991286d9c5f4061b8ac890d8b69df0ffb128c96c951b510133cfd9cd27ed",
    "docs/a18/REA_COMPARISON.md": "aa5a3d8d363b5901f6235eb32a66c5601b742d3c8d096f62664f6f572f063f41",
    "docs/a19/standard_tier.json": "379d922e3828b7ab3c3948ddac66df5c95c88cfaf605a9aa5c51af6bdab79cd0",
    "docs/a19/attempt2.json": "71cda4f5111442254d1553d5abef5b2b9ddda37a407335e64cd27462e4845de8",
    "docs/a19/standard_tier_v3.json": "7db0dd519d07495a3a9c2f758f488a036822b713931ed01bab77ac88aa7b26c8",
    "targets/zlib/NON_BLIND.md": "874ee54bde8aa4b06e6881d244b3177530dec24a36cd531ffbf15e90b71c196f",
}


def _logical(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def test_closed_failures_are_unchanged():
    for name, digest in FROZEN.items():
        assert hashlib.sha256(_logical((REPO / name).read_bytes())).hexdigest() == digest


def test_crlf_checkout_is_not_a_rewrite_of_the_closed_goal():
    original = (REPO / "docs/phase4/GOAL.md").read_bytes()
    assert hashlib.sha256(_logical(original.replace(b"\n", b"\r\n"))).hexdigest() == FROZEN["docs/phase4/GOAL.md"]


def test_new_crc32_goal_does_not_claim_the_closed_goal():
    text = (REPO / "docs" / "phase4" / "GOAL_CRC32.md").read_text(encoding="utf-8")
    assert "does not change" in text
    assert "0.99565" in text or "0.99565" in (REPO / "docs" / "evidence" / "zlib_enhancement.json").read_text(encoding="utf-8")
    goal = (REPO / "docs" / "phase4" / "GOAL_CRC32.json").read_text(encoding="utf-8")
    assert '"supersedes_closed_goal": false' in goal
    assert '"crc32_ratio_max": 0.9' in goal
