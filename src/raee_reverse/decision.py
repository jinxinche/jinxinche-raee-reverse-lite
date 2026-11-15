"""Rule router for difficulty, model tier, context, and cost.

This is not a resident agent and it does not call a model. A stronger tier is
not evidence. Missing prices stay unknown. Savings are not estimated in advance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raee_reverse.budget_ledger import BudgetDenied, BudgetLedger

TIERS = ("T0", "T1", "T2", "T3")
MODES = ("economy", "balanced", "quality")
DIFFICULTY_KEYS = (
    "architecture_known",
    "symbols_available",
    "scope_located",
    "indirect_or_cross_module",
    "evidence_complete",
    "evidence_conflict",
    "multistep_state",
    "verification_available",
    "target_calibrated",
)
COST_KEYS = (
    "retrieval_only",
    "affects_contract",
    "generates_implementation",
    "pollutes_downstream",
    "decides_acceptance",
)
CONTEXT_KEYS = (
    "requirements",
    "evidence_refs",
    "hypotheses",
    "counterexamples",
    "environment_limits",
    "open_issues",
    "acceptance",
)
_MODE_TIER = {"economy": "T1", "balanced": "T2", "quality": "T3"}


def load_profiles(profile_path: str | Path, price_path: str | Path) -> list[dict[str, Any]]:
    profiles = json.loads(Path(profile_path).read_text(encoding="utf-8"))["profiles"]
    prices = json.loads(Path(price_path).read_text(encoding="utf-8"))
    table = prices.get("prices") or {}
    observed_at = prices.get("observed_at")
    loaded = []
    for profile in profiles:
        item = dict(profile)
        price_id = item.get("price_id")
        entry = table.get(price_id) if price_id else None
        if not isinstance(entry, dict) or "input_per_million" not in entry or "output_per_million" not in entry:
            item["price_status"] = "unknown"
            item["price"] = None
        else:
            item["price_status"] = "known"
            item["price"] = {
                "input_per_million": str(entry["input_per_million"]),
                "output_per_million": str(entry["output_per_million"]),
                "observed_at": observed_at,
            }
        item["capability_verified"] = bool(item.get("calibrated")) and bool(item.get("verified_capabilities"))
        loaded.append(item)
    return loaded


def assess(task: dict[str, Any]) -> dict[str, Any]:
    signals = task.get("signals") if isinstance(task.get("signals"), dict) else {}
    costs = task.get("error_cost") if isinstance(task.get("error_cost"), dict) else {}
    missing = [key for key in DIFFICULTY_KEYS if key not in signals]
    difficulty: dict[str, Any] = {
        "status": "unknown" if missing else "known",
        "missing_basis": missing,
        "factors": {key: signals.get(key) for key in DIFFICULTY_KEYS},
        "auxiliary": {
            "file_bytes": signals.get("file_bytes"),
            "context_tokens": signals.get("context_tokens"),
        },
        "success_probability": None,
    }
    if not missing:
        hard = bool(
            signals["indirect_or_cross_module"]
            or signals["evidence_conflict"]
            or signals["multistep_state"]
            or not signals["target_calibrated"]
            or not signals["verification_available"]
        )
        easy = bool(
            signals["architecture_known"]
            and signals["symbols_available"]
            and signals["scope_located"]
            and signals["evidence_complete"]
            and signals["verification_available"]
            and signals["target_calibrated"]
            and not signals["indirect_or_cross_module"]
            and not signals["evidence_conflict"]
            and not signals["multistep_state"]
        )
        difficulty["level"] = "hard" if hard else "easy" if easy else "moderate"
    else:
        difficulty["level"] = None
    cost_missing = [key for key in COST_KEYS if key not in costs]
    high = any(bool(costs.get(key)) for key in COST_KEYS if key != "retrieval_only")
    error_cost = {
        "status": "unknown" if cost_missing else "known",
        "missing_basis": cost_missing,
        "factors": {key: costs.get(key) for key in COST_KEYS},
        "level": None if cost_missing else "high" if high else "low",
    }
    return {"difficulty": difficulty, "error_cost": error_cost}


def classify_gap(task: dict[str, Any]) -> str:
    if task.get("evidence_required") and not task.get("evidence_present"):
        return "evidence"
    if task.get("tool_required") and not task.get("tool_available"):
        return "tool"
    if task.get("reasoning_required") and not task.get("deterministic_possible"):
        return "reasoning"
    return "none"


def route(task: dict[str, Any], profiles: list[dict[str, Any]], budget: BudgetLedger | None = None) -> dict[str, Any]:
    """Choose the next action. Does not lower a quality gate to save money."""
    assessment = assess(task)
    gap = classify_gap(task)
    mode = task.get("mode") or "balanced"
    if mode not in MODES:
        mode = "balanced"
    reusable = task.get("reusable") if isinstance(task.get("reusable"), dict) else None
    plan: dict[str, Any] = {
        "task_id": task.get("task_id"),
        "difficulty": assessment["difficulty"],
        "error_cost": assessment["error_cost"],
        "gap": gap,
        "mode": mode,
        "verification_required": True,
        "quality_gate_lowered": False,
        "savings_percent": None,
        "success_probability": None,
        "capability_verified": False,
        "roles": {
            "intent": task.get("statement"),
            "change": None,
            "verification": "independent check required; model output is not ground truth",
            "environment": {
                "allowed_providers": task.get("allowed_providers"),
                "local_only": bool(task.get("local_only")),
                "fixed_model": task.get("fixed_model"),
            },
            "boundary": "restricted material stays on allowed providers",
        },
    }
    if reusable and reusable.get("applicable") and not reusable.get("expired") and not reusable.get("retracted"):
        plan.update(action="reuse", tier="T0", profile_id="t0-local", model=None, reason="unexpired reusable result")
        plan["expected_cost_status"] = "known"
        plan["expected_cost"] = "0.00"
        return _finish(plan, task, budget, reserve=False)
    if task.get("deterministic_possible") and gap == "none":
        plan.update(action="deterministic_tool", tier="T0", profile_id="t0-local", model=None, reason="deterministic tool covers the task")
        plan["expected_cost_status"] = "known"
        plan["expected_cost"] = "0.00"
        plan["capability_verified"] = True
        return _finish(plan, task, budget, reserve=False)
    if gap == "evidence":
        plan.update(
            action="collect_evidence",
            tier="T0",
            profile_id=None,
            model=None,
            reason="necessary evidence was never collected; a stronger model does not supply it",
            upgrade_model=False,
        )
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    if gap == "tool":
        plan.update(action="request_tool", tier="T0", profile_id=None, model=None, reason="missing tool capability")
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    if _capped(task):
        plan.update(action="stop_unresolved", tier=None, profile_id=None, model=None, reason="attempt or upgrade cap reached")
        plan["open_items"] = [task.get("task_id")]
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    if task.get("upgrade") and not task.get("upgrade_new_information") and not task.get("failure_reason"):
        plan.update(action="stop_unresolved", tier=None, profile_id=None, model=None, reason="upgrade needs new information or a precise failure reason")
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    eligible = _eligible(task, profiles)
    if not eligible:
        plan.update(action="stop_unresolved", tier=None, profile_id=None, model=None, reason="no allowed model has the needed capability")
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    chosen = _choose(task, assessment, eligible, mode)
    if chosen is None:
        plan.update(action="stop_unresolved", tier=None, profile_id=None, model=None, reason="no tier satisfies the quality constraint without lowering the gate")
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        return _finish(plan, task, budget, reserve=False)
    plan.update(
        action="call_model" if chosen["tier"] != "T0" else "deterministic_tool",
        tier=chosen["tier"],
        profile_id=chosen["id"],
        model=chosen.get("model"),
        provider=chosen.get("provider"),
        reason=_choice_reason(task, assessment, chosen, mode),
        capability_verified=bool(chosen.get("capability_verified")),
        verified_capabilities=list(chosen.get("verified_capabilities") or []),
        intended_capabilities=list(chosen.get("intended_capabilities") or []),
    )
    if chosen.get("price_status") != "known":
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
    else:
        # Expected cost includes one likely upgrade slot, not only the first request.
        # Without a calibrated upgrade rate the upgrade component stays unknown.
        plan["expected_cost_status"] = "unknown"
        plan["expected_cost"] = None
        plan["first_request_price"] = chosen.get("price")
        plan["rework_included"] = False
    plan["upgrade_conditions"] = [
        "output breaks the required data contract",
        "a key conclusion has no located evidence",
        "a counterexample conflicts with the explanation",
        "repeated attempts do not separate the main hypotheses",
    ]
    plan["stop_conditions"] = ["attempt cap", "upgrade cap", "budget denial", "evidence gap"]
    plan["handover_must_include"] = list(CONTEXT_KEYS)
    if task.get("upgrade") and not task.get("counterexamples"):
        plan.update(action="stop_unresolved", reason="model switch is missing counterexamples")
        plan["tier"] = None
        plan["profile_id"] = None
        plan["model"] = None
        return _finish(plan, task, budget, reserve=False)
    return _finish(plan, task, budget, reserve=plan["action"] == "call_model")


def compress_context(bundle: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in CONTEXT_KEYS if key not in bundle]
    if missing:
        return {"ok": False, "reason": "required context missing", "missing": missing, "usable_as_facts": False}
    kept = {key: bundle[key] for key in CONTEXT_KEYS}
    conflict = bool(bundle.get("summary_conflicts_with_evidence"))
    return {
        "ok": not conflict,
        "action": "return_to_raw" if conflict else "compressed",
        "usable_as_facts": False,
        "hypotheses_are_facts": False,
        "kept": kept,
        "summary": None if conflict else bundle.get("summary"),
        "reason": "summary conflicts with raw evidence" if conflict else "required material kept",
    }


def record_decision(store: Any, plan: dict[str, Any]) -> str:
    return store.add_record(
        kind="experiment",
        payload={"route": plan, "not_a_pass": True},
        provenance="observed",
        execution_result="not_executed",
        applicability="valid",
        usage="background",
        verification_scope={
            "inputs": [str(plan.get("task_id"))],
            "behaviors": ["route"],
            "environments": ["local-ledger"],
            "complete_output": True,
        },
        source_family=f"route:{plan.get('task_id')}",
    )


def classify_failure(kind: str) -> dict[str, Any]:
    infrastructure = kind in {"rate_limit", "timeout", "service", "network"}
    return {
        "kind": kind,
        "class": "infrastructure" if infrastructure else kind,
        "counts_as_reasoning_failure": not infrastructure,
    }


def comparison_record() -> dict[str, Any]:
    """The five routing policies were not executed. No savings number is invented."""
    policies = [
        "fixed_high_tier",
        "fixed_economy",
        "fixed_by_task_type",
        "auto_difficulty_routing",
        "auto_routing_plus_context_optimization",
    ]
    metrics = [
        "correct_completion_rate",
        "unsupported_conclusion_rate",
        "coverage",
        "unfinished_rate",
        "total_cost",
        "input_tokens",
        "output_tokens",
        "other_billed_tokens",
        "cost_per_success",
        "latency_distribution",
        "routing_overhead",
        "upgrade_rate",
        "upgrade_success_rate",
        "wrong_downgrade_rate",
        "unnecessary_upgrade_rate",
    ]
    return {
        "executed": False,
        "reason": "No configured profile has an available endpoint and a known price. The shipped prices file is empty.",
        "policies": policies,
        "metrics": {metric: "not_collected" for metric in metrics},
        "savings_percent": None,
        "high_tier_answers_are_ground_truth": False,
    }


def _finish(plan: dict[str, Any], task: dict[str, Any], budget: BudgetLedger | None, *, reserve: bool) -> dict[str, Any]:
    plan["reservation"] = None
    if reserve and budget is not None:
        generation = None
        try:
            generation = budget.reserve(
                unit_id=str(task.get("task_id") or "task"),
                kind="generation",
                calls=1,
                tier=plan.get("tier"),
                price_status="unknown",
                price_amount=None,
            )
            review = budget.reserve(
                unit_id=str(task.get("task_id") or "task") + ":review",
                kind="review",
                calls=1,
                tier="T0",
                price_status="known",
                price_amount="0.00",
            )
            plan["reservation"] = {"generation": generation["id"], "review": review["id"]}
        except BudgetDenied as exc:
            if generation is not None and generation.get("billing") == "not_issued":
                budget.release(generation["id"])
            plan["action"] = "stop_unresolved"
            plan["reason"] = f"budget denied: {exc.reason}"
            plan["reservation"] = None
            plan["quality_gate_lowered"] = False
    return plan


def _capped(task: dict[str, Any]) -> bool:
    attempts = int(task.get("attempts_used") or 0)
    upgrades = int(task.get("upgrades_used") or 0)
    return attempts >= int(task.get("max_attempts") or 3) or upgrades >= int(task.get("max_upgrades") or 2)


def _eligible(task: dict[str, Any], profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needed = set(task.get("needs") or [])
    allowed = task.get("allowed_providers")
    local_only = bool(task.get("local_only"))
    fixed = task.get("fixed_model")
    restricted = bool(task.get("restricted_material"))
    chosen = []
    for profile in profiles:
        if profile.get("tier") == "T0":
            continue
        if not profile.get("available", True):
            continue
        if fixed and profile.get("id") != fixed and profile.get("model") != fixed:
            continue
        if allowed is not None and profile.get("provider") not in allowed:
            continue
        if local_only and profile.get("deployment") != "local":
            continue
        if restricted and profile.get("data_egress") not in (None, "none", "local"):
            continue
        intended = set(profile.get("intended_capabilities") or [])
        if needed and not needed <= intended:
            continue
        chosen.append(profile)
    return chosen


def _choose(task: dict[str, Any], assessment: dict[str, Any], eligible: list[dict[str, Any]], mode: str) -> dict[str, Any] | None:
    hard = assessment["difficulty"].get("level") == "hard" or bool(task.get("clearly_hard"))
    high = assessment["error_cost"].get("level") == "high" or bool(task.get("high_stakes"))
    if hard or high:
        top = [item for item in eligible if item["tier"] == "T3"]
        if top:
            return top[0]
        # Do not pretend a weaker model meets the high-stakes gate.
        if high and hard:
            return None
    preferred = _MODE_TIER[mode]
    ordered = sorted(eligible, key=lambda item: (_tier_distance(item["tier"], preferred), TIERS.index(item["tier"])))
    return ordered[0] if ordered else None


def _tier_distance(tier: str, preferred: str) -> int:
    return abs(TIERS.index(tier) - TIERS.index(preferred))


def _choice_reason(task: dict[str, Any], assessment: dict[str, Any], chosen: dict[str, Any], mode: str) -> str:
    if assessment["difficulty"].get("level") == "hard" or task.get("clearly_hard") or assessment["error_cost"].get("level") == "high":
        return "hard or high-stakes task entered the highest available eligible tier directly"
    return f"mode {mode} preference among allowed profiles; verification is still required"
