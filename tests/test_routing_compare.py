"""Harness accounting. These runs are not the live five-policy comparison."""

import json

from raee_reverse.routing_compare import (
    POLICIES,
    availability_record,
    measured_cost_ratio,
    run_policy,
)


def _profile(tier, **overrides):
    item = {
        "id": f"profile-{tier}",
        "tier": tier,
        "provider": "local",
        "model": f"model-{tier}",
        "available": True,
        "price_status": "known",
        "price": {"input_per_million": "1.00", "output_per_million": "2.00"},
        "intended_capabilities": ["explain", "conflict", "locate", "structure", "local_explain", "call_graph"],
        "deployment": "local",
        "data_egress": "none",
    }
    item.update(overrides)
    return item


def _task(**overrides):
    item = {
        "task_id": "locate-1",
        "task_type": "locate",
        "statement": "name the modulus",
        "prompt": "name the modulus",
        "signals": {
            "architecture_known": True,
            "symbols_available": True,
            "scope_located": True,
            "indirect_or_cross_module": False,
            "evidence_complete": True,
            "evidence_conflict": False,
            "multistep_state": False,
            "verification_available": True,
            "target_calibrated": True,
        },
        "error_cost": {
            "retrieval_only": True,
            "affects_contract": False,
            "generates_implementation": False,
            "pollutes_downstream": False,
            "decides_acceptance": False,
            "level": "low",
        },
        "needs": ["locate"],
        "deterministic_possible": False,
        "evidence_present": True,
        "evidence_required": True,
        "tool_available": True,
        "reasoning_required": True,
        "mode": "balanced",
        "counterexamples": ["boundary"],
        "max_attempts": 3,
        "max_upgrades": 1,
        "oracle": lambda answer: answer == "65521",
        "context": {
            "requirements": ["r"],
            "evidence_refs": ["sha256:abc"],
            "hypotheses": ["maybe"],
            "counterexamples": ["empty"],
            "environment_limits": ["no namespace"],
            "open_issues": ["none"],
            "acceptance": ["match"],
            "summary": "modulus",
        },
    }
    item.update(overrides)
    return item


class Scripted:
    live = False

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def call(self, *, profile, prompt, task_id):
        self.prompts.append(prompt)
        text, tokens, extra = self.answers.pop(0)
        return {
            "text": text,
            "input_tokens": tokens[0],
            "output_tokens": tokens[1],
            "other_billed_tokens": tokens[2],
            "latency_seconds": 0.01,
            "cancelled": extra.get("cancelled", False),
            **extra,
        }


def test_high_tier_wrong_answer_is_not_ground_truth():
    transport = Scripted([
        (json.dumps({"answer": "1", "evidence_refs": ["obs-1"]}), (10, 4, 0), {}),
    ])
    report = run_policy("fixed_high_tier", [_task()], [_profile("T3"), _profile("T1")], transport)
    assert report["counts_as_project_comparison"] is False
    assert report["high_tier_answers_are_ground_truth"] is False
    assert report["correct_completion_rate"] == 0.0
    assert report["savings_percent"] is None
    assert report["rows"][0]["calls"][0]["tier"] == "T3"


def test_cancelled_call_stays_on_the_ledger_and_missing_price_is_unknown():
    transport = Scripted([
        ("", (None, None, None), {"cancelled": True, "error": None}),
    ])
    profiles = [_profile("T1", price_status="unknown", price=None)]
    report = run_policy("fixed_economy", [_task()], profiles, transport)
    assert report["cancelled_calls"] == 1
    assert report["input_tokens"] is None
    assert report["total_cost"]["status"] == "unknown"
    assert report["total_cost"]["amount"] is None
    assert report["cost_per_success"] is None
    assert report["rows"][0]["finished"] is False


