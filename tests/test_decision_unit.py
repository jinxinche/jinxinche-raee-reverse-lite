"""Rule router, budget reservations, and the cases that must not become a pass."""

import threading

from raee_reverse.budget_ledger import BudgetDenied, BudgetLedger
from raee_reverse.decision import (
    assess,
    classify_failure,
    comparison_record,
    compress_context,
    load_profiles,
    record_decision,
    route,
)


def _profile(tier, **overrides):
    item = {
        "id": f"profile-{tier}",
        "tier": tier,
        "provider": "local",
        "model": f"model-{tier}",
        "deployment": "local",
        "data_egress": "none",
        "available": True,
        "calibrated": False,
        "verified_capabilities": [],
        "intended_capabilities": ["explain", "conflict", "locate", "structure", "local_explain", "call_graph"],
        "price_status": "unknown",
        "price": None,
        "capability_verified": False,
    }
    item.update(overrides)
    return item


def _signals(**overrides):
    base = {
        "architecture_known": True,
        "symbols_available": True,
        "scope_located": True,
        "indirect_or_cross_module": False,
        "evidence_complete": True,
        "evidence_conflict": False,
        "multistep_state": False,
        "verification_available": True,
        "target_calibrated": True,
    }
    base.update(overrides)
    return base


def _cost(**overrides):
    base = {
        "retrieval_only": True,
        "affects_contract": False,
        "generates_implementation": False,
        "pollutes_downstream": False,
        "decides_acceptance": False,
    }
    base.update(overrides)
    return base


def _task(**overrides):
    item = {
        "task_id": "task-1",
        "statement": "explain one located function",
        "signals": _signals(),
        "error_cost": _cost(),
        "needs": ["explain"],
        "deterministic_possible": False,
        "evidence_present": True,
        "evidence_required": True,
        "tool_available": True,
        "tool_required": False,
        "reasoning_required": True,
        "mode": "balanced",
        "counterexamples": ["boundary input"],
        "max_attempts": 3,
        "max_upgrades": 2,
    }
    item.update(overrides)
    return item


def test_missing_basis_is_unknown_difficulty_without_a_probability():
    found = assess(_task(signals={"file_bytes": 12}))
    assert found["difficulty"]["status"] == "unknown"
    assert found["difficulty"]["level"] is None
    assert found["difficulty"]["success_probability"] is None


def test_file_size_does_not_set_difficulty():
    large_easy = assess(_task(signals=_signals(file_bytes=10_000_000)))
    short_hard = assess(_task(signals=_signals(file_bytes=20, evidence_conflict=True)))
    assert large_easy["difficulty"]["level"] == "easy"
    assert short_hard["difficulty"]["level"] == "hard"
    assert large_easy["error_cost"]["level"] == "low"


def test_simple_task_stays_on_t0_without_a_model():
    plan = route(_task(deterministic_possible=True, reasoning_required=False), [_profile("T3")])
    assert plan["action"] == "deterministic_tool"
    assert plan["tier"] == "T0"
    assert plan["model"] is None
    assert plan["verification_required"] is True


def test_reusable_unexpired_result_is_reused():
    plan = route(
        _task(reusable={"applicable": True, "expired": False, "retracted": False}),
        [_profile("T3")],
    )
    assert plan["action"] == "reuse"
    expired = route(
        _task(reusable={"applicable": True, "expired": True, "retracted": False}, deterministic_possible=True, reasoning_required=False),
        [_profile("T3")],
    )
    assert expired["action"] != "reuse"


def test_hard_high_stakes_task_may_enter_t3_directly():
    profiles = [_profile("T1"), _profile("T3")]
    plan = route(
        _task(
            clearly_hard=True,
            high_stakes=True,
            signals=_signals(evidence_conflict=True, multistep_state=True),
            error_cost=_cost(decides_acceptance=True, retrieval_only=False),
        ),
        profiles,
    )
    assert plan["tier"] == "T3"
    assert plan["quality_gate_lowered"] is False
    assert "directly" in plan["reason"]


