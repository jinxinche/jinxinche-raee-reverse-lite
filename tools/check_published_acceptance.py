"""Check the published Canterbury inputs. This set is not blind.

Expected gzip bytes are not read from the tree. GNU gzip and CPython zlib
are the oracles. A CRC of 00000000 fails.
"""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.published_acceptance import (  # noqa: E402
    gzip_oracle,
    judge_observed_crc,
    load_manifest,
    verify_inputs,
    verify_seal,
)


def main() -> int:
    minigzip = Path(sys.argv[1])
    bench = Path(sys.argv[2])
    out = Path(sys.argv[3])
    manifest = load_manifest(REPO)
    seal = verify_seal(REPO)
    inputs = verify_inputs(REPO)
    gzip_bin = shutil.which("gzip")
    gzip_version = None
    if gzip_bin:
        probed = subprocess.run([gzip_bin, "--version"], capture_output=True, text=True, check=False)
        gzip_version = (probed.stdout or probed.stderr).splitlines()[0] if (probed.stdout or probed.stderr) else None
    rows = []
    ok = seal["match"] and all(item["matches_manifest"] for item in inputs) and manifest.get("blind") is False
    for item in manifest["inputs"]:
        data = (REPO / "targets" / "zlib" / "published_acceptance" / "inputs" / item["name"]).read_bytes()
        crc_run = subprocess.run([str(bench), "crc"], input=data, capture_output=True, check=False)
        observed = crc_run.stdout.decode("ascii", "replace").strip()
        python_hex = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
        verdict = judge_observed_crc(observed, python_hex)
        gzip_run = subprocess.run([str(minigzip)], input=data, capture_output=True, check=False)
        external = gzip_oracle(gzip_run.stdout, Path(tempfile.mkdtemp(prefix="rrl-gzip-")) / item["name"])
        external_match = bool(external.get("ran") and external.get("returncode") == 0 and external.get("stdout") == data)
        try:
            python_plain = zlib.decompress(gzip_run.stdout, wbits=16 + zlib.MAX_WBITS) if gzip_run.returncode == 0 else b""
            python_match = python_plain == data
        except zlib.error:
            python_match = False
        row = {
            "name": item["name"],
            "length": len(data),
            "crc_exit": crc_run.returncode,
            "observed_crc32": observed,
            "python_crc32": python_hex,
            "judge": verdict,
            "minigzip_exit": gzip_run.returncode,
            "gzip_external_ran": external.get("ran"),
            "gzip_external_match": external_match,
            "python_zlib_decompress_match": python_match,
        }
        rows.append(row)
        ok = (
            ok
            and verdict["pass"]
            and crc_run.returncode == 0
            and gzip_run.returncode == 0
            and external_match
            and python_match
        )
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    report = {
        "minigzip": str(minigzip),
        "minigzip_sha256": hashlib.sha256(minigzip.read_bytes()).hexdigest() if minigzip.is_file() else None,
        "crc_bench": str(bench),
        "blind": False,
        "blind_claim": False,
        "blind_reason": manifest["blind_reason"],
        "inputs_invented_for_this_candidate": False,
        "inputs_origin": manifest.get("inputs_origin"),
        "origin_url": manifest.get("origin_url"),
        "origin_tar_sha256": manifest.get("origin_tar_sha256"),
        "expected_gzip_stored": False,
        "oracle": "GNU gzip and CPython zlib",
        "tuned_on_this_set": False,
        "seal_match": seal["match"],
        "inputs_match_manifest": all(item["matches_manifest"] for item in inputs),
        "sample_size": len(rows),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_zlib": zlib.ZLIB_VERSION,
        "gzip": gzip_version,
        "uname": uname.stdout.strip(),
        "rows": rows,
        "pass": ok,
        "self_built_is_not_the_only_check": True,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": ok, "blind": False, "sample_size": len(rows)}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
