"""Compare a built baseline to the sealed surfaces.

Run this only after the baseline recipe is fixed. It is the component that
reads the final-acceptance file. The acceptance label is non-blind.
compression_level_9 is not scored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.sandbox import run_sandboxed  # noqa: E402
from raee_reverse.zlib_contract import zlib_verdict  # noqa: E402

SEALED = REPO / "targets" / "zlib" / "sealed_observations.json"


def regenerate_inputs() -> dict[str, dict[str, bytes]]:
    """Same generator that sealed the sets. This does not read expected outputs."""
    dev = {"empty": b"", "abc": b"abc", "hello": b"hello"}
    tune = {
        "tune-alpha": b"tune-alpha",
        "tune-repeat": b"tune-beta" * 10,
        "tune-range": bytes(range(64)),
    }
    final = {}
    generator = random.Random(20261114)
    for index, length in enumerate((1, 2, 7, 16, 32, 100, 256, 1000)):
        final[f"final-{index}-len{length}"] = bytes(generator.randrange(256) for _ in range(length))
    return {"dev": dev, "tune": tune, "final": final}


def observe(minigzip: Path, crc_bin: Path, data: bytes, work: Path) -> dict:
    compressed = run_sandboxed(
        [str(minigzip)], work_dir=work / "c", stdin=data, timeout=20, cpu_seconds=10, fsize_bytes=5_000_000
    )
    decompressed = run_sandboxed(
        [str(minigzip), "-d"],
        work_dir=work / "d",
        stdin=compressed["stdout"],
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
    )
    crc = run_sandboxed([str(crc_bin)], work_dir=work / "r", stdin=data, timeout=20, cpu_seconds=10)
    return {
        "stdout_sha256": hashlib.sha256(compressed["stdout"]).hexdigest(),
        "stderr_sha256": hashlib.sha256(compressed["stderr"]).hexdigest(),
        "exit_code": compressed["returncode"],
        "roundtrip_equals_input": decompressed["returncode"] == 0 and decompressed["stdout"] == data,
        "crc32_hex": crc["stdout"].decode("ascii", "replace").strip() if crc["returncode"] == 0 else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    inputs = regenerate_inputs()
    prefix = Path(args.prefix)
    work = Path(args.work)
    rows = []
    compatible = True
    for split, mapping in inputs.items():
        for name, data in mapping.items():
            expected = sealed["sets"][split][name]["observed"]
            got = observe(prefix / "bin" / "minigzip", prefix / "bin" / "crc32_cli", data, work / split / name)
            verdict = zlib_verdict(got, expected)
            if not verdict["compatible_on_collected_surfaces"]:
                compatible = False
            rows.append(
                {
                    "split": split,
                    "name": name,
                    "input_sha256": hashlib.sha256(data).hexdigest(),
                    "compatible_on_collected_surfaces": verdict["compatible_on_collected_surfaces"],
                    "mismatches": verdict["mismatches"],
                    "not_compared": verdict["not_compared"],
                    "compression_level_9": "not_compared",
                    "universal": False,
                    "acceptance": "non-blind",
                }
            )
    final_rows = [row for row in rows if row["split"] == "final"]
    report = {
        "acceptance": "non-blind",
        "compatible_baseline_matches_sealed_surfaces": compatible,
        "final_match_count": sum(1 for row in final_rows if row["compatible_on_collected_surfaces"]),
        "final_count": len(final_rows),
        "compression_level_9": "not_compared",
        "universal": False,
        "accepted_pass": False,
        "rows": rows,
    }
    Path(args.result).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "compatible_baseline_matches_sealed_surfaces": compatible,
        "final_match_count": report["final_match_count"],
        "final_count": report["final_count"],
        "mismatches": [row["name"] for row in rows if row["mismatches"]],
        "compression_level_9": "not_compared",
        "acceptance": "non-blind",
    }))
    return 0 if compatible else 1


if __name__ == "__main__":
    raise SystemExit(main())
