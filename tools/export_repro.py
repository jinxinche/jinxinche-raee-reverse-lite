"""Copy the compatible baseline into a reproduction directory.

The copy does not include the sealed expected-output file. Final acceptance
stays non-blind and lives in the repository.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "generated" / "zlib-baseline"
FILES = ["README.md", "build_and_check.py", "accept.py"]


def main() -> int:
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    lines = []
    for name in FILES:
        target = destination / name
        shutil.copy2(SOURCE / name, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    harness = REPO / "targets" / "zlib" / "harness" / "crc32_cli.c"
    harness_dest = destination / "crc32_cli.c"
    shutil.copy2(harness, harness_dest)
    lines.append(f"{hashlib.sha256(harness_dest.read_bytes()).hexdigest()}  crc32_cli.c")
    (destination / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (destination / "README-REPRO.md").write_text(
        "\n".join(
            [
                "# Reproduction pack for the zlib 1.4 compatible baseline",
                "",
                "Run `build_and_check.py` from a checkout that still contains `targets/zlib/dist/zlib-1.4.tar.gz`.",
                "Dev checks do not read the sealed final-acceptance file.",
                "`accept.py` does read it. That comparison is non-blind and is not included as expected bytes in this directory.",
                "This pack is not an enhanced zlib and not an REA comparison.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
