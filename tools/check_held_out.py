"""Check the held-out inputs once. This is not called by the measurement script."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.held_out import gzip_decompress, judge_crc, load_manifest, verify_inputs, verify_seal  # noqa: E402


def main() -> int:
    minigzip = Path(sys.argv[1])
    bench = Path(sys.argv[2])
    out = Path(sys.argv[3])
    manifest = load_manifest(REPO)
    seal = verify_seal(REPO)
    inputs = verify_inputs(REPO)
    rows = []
    ok = seal["match"] and all(item["matches_manifest"] for item in inputs)
    for item in manifest["inputs"]:
        data = (REPO / "targets" / "zlib" / "held_out" / "inputs" / item["name"]).read_bytes()
        crc_run = subprocess.run([str(bench), "crc"], input=data, capture_output=True, check=False)
        observed = crc_run.stdout.decode("ascii", "replace").strip()
        python_hex = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
        verdict = judge_crc(item["name"], observed, python_hex)
        gzip_run = subprocess.run([str(minigzip)], input=data, capture_output=True, check=False)
        external = gzip_decompress(gzip_run.stdout, out.parent / "gzip" / item["name"])
        external_match = bool(external.get("ran") and external.get("returncode") == 0 and external.get("stdout") == data)
        row = {
            "name": item["name"],
            "crc_exit": crc_run.returncode,
            "observed_crc32": observed,
            "python_crc32": python_hex,
            "judge": {key: value for key, value in verdict.items()},
            "minigzip_exit": gzip_run.returncode,
            "gzip_external_ran": external.get("ran"),
            "gzip_external_match": external_match,
        }
        rows.append(row)
        ok = ok and verdict["pass"] and crc_run.returncode == 0 and gzip_run.returncode == 0 and external_match
    report = {
        "blind": False,
        "blind_reason": manifest["blind_reason"],
        "seal_match": seal["match"],
        "inputs_match_manifest": all(item["matches_manifest"] for item in inputs),
        "python": platform.python_version(),
        "python_zlib": zlib.ZLIB_VERSION,
        "rows": rows,
        "pass": ok,
        "self_built_is_not_the_only_check": True,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": ok, "blind": False}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
