"""Cache keys bound to content, dependencies, tool, parameters, config, and environment.

File paths and modification times are ignored. An incomplete environment is
stored and then treated as a miss.
"""

from __future__ import annotations

from typing import Any

from raee_reverse.canonical import digest_obj
from raee_reverse.errors import RrlError

_IGNORED = {"path", "paths", "mtime", "mtime_ns", "path_hint", "modified_time", "filename"}


def prepare_cache(components: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(components, dict):
        raise RrlError("E_CACHE_COMPONENTS", "cache components must be an object")
    required = (
        "content_digests",
        "dependency_digests",
        "tool_name",
        "tool_version",
        "params",
        "config",
        "env",
        "env_complete",
    )
    missing = [key for key in required if key not in components]
    if missing:
        raise RrlError("E_CACHE_COMPONENTS", "cache components are incomplete", missing=missing)
    content = _digest_list(components["content_digests"], "content_digests")
    deps = _digest_list(components["dependency_digests"], "dependency_digests")
    if not isinstance(components["tool_name"], str) or not components["tool_name"].strip():
        raise RrlError("E_CACHE_COMPONENTS", "tool_name is required")
    if not isinstance(components["tool_version"], str) or not components["tool_version"].strip():
        raise RrlError("E_CACHE_COMPONENTS", "tool_version is required")
    if not isinstance(components["params"], dict) or not isinstance(components["config"], dict):
        raise RrlError("E_CACHE_COMPONENTS", "params and config must be objects")
    if not isinstance(components["env"], dict):
        raise RrlError("E_CACHE_COMPONENTS", "env must be an object")
    env_complete = components["env_complete"] is True
    limitations: list[str] = []
    if not env_complete:
        limitations.append(
            "environment model is incomplete; cache entry is not reusable (conservative invalidation)"
        )
    bound = {
        "content_digests": content,
        "dependency_digests": deps,
        "tool_name": components["tool_name"],
        "tool_version": components["tool_version"],
        "params": components["params"],
        "config": components["config"],
        "env": components["env"],
        "env_complete": env_complete,
    }
    return {
        "key": digest_obj(bound),
        "components": bound,
        "reusable": env_complete,
        "limitations": limitations,
        "ignored_fields": sorted(set(components) & _IGNORED),
    }


def _digest_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and len(item) == 64 for item in value):
        raise RrlError("E_CACHE_COMPONENTS", f"{label} must be a list of sha256 hex digests")
    return sorted(value)
