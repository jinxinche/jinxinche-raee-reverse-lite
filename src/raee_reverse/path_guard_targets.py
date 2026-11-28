"""Refuse opens of the sealed trees of every target, not only zlib.

`path_guard.py` is a frozen checker file of the sealed blind-broad manifest, so
its bytes must not change. This module extends its deny list for the Lua and
base64 sealed observations without editing that file.
"""

from __future__ import annotations

import builtins
from pathlib import Path

from .path_guard import DENIED as ZLIB_DENIED
from .path_guard import SealViolation, restore

__all__ = ["DENIED", "SealViolation", "denied", "install", "restore"]

DENIED = ZLIB_DENIED + (
    "targets/lua/sealed_observations.json",
    "targets/base64/sealed_observations.json",
)


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
