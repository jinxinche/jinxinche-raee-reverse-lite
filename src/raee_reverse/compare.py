"""Compare named observation surfaces.

A surface that was not collected is `not_compared`. It is not a match.
Agreement on the collected surfaces is not agreement on every input.
"""

from __future__ import annotations

COLLECTED_SURFACES = (
    "stdout_sha256",
    "stderr_sha256",
    "exit_code",
    "roundtrip_equals_input",
    "crc32_hex",
)

# These names are part of the zlib contract boundary. They stay not_compared
# until a run actually records them. Adding a name here is not a measurement.
UNCOLLECTED_SURFACES = (
    "wall_clock_threshold",
    "peak_rss",
    "named_file_mode",
    "compression_level_9",
    "missing_path_stderr_text",
    "crc32_combine",
    "multi_member_gzip",
    "concurrent_calls",
)


def compare_surfaces(observed: dict, expected: dict, *, collected: tuple[str, ...] = COLLECTED_SURFACES) -> dict:
    surfaces: dict[str, str] = {}
    for name in collected:
        if name not in observed or name not in expected:
            surfaces[name] = "not_compared"
        elif observed[name] == expected[name]:
            surfaces[name] = "match"
        else:
            surfaces[name] = "mismatch"
    for name in UNCOLLECTED_SURFACES:
        surfaces[name] = "not_compared"
    collected_results = [surfaces[name] for name in collected]
    compatible = bool(collected_results) and all(item == "match" for item in collected_results)
    return {
        "surfaces": surfaces,
        "compatible_on_collected_surfaces": compatible,
        "universal": False,
        "accepted_pass": False,
        "not_compared": [name for name, value in surfaces.items() if value == "not_compared"],
        "mismatches": [name for name, value in surfaces.items() if value == "mismatch"],
    }
