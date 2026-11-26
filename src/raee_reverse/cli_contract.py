"""Executable contracts for the Lua and base64 targets.

A match on the collected surfaces is not universal and is not accepted_pass.
Names that were not collected stay not_compared. Truncation is not a match.
"""

from __future__ import annotations

import random

LUA_COLLECTED = (
    "exit_code",
    "stdout_sha256",
    "stderr_sha256",
    "output_file_exists",
    "output_file_sha256",
)

LUA_UNCOLLECTED = (
    "executes_chunk",
    "listing",
    "strip_debug",
    "renamed_output",
    "wall_clock_threshold",
    "peak_rss",
    "other_lua_versions",
    "ghidra",
)

BASE64_COLLECTED = (
    "exit_code",
    "stdout_sha256",
    "stderr_sha256",
    "stdout_has_newline",
    "roundtrip_equals_input",
)

BASE64_UNCOLLECTED = (
    "ignore_garbage",
    "keep_newlines",
    "wrap_widths_other_than_0_and_76",
    "multiple_input_files",
    "wall_clock_threshold",
    "peak_rss",
    "ghidra",
)


def lua_final_files() -> dict[str, bytes]:
    rng = random.Random(20261126)
    files: dict[str, bytes] = {}
    for index in range(4):
        count = rng.randint(1, 5)
        body = "".join(f"local v{j} = {rng.randint(0, 999)}\n" for j in range(count))
        files[f"valid-{index}"] = body.encode()
    files["invalid-0"] = b"local =\n"
    files["invalid-1"] = b"return =\n"
    return files


def base64_final_inputs() -> dict[str, bytes]:
    rng = random.Random(20261126)
    lengths = (4, 7, 57, 58, 76, 120)
    return {f"len-{length}": bytes(rng.getrandbits(8) for _ in range(length)) for length in lengths}


def cli_verdict(observed: dict, expected: dict, *, collected: tuple[str, ...], uncollected: tuple[str, ...]) -> dict:
    surfaces: dict[str, str] = {}
    truncated = bool(observed.get("truncated") or expected.get("truncated"))
    for name in collected:
        if name not in expected or truncated or name not in observed:
            surfaces[name] = "not_compared"
        elif observed[name] == expected[name]:
            surfaces[name] = "match"
        else:
            surfaces[name] = "mismatch"
    for name in uncollected:
        surfaces[name] = "not_compared"
    relevant = [surfaces[name] for name in collected if name in expected]
    compatible = bool(relevant) and all(item == "match" for item in relevant) and not truncated
    return {
        "surfaces": surfaces,
        "compatible_on_collected_surfaces": compatible,
        "universal": False,
        "accepted_pass": False,
        "acceptance": "non-blind",
        "not_compared": [name for name, value in surfaces.items() if value == "not_compared"],
        "mismatches": [name for name, value in surfaces.items() if value == "mismatch"],
    }
