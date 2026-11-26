"""Compare a built base64 CLI with the sealed encode surfaces.

The build recipe does not read the sealed file. This program does.
The comparison is non-blind.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.cli_contract import BASE64_COLLECTED, BASE64_UNCOLLECTED, base64_final_inputs, cli_verdict  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

SEAL = REPO / "targets" / "base64" / "sealed_observations.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one(binary: Path, parent: Path, name: str, data: bytes) -> dict:
    work = parent / name
    work.mkdir(parents=True)
    copy = work / "base64"
    copy.write_bytes(binary.read_bytes())
    copy.chmod(0o755)
    result = run_sandboxed(
        ["./base64"],
        work_dir=work,
        stdin=data,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )
    decode_work = parent / f"{name}-decode"
    decode_work.mkdir(parents=True)
    decode_copy = decode_work / "base64"
    decode_copy.write_bytes(binary.read_bytes())
    decode_copy.chmod(0o755)
    decoded = run_sandboxed(
        ["./base64", "-d"],
        work_dir=decode_work,
        stdin=result["stdout"],
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )
    return {
        "exit_code": result["returncode"],
        "stdout_sha256": _sha(result["stdout"]),
        "stderr_sha256": _sha(result["stderr"]),
        "stdout_has_newline": b"\n" in result["stdout"],
        "roundtrip_equals_input": (
            not result["truncated"]
            and not decoded["truncated"]
            and decoded["returncode"] == 0
            and decoded["stdout"] == data
        ),
        "truncated": result["truncated"] or decoded["truncated"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    binary = args.prefix / "bin" / "base64"
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory(prefix="rrl-base64-accept-") as temporary:
        parent = Path(temporary)
        for name, data in base64_final_inputs().items():
            key = f"final:{name}"
            expected = seal["cases"][key]
            if expected["input_sha256"] != _sha(data):
                raise SystemExit(f"generator does not match the sealed input for {name}")
            observed = _one(binary, parent, name, data)
            verdict = cli_verdict(observed, expected, collected=BASE64_COLLECTED, uncollected=BASE64_UNCOLLECTED)
            rows.append({"name": name, "compatible": verdict["compatible_on_collected_surfaces"], "mismatches": verdict["mismatches"], "not_compared": verdict["not_compared"]})
    report = {
        "acceptance": "non-blind",
        "accepted_pass": False,
        "universal": False,
        "rows": rows,
        "pass": all(row["compatible"] for row in rows) and bool(rows),
    }
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
