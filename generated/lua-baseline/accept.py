"""Compare a built luac with the sealed surfaces.

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

from raee_reverse.cli_contract import LUA_COLLECTED, LUA_UNCOLLECTED, cli_verdict, lua_final_files  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

SEAL = REPO / "targets" / "lua" / "sealed_observations.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one(binary: Path, parent: Path, name: str, data: bytes) -> dict:
    work = parent / name
    work.mkdir(parents=True)
    copy = work / "luac"
    copy.write_bytes(binary.read_bytes())
    copy.chmod(0o755)
    (work / "chunk.lua").write_bytes(data)
    result = run_sandboxed(
        ["./luac", "-p", "chunk.lua"],
        work_dir=work,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=1_000_000,
    )
    output = work / "luac.out"
    return {
        "exit_code": result["returncode"],
        "stdout_sha256": _sha(result["stdout"]),
        "stderr_sha256": _sha(result["stderr"]),
        "output_file_exists": output.exists(),
        "output_file_sha256": _sha(output.read_bytes()) if output.exists() else None,
        "truncated": result["truncated"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    binary = args.prefix / "bin" / "luac"
    seal = json.loads(SEAL.read_text(encoding="utf-8"))
    files = lua_final_files()
    rows = []
    with tempfile.TemporaryDirectory(prefix="rrl-lua-accept-") as temporary:
        parent = Path(temporary)
        for name, data in files.items():
            key = f"final:{name}"
            expected = seal["cases"][key]
            if expected["input_sha256"] != _sha(data):
                raise SystemExit(f"generator does not match the sealed input for {name}")
            observed = _one(binary, parent, name, data)
            verdict = cli_verdict(observed, expected, collected=LUA_COLLECTED, uncollected=LUA_UNCOLLECTED)
            rows.append({"name": name, "compatible": verdict["compatible_on_collected_surfaces"], "mismatches": verdict["mismatches"]})
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
