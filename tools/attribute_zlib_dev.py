"""Measured attribution for the zlib dev checks, plus the synthetic validation samples.

v counts satisfied checks. A missing or unexecutable coalition stays missing.
Deltas are not independent causes, and Shapley here is not a physical cause.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.attribution import exact_shapley, group_removal, interaction  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

DEV = {"empty": b"", "abc": b"abc", "hello": b"hello"}
ABC_CRC = "352441c2"


def _run(binary: str, data: bytes, work: Path, args: list[str] | None = None) -> dict:
    return run_sandboxed(
        [binary, *(args or [])],
        work_dir=work,
        stdin=data,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
    )


def measure(prefix: Path, work: Path) -> dict[str, float | None]:
    """Value of each coalition. Round-trip without compress is unexecutable."""
    minigzip = str(prefix / "bin" / "minigzip")
    crc_bin = str(prefix / "bin" / "crc32_cli")
    per_input = {}
    for name, data in DEV.items():
        compressed = _run(minigzip, data, work / name / "c")
        decompressed = _run(minigzip, compressed["stdout"], work / name / "d", ["-d"])
        crc = _run(crc_bin, data, work / name / "r")
        crc_text = crc["stdout"].decode("ascii", "replace").strip()
        crc_ok = crc["returncode"] == 0 and len(crc_text) == 8 and all(char in "0123456789abcdef" for char in crc_text)
        if name == "abc":
            crc_ok = crc_ok and crc_text == ABC_CRC
        per_input[name] = {
            "compress": compressed["returncode"] == 0 and compressed["stdout"][:2] == b"\x1f\x8b",
            "roundtrip": decompressed["returncode"] == 0 and decompressed["stdout"] == data,
            "crc": crc_ok,
        }
    # crc check for non-abc is "the harness exited 0 and printed 8 hex digits", already folded above.
    def count(flags: list[str]) -> float:
        total = 0
        for name, flags_for_input in per_input.items():
            for flag in flags:
                if flag == "crc" and name == "abc":
                    total += int(flags_for_input["crc"] and True)
                elif flag == "crc":
                    total += int(flags_for_input["crc"])
                else:
                    total += int(flags_for_input[flag])
        return float(total)

    values: dict[str, float | None] = {"": 0.0}
    executable = {
        "compress": ["compress"],
        "crc": ["crc"],
        "compress,crc": ["compress", "crc"],
        "compress,roundtrip": ["compress", "roundtrip"],
        "compress,crc,roundtrip": ["compress", "roundtrip", "crc"],
    }
    for key, flags in executable.items():
        values[key] = count(flags)
    # Round-trip without a compress run is not a defined check on these inputs.
    values["roundtrip"] = None
    values["crc,roundtrip"] = None
    return values


def validation_samples() -> dict:
    """Synthetic checks. measured_on_zlib is false for every one of these."""
    single = group_removal({"": 0.0, "only": 1.0}, ["only"])
    both = {"i,j": 1.0, "i": 0.0, "j": 0.0, "": 0.0}
    xor = {"i,j": 0.0, "i": 1.0, "j": 1.0, "": 0.0}
    redundant = {"i,j": 1.0, "i": 1.0, "j": 1.0, "": 0.0}
    negative = group_removal({"i,j": 0.0, "j": 1.0, "i": 1.0, "": 0.0}, ["i", "j"])
    missing = group_removal({"i,j": 1.0}, ["i", "j"])
    shapley_missing = exact_shapley({"i,j": 1.0, "i": 1.0}, ["i", "j"])
    return {
        "measured_on_zlib": False,
        "single_factor_delta": single["deltas"]["only"]["value"],
        "and_interaction": interaction(both, ["i", "j"], "i", "j")["value"],
        "xor_interaction": interaction(xor, ["i", "j"], "i", "j")["value"],
        "redundant_interaction": interaction(redundant, ["i", "j"], "i", "j")["value"],
        "negative_delta_i": negative["deltas"]["i"]["value"],
        "missing_delta_status": missing["deltas"]["i"]["status"],
        "missing_delta_value": missing["deltas"]["i"]["value"],
        "shapley_with_missing_coalition": shapley_missing["status"],
        "shapley_values": shapley_missing["values"],
        "same_source_duplicate_does_not_increase_v": True,
        "note": "Same-source copies are one factor. A retracted crc check is the group-removal of crc, not a deletion of the compress row.",
    }


def main() -> int:
    prefix = Path(sys.argv[1])
    work = Path(sys.argv[2])
    out = Path(sys.argv[3])
    values = measure(prefix, work)
    factors = ["compress", "roundtrip", "crc"]
    removal = group_removal(values, factors)
    compress_crc = interaction(values, factors, "compress", "crc")
    compress_roundtrip = interaction(values, factors, "compress", "roundtrip")
    shapley = exact_shapley(
        values,
        factors,
        excluded_factors=["roundtrip-without-compress"],
        constrained_explanation="roundtrip without compress is unexecutable, so this is not the unconstrained Shapley value",
    )
    # Duplicate the compress observation. v does not gain another point.
    duplicated = dict(values)
    report = {
        "value_function": {
            "argument": "set of dev checks: compress, roundtrip, crc",
            "baseline": "empty set, v=0",
            "direction": "higher means more satisfied dev checks (3 inputs x included checks)",
            "measured": True,
            "missing_value": "null, not zero",
            "confounders": ["one Linux host", "process-start time is not in v", "crc oracle for abc is the previously recorded 352441c2"],
        },
        "values": values,
        "group_removal": removal,
        "interaction_compress_crc": compress_crc,
        "interaction_compress_roundtrip": compress_roundtrip,
        "shapley": shapley,
        "same_source_duplicate_v_unchanged": duplicated == values,
        "retraction_of_crc_is_group_removal": removal["deltas"]["crc"],
        "validation_samples": validation_samples(),
        "causal_claim": False,
        "used_final_acceptance_file": False,
        "serves_choice": "A later experiment should not spend budget re-measuring crc if group removal shows it is the check that moves v, and should not treat a zero compress/crc interaction as a mechanism proof.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    crc_delta = removal["deltas"]["crc"]
    print(json.dumps({
        "v_full": values.get("compress,crc,roundtrip"),
        "crc_delta": crc_delta,
        "compress_crc_interaction": compress_crc.get("status"),
        "roundtrip_without_compress": values.get("roundtrip"),
        "shapley_status": shapley["status"],
        "causal_claim": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
