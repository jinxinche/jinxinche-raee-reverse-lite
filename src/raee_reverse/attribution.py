"""Arithmetic attribution on a caller-supplied value function.

These functions do not measure a target program. A missing coalition is not
zero. A computed delta is not an independent cause. Shapley on an evidence
value function is not a real-world causal contribution.
"""

from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Any

from raee_reverse.errors import RrlError


def coalition_key(items: object) -> str:
    if isinstance(items, str):
        parts = [part for part in items.split(",") if part]
    else:
        parts = list(items)  # type: ignore[arg-type]
    if not all(isinstance(part, str) and part.strip() and "," not in part for part in parts):
        raise RrlError("E_FACTOR_NAME", "factor names must be non-empty strings without commas")
    return ",".join(sorted(parts))


def _value(v: dict[str, Any], items: list[str] | tuple[str, ...]) -> float | None:
    key = coalition_key(items)
    if key not in v or v[key] is None:
        return None
    number = v[key]
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise RrlError("E_VALUE_TYPE", "value function entries must be numbers or null", key=key)
    return float(number)


def _base(v: dict[str, Any], factors: list[str]) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise RrlError("E_VALUE_FUNCTION", "v must be a mapping of coalition key to number or null")
    if not factors or not all(isinstance(factor, str) for factor in factors):
        raise RrlError("E_FACTORS", "at least one factor name is required")
    return {
        "causal_claim": False,
        "not_independent_cause": True,
        "treated_missing_as_zero": False,
        "factors": list(factors),
    }


def group_removal(v: dict[str, Any], factors: list[str]) -> dict[str, Any]:
    """Δᵢ = v(N) − v(N \\ {i}). Missing coalitions stay missing."""
    report = _base(v, factors)
    whole = _value(v, factors)
    deltas = {}
    for factor in factors:
        rest = [item for item in factors if item != factor]
        without = _value(v, rest)
        if whole is None or without is None:
            deltas[factor] = {"status": "missing", "value": None}
        else:
            deltas[factor] = {
                "status": "computed",
                "value": whole - without,
                "not_independent_cause": True,
            }
    report["deltas"] = deltas
    report["definition"] = "delta_i = v(N) - v(N without i)"
    return report


def interaction(v: dict[str, Any], factors: list[str], left: str, right: str, context: list[str] | None = None) -> dict[str, Any]:
    """Iᵢⱼ(T) = v(T∪{i,j}) − v(T∪{i}) − v(T∪{j}) + v(T), for this context only."""
    report = _base(v, factors)
    context = list(context or [])
    needed = {
        "both": context + [left, right],
        "left": context + [left],
        "right": context + [right],
        "context": context,
    }
    values = {name: _value(v, items) for name, items in needed.items()}
    report["context"] = context
    report["pair"] = [left, right]
    report["definition"] = "I = v(T+i+j) - v(T+i) - v(T+j) + v(T)"
    report["scope"] = "this context only"
    if any(value is None for value in values.values()):
        report["status"] = "missing"
        report["value"] = None
        report["observed"] = {name: values[name] for name in values}
        return report
    report["status"] = "computed"
    report["value"] = values["both"] - values["left"] - values["right"] + values["context"]
    return report


def exact_shapley(
    v: dict[str, Any],
    factors: list[str],
    *,
    excluded_factors: list[str] | None = None,
    constrained_explanation: str | None = None,
) -> dict[str, Any]:
    """Small exact Shapley. Any missing coalition makes the result uncertain."""
    report = _base(v, factors)
    names = list(factors)
    if len(names) > 8:
        raise RrlError("E_SHAPLEY_TOO_LARGE", "exact Shapley is limited to 8 factors; pass a sampler budget explicitly")
    excluded = list(excluded_factors or [])
    constrained = bool(excluded or constrained_explanation)
    if constrained and not (isinstance(constrained_explanation, str) and constrained_explanation.strip()):
        return {
            **report,
            "status": "uncertain",
            "values": None,
            "reason": "constrained value function requires an explanation of how it differs",
            "constrained_value_function": False,
        }
    missing: list[str] = []
    for size in range(len(names) + 1):
        for combo in combinations(names, size):
            if _value(v, combo) is None:
                missing.append(coalition_key(combo))
    report["constrained_value_function"] = constrained
    report["same_as_unconstrained_shapley"] = not constrained
    report["excluded_factors"] = excluded
    report["constrained_explanation"] = constrained_explanation
    report["sample_count"] = None
    report["seed"] = None
    if missing:
        report["status"] = "uncertain"
        report["values"] = None
        report["missing_coalitions"] = missing
        report["reason"] = "missing coalition is not treated as zero"
        return report
    n = len(names)
    factorial = math.factorial
    values = {factor: 0.0 for factor in names}
    for factor in names:
        others = [item for item in names if item != factor]
        total = 0.0
        for size in range(len(others) + 1):
            for combo in combinations(others, size):
                weight = factorial(size) * factorial(n - size - 1) / factorial(n)
                with_factor = _value(v, list(combo) + [factor])
                without = _value(v, combo)
                assert with_factor is not None and without is not None
                total += weight * (with_factor - without)
        values[factor] = total
    report["status"] = "computed"
    report["values"] = values
    report["missing_coalitions"] = []
    report["estimator"] = "exact"
    return report


def sample_shapley(
    v: dict[str, Any],
    factors: list[str],
    *,
    sample_count: int,
    seed: int,
) -> dict[str, Any]:
    """Permutation-sample Shapley. Stops uncertain if a sampled coalition is missing."""
    report = _base(v, factors)
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 1:
        raise RrlError("E_SAMPLE_COUNT", "sample_count must be a positive integer")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise RrlError("E_SEED", "seed must be an integer")
    rng = random.Random(seed)
    names = list(factors)
    sums = {factor: 0.0 for factor in names}
    squares = {factor: 0.0 for factor in names}
    completed = 0
    for _ in range(sample_count):
        order = names[:]
        rng.shuffle(order)
        prefix: list[str] = []
        for factor in order:
            without = _value(v, prefix)
            with_factor = _value(v, prefix + [factor])
            if without is None or with_factor is None:
                report.update(
                    {
                        "status": "uncertain",
                        "values": None,
                        "reason": "sampled coalition is missing and was not treated as zero",
                        "seed": seed,
                        "sample_count_requested": sample_count,
                        "sample_count_completed": completed,
                        "stopping_condition": "missing coalition",
                        "estimator": "permutation_sample",
                    }
                )
                return report
            marginal = with_factor - without
            sums[factor] += marginal
            squares[factor] += marginal * marginal
            prefix.append(factor)
        completed += 1
    means = {factor: sums[factor] / completed for factor in names}
    errors = {}
    for factor in names:
        mean = means[factor]
        variance = max(0.0, squares[factor] / completed - mean * mean)
        errors[factor] = math.sqrt(variance / completed)
    report.update(
        {
            "status": "computed",
            "values": means,
            "standard_error": errors,
            "seed": seed,
            "sample_count_requested": sample_count,
            "sample_count_completed": completed,
            "stopping_condition": "sample_count reached",
            "estimator": "permutation_sample",
            "missing_coalitions": [],
        }
    )
    return report
