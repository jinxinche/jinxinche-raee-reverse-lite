"""Fail if the collected test ids differ from tests/COLLECTED_IDS.txt.

A missing id means a test was deleted or renamed. An extra id means the floor
file was not updated in the same change. Zero collected tests fail.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOOR = ROOT / "tests" / "COLLECTED_IDS.txt"


def collected() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    ids = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("="):
            ids.append(line.split(" ", 1)[0])
    if not ids:
        raise SystemExit("pytest collected zero tests")
    return ids


def main() -> int:
    ids = collected()
    if "--write" in sys.argv:
        FLOOR.write_text("\n".join(ids) + "\n", encoding="utf-8")
        print(f"wrote {len(ids)} ids")
        return 0
    required = [line.strip() for line in FLOOR.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not required:
        raise SystemExit("collection floor is empty")
    missing = sorted(set(required) - set(ids))
    extra = sorted(set(ids) - set(required))
    if missing or extra:
        sys.stderr.write(f"missing: {missing}\nextra: {extra}\n")
        return 1
    print(f"collection floor matches {len(ids)} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