def test_upgrade_after_failure_is_counted_and_a_needless_upgrade_is_separate():
    fail_then_ok = Scripted([
        (json.dumps({"answer": "nope", "evidence_refs": ["obs-1"]}), (8, 2, 0), {}),
        (json.dumps({"answer": "65521", "evidence_refs": ["obs-2"]}), (9, 3, 1), {}),
    ])
    profiles = [
        _profile("T1"),
        _profile("T3", price={"input_per_million": "3", "output_per_million": "4", "other_per_million": "1"}),
    ]
    hard = _task(clearly_hard=True, task_type="conflict", needs=["conflict"])
    failed = run_policy("fixed_economy", [hard], profiles, fail_then_ok)
    assert failed["rows"][0]["upgraded"] is True
    assert failed["rows"][0]["upgrade_succeeded"] is True
    assert failed["rows"][0]["correct"] is True
    assert failed["input_tokens"] == 17
    assert failed["other_billed_tokens"] == 1
    assert len(failed["rows"][0]["calls"]) == 2
    assert failed["total_cost"]["status"] == "known"

    needless = Scripted([
        (json.dumps({"answer": "65521", "evidence_refs": ["obs-1"]}), (4, 1, 0), {}),
        (json.dumps({"answer": "65521", "evidence_refs": ["obs-1"]}), (4, 1, 0), {}),
    ])
    extra = run_policy(
        "fixed_economy",
        [_task(upgrade_even_if_correct=True)],
        [_profile("T1"), _profile("T2")],
        needless,
    )
    assert extra["unnecessary_upgrade_rate"] == 1.0
    assert extra["rows"][0]["wrong_downgrade"] is False


def test_context_policy_sends_the_compressed_bundle_and_refuses_a_conflict():
    transport = Scripted([
        (json.dumps({"answer": "65521", "evidence_refs": []}), (3, 1, 0), {}),
    ])
    profiles = [_profile("T2", id="profile-T2")]
    easy = _task(needs=["locate"], mode="balanced")
    # The router may pick T1 when both exist. Offer only T2 so the call happens.
    report = run_policy("auto_routing_plus_context_optimization", [easy], profiles, transport)
    assert report["rows"][0]["conclusion"] is True
    assert report["unsupported_conclusion_rate"] == 1.0
    assert "environment_limits" in transport.prompts[0]
    conflict = _task(context={
        "requirements": ["r"],
        "evidence_refs": ["sha256:abc"],
        "hypotheses": ["maybe"],
        "counterexamples": ["empty"],
        "environment_limits": ["no namespace"],
        "open_issues": ["none"],
        "acceptance": ["match"],
        "summary_conflicts_with_evidence": True,
    })
    refused = run_policy("auto_routing_plus_context_optimization", [conflict], profiles, Scripted([]))
    assert refused["rows"][0]["finished"] is False
    assert refused["unfinished_rate"] == 1.0


def test_missing_other_token_price_keeps_cost_unknown_and_ratio_is_not_a_savings_target():
    transport = Scripted([
        (json.dumps({"answer": "65521", "evidence_refs": ["e"]}), (10, 2, 5), {}),
    ])
    report = run_policy("fixed_high_tier", [_task()], [_profile("T3")], transport)
    assert report["total_cost"]["status"] == "unknown"
    other = run_policy(
        "fixed_economy",
        [_task()],
        [_profile("T1", price={"input_per_million": "1", "output_per_million": "1", "other_per_million": "0"})],
        Scripted([(json.dumps({"answer": "65521", "evidence_refs": ["e"]}), (10, 2, 0), {})]),
    )
    assert measured_cost_ratio(report, other) is None
    assert other["savings_percent"] is None


def test_availability_record_stays_unexecuted_without_inventing_a_price():
    record = availability_record(
        [{"id": "t1-unverified", "tier": "T1", "available": False, "price_status": "unknown"}],
        {"observed_at": None, "prices": {}},
        {},
        {11434: False, 1234: False, 8080: False},
    )
    assert record["executed"] is False
    assert record["savings_percent"] is None
    assert record["metrics"]["total_cost"] == "not_collected"
    assert "no model profile has available=true" in record["missing_conditions"]
    assert set(POLICIES) == set(record["policies"])
