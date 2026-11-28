"""The fourth minigzip goal is a different metric and is not a weaker bar."""

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GOAL_MD = "bc1be23e11e77493c1096e9ae2a565fa241c4fd7d4f4dbe6f68d00379e8071ef"
GOAL_JSON = "1a6e737f283fa9181f596a507395807ca7b1eec3bc31e850486b7e978c5f2ce7"


def _logical(data: bytes) -> bytes:
    if b"\0" in data:
        return data
    return data.replace(b"\r\n", b"\n")


def test_attempt4_goal_is_not_weaker_and_does_not_reopen_earlier_misses():
    markdown = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT4.md"
    payload = REPO / "docs" / "phase4" / "GOAL_MINIGZIP_ATTEMPT4.json"
    assert hashlib.sha256(_logical(markdown.read_bytes())).hexdigest() == GOAL_MD
    assert hashlib.sha256(_logical(payload.read_bytes())).hexdigest() == GOAL_JSON
    text = markdown.read_text(encoding="utf-8")
    body = payload.read_text(encoding="utf-8")
    assert "Changing the metric does not turn any earlier miss into a pass." in text
    assert "0.9956544893408726" in text
    assert "1.003810222421081" in text
    assert "0.9977490944434495" in text
    assert "0.9771281840737216" in text
    assert "does not change" in text
    assert "in-process" in text
    assert "CLOCK_MONOTONIC" in text
    assert '"decompress_ratio_max": 0.9' in body
    assert '"compress_ratio_max": 1.05' in body
    assert '"supersedes_closed_goal": false' in body
    assert '"supersedes_attempt2": false' in body
    assert '"supersedes_attempt3": false' in body
    assert '"metric_change_does_not_convert_earlier_misses": true' in body
    assert '"metric_is_sandboxed_minigzip_wall_time": false' in body
    assert '"stable_improvement_allowed_for_one_sample": false' in body
    assert '"true_floor_decides_enhancement": false' in body
    assert '"cflags_override": null' in body
    assert '"minigzip_buflen": 16384' in body
    assert '"setvbuf_added": false' in body
    assert '"crc32_hook": null' in body
    assert '"copy_width_bytes": 16' in body
    assert '"payload_bytes": 4194304' in body
    assert '"runs": 21' in body
    assert '"warmup_excluded": 1' in body
    assert '"-O3"' in body and '"-flto"' in body
    assert "./configure && make" in text
    script = (REPO / "tools" / "measure_zlib_minigzip_attempt4.py").read_text(encoding="utf-8")
    assert "install(REPO)" in script
    assert "held_out" not in script
    assert "sealed_observations" not in script
    assert "published_acceptance" not in script
    assert "blind_acceptance" not in script
    assert "0.90" in script
    assert "1.05" in script
    assert "262144" not in script
    assert "refusing a crc32 hook" in script
    assert "refusing a sandboxed wall-time clock" in script
    assert "CLOCK_MONOTONIC" in script
    assert "_mm_loadu_si128" in script
    assert '"stable_improvement": False' in script
    harness = (REPO / "targets" / "zlib" / "harness" / "inflate_deflate_bench.c").read_text(encoding="utf-8")
    assert "CLOCK_MONOTONIC" in harness
    assert "pthread" not in harness
    assert "15 + 16" in harness
    assert "% 251" in harness
    assert "Z_DEFAULT_COMPRESSION" in harness
    assert "Z_FINISH" in harness
    assert "Z_NO_FLUSH" in harness
