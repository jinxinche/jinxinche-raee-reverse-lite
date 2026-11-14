"""Canonical JSON and content digests.

A path or mtime is not a content identity. Callers that pass those fields
to cache-key construction must drop them before hashing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_obj(obj: Any) -> str:
    return digest_bytes(canonical_dumps(obj).encode("utf-8"))