def test_missing_evidence_is_not_fixed_by_a_stronger_model():
    plan = route(_task(evidence_present=False), [_profile("T3")])
    assert plan["action"] == "collect_evidence"
    assert plan["gap"] == "evidence"
    assert plan["upgrade_model"] is False
    assert plan["model"] is None


def test_unavailable_strong_model_does_not_lower_the_gate():
    plan = route(
        _task(
            clearly_hard=True,
            high_stakes=True,
            signals=_signals(evidence_conflict=True),
            error_cost=_cost(decides_acceptance=True, retrieval_only=False),
        ),
        [_profile("T1")],
    )
    assert plan["action"] == "stop_unresolved"
    assert plan["quality_gate_lowered"] is False
    assert plan["verification_required"] is True


def test_restricted_material_is_not_sent_to_a_vendor():
    remote = _profile("T2", provider="example-vendor", deployment="remote", data_egress="vendor")
    local = _profile("T2", id="local-t2", provider="local")
    plan = route(_task(restricted_material=True, allowed_providers=["example-vendor", "local"]), [remote, local])
    assert plan["profile_id"] == "local-t2"
    blocked = route(_task(restricted_material=True, local_only=True), [remote])
    assert blocked["action"] == "stop_unresolved"


def test_fixed_model_and_provider_limits_are_honored():
    other = _profile("T2", id="other", provider="other-vendor")
    chosen = _profile("T1", id="fixed-one", provider="kept")
    plan = route(_task(fixed_model="fixed-one", allowed_providers=["kept"]), [other, chosen])
    assert plan["profile_id"] == "fixed-one"


def test_mode_changes_preference_not_verification():
    profiles = [_profile("T1"), _profile("T2"), _profile("T3")]
    economy = route(_task(mode="economy"), profiles)
    quality = route(_task(mode="quality"), profiles)
    assert economy["tier"] == "T1"
    assert quality["tier"] == "T3"
    assert economy["verification_required"] is True
    assert quality["verification_required"] is True


def test_upgrade_requires_new_information_and_counterexamples():
    profiles = [_profile("T2"), _profile("T3")]
    missing_reason = route(_task(upgrade=True, upgrades_used=0), profiles)
    assert missing_reason["action"] == "stop_unresolved"
    missing_counter = route(
        _task(upgrade=True, failure_reason="contract mismatch", counterexamples=[], upgrades_used=0),
        profiles,
    )
    assert "counterexamples" in missing_counter["reason"]
    capped = route(_task(upgrades_used=2, max_upgrades=2), profiles)
    assert capped["action"] == "stop_unresolved"
    assert capped["quality_gate_lowered"] is False


def test_infrastructure_failure_is_not_a_reasoning_failure():
    infra = classify_failure("timeout")
    reasoning = classify_failure("reasoning")
    assert infra["counts_as_reasoning_failure"] is False
    assert reasoning["counts_as_reasoning_failure"] is True
    assert classify_failure("rate_limit")["class"] == "infrastructure"


