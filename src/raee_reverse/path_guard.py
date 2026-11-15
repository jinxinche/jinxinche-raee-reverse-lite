"""Refuse opens of the held-out acceptance tree and the non-blind seal.

The guard covers this process's open() calls. It does not make a single-agent
run blind: the same agent can still read the files by not installing the guard.
"""

from __future__ import annotations

import builtins
from pathlib import Path

DENIED = (
    "targets/zlib/held_out",
    "targets/zlib/sealed_observations.json",
)


class SealViolation(RuntimeError):
    pass


def denied(path: Path, repo: Path) -> bool:
    try:
        relative = path.resolve().relative_to(repo.resolve())
    except (ValueError, OSError):
        return False
    text = relative.as_posix()
    for item in DENIED:
        if text == item or text.startswith(item + "/"):
            return True
    return False


def install(repo: str | Path):
    root = Path(repo).resolve()
    original = builtins.open

    def guarded(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            if denied(Path(file), root):
                raise SealViolation(f"refusing to open sealed acceptance path: {file}")
        return original(file, *args, **kwargs)

    builtins.open = guarded
    return original


def restore(original) -> None:
    builtins.open = original
