"""Independent evidence dimensions. None of these is a single confidence score."""

from __future__ import annotations

from enum import StrEnum


class Kind(StrEnum):
    REQUIREMENT = "requirement"
    ARTIFACT = "artifact"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    CLAIM = "claim"
    CANDIDATE = "candidate"
    ATTRIBUTION = "attribution"
    RETRACTION = "retraction"
    EVALUATION = "evaluation"
    ENVIRONMENT = "environment"


class Provenance(StrEnum):
    OBSERVED = "observed"
    IMPORTED = "imported"
    MODEL_GENERATED = "model_generated"


class ExecutionResult(StrEnum):
    NOT_EXECUTED = "not_executed"
    PASSED = "passed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class Applicability(StrEnum):
    VALID = "valid"
    STALE = "stale"
    RETRACTED = "retracted"
    INCOMPLETE_SCOPE = "incomplete_scope"


class Usage(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    QUALIFY = "qualify"
    BACKGROUND = "background"


class RelType(StrEnum):
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    COLLECTED_IN = "collected_in"
    VERIFIES = "verifies"
    SUPERSEDES = "supersedes"
    INVALIDATED_BY = "invalidated_by"


class SupportStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTESTED = "contested"
    INSUFFICIENT = "insufficient"
    DOWNGRADED = "downgraded"


class TaskState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class FailureClass(StrEnum):
    NONE = "none"
    INFRA = "infra"
    DETERMINISTIC = "deterministic"


class ResourceClass(StrEnum):
    DEV = "dev"
    NATIVE_ANALYSIS = "native_analysis"
    MODEL = "model"
    PERF = "perf"


EXCLUSIVE_RESOURCE_CLASSES = {
    ResourceClass.NATIVE_ANALYSIS,
    ResourceClass.MODEL,
    ResourceClass.PERF,
}

SCOPE_KEYS = ("inputs", "behaviors", "environments")


def scope_explicit(scope: object) -> bool:
    """A pass may only cover a listed input, behavior, and environment.

    An empty scope is not universal quantification.
    """
    if not isinstance(scope, dict):
        return False
    for key in SCOPE_KEYS:
        items = scope.get(key)
        if not isinstance(items, list) or not items:
            return False
        if not all(isinstance(item, str) and item.strip() for item in items):
            return False
    return True


def scope_covers(have: object, need: object) -> bool:
    if not scope_explicit(need) or not isinstance(have, dict):
        return False
    for key in SCOPE_KEYS:
        present = set(have.get(key) or [])
        for item in need[key]:
            if item not in present:
                return False
    if need.get("require_complete_output") and not have.get("complete_output"):
        return False
    return True