def test_unknown_price_is_not_zero_and_cancelled_calls_remain(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.configure(call_cap=4, review_reserve=1, high_tier_cap=2, money_cap=None)
    reservation = ledger.reserve(unit_id="u", kind="generation", tier="T1", price_status="unknown")
    issued = ledger.mark_issued(reservation["id"])
    assert issued["billing"] == "issued_maybe_billed"
    cancelled = ledger.cancel(reservation["id"])
    assert cancelled["billing"] == "cancelled_maybe_billed"
    assert cancelled["money_status"] == "unknown"
    assert cancelled["money_amount"] is None
    rollup = ledger.rollup()
    assert rollup["money_status"] == "unknown"
    assert rollup["money_amount"] is None
    assert rollup["call_count"] == 1
    assert rollup["savings_percent"] is None
    ledger.close()


def test_usage_fields_stay_separate_and_missing_usage_is_unknown(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    reservation = ledger.reserve(unit_id="u", kind="generation", tier="T1", price_status="unknown")
    ledger.commit_usage(reservation["id"], {"raw_input_tokens": 100, "cache_hit_tokens": 40})
    rollup = ledger.rollup()
    assert rollup["raw_input_tokens"]["value"] == 100
    assert rollup["cache_hit_tokens"]["value"] == 40
    assert rollup["billed_tokens"]["status"] == "unknown"
    assert rollup["billed_tokens"]["value"] is None
    ledger.close()


def test_concurrent_reservations_cannot_both_spend_the_last_slot(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.configure(call_cap=3, review_reserve=1, high_tier_cap=2, money_cap="1.00")
    results = []
    barrier = threading.Barrier(2)

    def attempt(name: str) -> None:
        barrier.wait()
        try:
            results.append(ledger.reserve(unit_id=name, kind="generation", tier="T1", price_status="known", price_amount="0.60"))
        except BudgetDenied as exc:
            results.append(exc)

    threads = [threading.Thread(target=attempt, args=(f"unit-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    granted = [item for item in results if isinstance(item, dict)]
    denied = [item for item in results if isinstance(item, BudgetDenied)]
    assert len(granted) == 1
    assert len(denied) == 1
    ledger.close()


def test_unknown_price_blocks_a_second_money_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    ledger.configure(call_cap=6, review_reserve=1, high_tier_cap=2, money_cap="5.00")
    ledger.reserve(unit_id="first", kind="generation", tier="T1", price_status="unknown")
    try:
        ledger.reserve(unit_id="second", kind="generation", tier="T1", price_status="known", price_amount="0.10")
        raised = False
    except BudgetDenied:
        raised = True
    assert raised is True
    ledger.close()


def test_compression_keeps_limits_and_returns_to_raw_on_conflict():
    bundle = {
        "requirements": ["r"],
        "evidence_refs": ["sha256:abc"],
        "hypotheses": ["maybe the loop exits early"],
        "counterexamples": ["empty input"],
        "environment_limits": ["no network namespace"],
        "open_issues": ["unverified"],
        "acceptance": ["roundtrip"],
        "summary": "the loop always exits",
        "summary_conflicts_with_evidence": True,
    }
    conflict = compress_context(bundle)
    assert conflict["action"] == "return_to_raw"
    assert conflict["usable_as_facts"] is False
    assert conflict["hypotheses_are_facts"] is False
    assert conflict["kept"]["environment_limits"] == ["no network namespace"]
    dropped = compress_context({"requirements": ["r"]})
    assert dropped["ok"] is False
    assert "environment_limits" in dropped["missing"]


def test_route_record_is_not_an_execution_pass(store):
    plan = route(_task(deterministic_possible=True, reasoning_required=False), [])
    record_id = record_decision(store, plan)
    stored = store.get(record_id)
    assert stored["kind"] == "experiment"
    assert stored["projection"]["execution_result"] == "not_executed"
    assert stored["payload"]["not_a_pass"] is True


def test_shipped_profiles_have_unknown_prices_and_comparison_is_not_executed():
    profiles = load_profiles("config/model_profiles.json", "config/prices.json")
    assert all(item["price_status"] == "unknown" or item["tier"] == "T0" for item in profiles)
    assert all(item["capability_verified"] is False or item["tier"] == "T0" for item in profiles)
    report = comparison_record()
    assert report["executed"] is False
    assert report["savings_percent"] is None
    assert report["metrics"]["total_cost"] == "not_collected"
    assert report["high_tier_answers_are_ground_truth"] is False


def test_full_rollup_includes_a_failed_call_and_not_only_the_success(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite")
    failed = ledger.reserve(unit_id="fail", kind="generation", tier="T1", price_status="unknown")
    ledger.cancel(failed["id"])
    succeeded = ledger.reserve(unit_id="ok", kind="generation", tier="T1", price_status="known", price_amount="0.20")
    ledger.commit_usage(succeeded["id"], {"raw_input_tokens": 10, "cache_hit_tokens": 0, "billed_tokens": 4, "output_tokens": 2})
    rollup = ledger.rollup()
    assert rollup["call_count"] == 2
    assert rollup["includes_failed_and_cancelled"] is True
    assert rollup["money_status"] == "unknown"
    ledger.close()
