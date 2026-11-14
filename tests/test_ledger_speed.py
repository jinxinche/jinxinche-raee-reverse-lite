"""Regression for claim reevaluation cost.

The old lookup reread every relation on each insert. A support batch then
slowed by more than an order of magnitude between the first and last hundred.
These tests keep the decision rules and reject that collapse.
"""

import time

from tests.helpers import SCOPE, add_claim, add_observation, support


def _claim(store, index: int) -> str:
    return store.add_record(
        kind="claim",
        payload={"statement": f"speed claim {index}", "required_scope": dict(SCOPE)},
        provenance="observed",
        execution_result="not_executed",
        applicability="valid",
        usage="background",
        verification_scope=dict(SCOPE),
    )


def _observation(store, index: int) -> str:
    return store.add_record(
        kind="observation",
        payload={
            "summary": f"speed obs {index}",
            "truncated": False,
            "run": {"command": ["checksum_cli"], "exit_code": 0, "observed_status": "passed"},
        },
        provenance="observed",
        execution_result="passed",
        applicability="valid",
        usage="support",
        verification_scope=dict(SCOPE),
        source_family=f"speed-obs-{index}",
    )


def test_support_batch_does_not_collapse(store):
    claims = [_claim(store, index) for index in range(100)]
    observations = [_observation(store, index) for index in range(500)]
    started = time.perf_counter()
    first_done = None
    last_started = None
    for index in range(2000):
        if index == 1900:
            last_started = time.perf_counter()
        store.add_relation(
            "supports",
            observations[index % 500],
            claims[index % 100],
            {"statement": "speed support", "method": "explicit"},
        )
        if index == 99:
            first_done = time.perf_counter()
    finished = time.perf_counter()
    assert first_done is not None and last_started is not None
    first = first_done - started
    last = finished - last_started
    # On this shape, before the fix, the last hundred was about 18x the first
    # hundred. After the fix the same comparison was about 3x.
    assert last < first * 6
    assert store.decision(claims[0])["accepted_pass"] is True
    assert store.get(claims[0])["projection"]["extra"]["accepted_pass"] is True


def test_derived_from_does_not_rewrite_unrelated_evaluations(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="kept")
    support(store, evidence, claim)
    before = store.get(claim)["projection"]["extra"]["latest_evaluation_id"]
    left = add_observation(store, family="left")
    right = add_observation(store, family="right")
    for index in range(50):
        store.add_relation(
            "derived_from",
            left if index % 2 == 0 else right,
            right if index % 2 == 0 else left,
            {"statement": "unrelated derivation", "method": "explicit"},
        )
    after = store.get(claim)["projection"]["extra"]["latest_evaluation_id"]
    assert after == before
    assert store.decision(claim)["accepted_pass"] is True


def test_dependent_claim_still_follows_a_retracted_support(store):
    left = add_observation(store, family="left")
    right = add_observation(store, family="right")
    claim_a = add_claim(store, statement="A")
    claim_b = add_claim(store, statement="B")
    support(store, left, claim_a)
    support(store, right, claim_b)
    store.add_relation(
        "depends_on",
        claim_b,
        claim_a,
        {"statement": "B needs A", "method": "explicit"},
        role="necessary",
    )
    assert store.decision(claim_b)["accepted_pass"] is True
    store.retract(left, "A's only support")
    assert store.decision(claim_a)["accepted_pass"] is False
    assert store.decision(claim_b)["accepted_pass"] is False
