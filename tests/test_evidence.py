import sqlite3

import pytest

from raee_reverse.errors import RrlError
from tests.helpers import REQUIRED, SCOPE, add_claim, add_observation, support


def test_normal_support_is_scoped_pass(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="run-1")
    support(store, evidence, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is True
    assert decision["execution_result"] == "passed"
    assert decision["independent_support_count"] == 1
    assert decision["not_universal"] is True
    assert decision["applicability"] == "valid"


def test_failed_observation_is_not_a_pass(store):
    claim = add_claim(store)
    evidence = add_observation(store, result="failed")
    support(store, evidence, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["execution_result"] == "failed"


def test_missing_evidence_is_not_executed(store):
    claim = add_claim(store)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["execution_result"] == "not_executed"
    assert decision["support_status"] == "unsupported"


def test_uncertain_does_not_become_pass(store):
    claim = add_claim(store)
    evidence = add_observation(store, result="uncertain")
    support(store, evidence, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["execution_result"] == "uncertain"


def test_truncated_output_is_not_complete(store):
    claim = add_claim(store)
    evidence = add_observation(store, result="passed", truncated=True)
    stored = store.get(evidence)
    assert stored["payload"]["truncated"] is True
    assert stored["projection"]["applicability"] == "incomplete_scope"
    assert stored["projection"]["execution_result"] != "passed"
    support(store, evidence, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert any(item["reason"] == "truncated" for item in decision["excluded"])


def test_stale_support_cannot_carry_a_pass(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="run-1")
    support(store, evidence, claim)
    assert store.decision(claim)["accepted_pass"] is True
    before = store.get(evidence)["content_digest"]
    store.mark_stale(evidence, "source changed")
    after = store.get(evidence)
    assert after["content_digest"] == before
    assert after["payload"]["dimensions_at_creation"]["applicability"] == "valid"
    assert after["projection"]["applicability"] == "stale"
    assert after["projection"]["execution_result"] == "passed"
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["execution_result"] != "passed"


def test_empty_scope_cannot_pass(store):
    claim = add_claim(store, scope={"inputs": [], "behaviors": [], "environments": []})
    evidence = add_observation(store)
    support(store, evidence, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["applicability"] == "incomplete_scope"


def test_name_similarity_is_rejected(store):
    claim = add_claim(store, statement="login works")
    other = add_claim(store, statement="login work")
    with pytest.raises(RrlError) as raised:
        store.add_relation(
            "verifies",
            other,
            claim,
            {"statement": "the names look similar", "method": "name_similarity"},
        )
    assert raised.value.code == "E_SIMILARITY_NOT_COVERAGE"
    assert store.list_relations() == []


def test_same_source_copies_do_not_increase_support(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="same-run")
    copy = store.copy_same_source(evidence)
    support(store, evidence, claim)
    support(store, copy, claim)
    decision = store.decision(claim)
    assert decision["accepted_pass"] is True
    assert decision["independent_support_count"] == 1
    assert sorted(decision["positive_support_ids"]) == sorted([evidence, copy])


def test_distinct_sources_increase_support(store):
    claim = add_claim(store)
    first = add_observation(store, family="run-a")
    second = add_observation(store, family="run-b")
    support(store, first, claim)
    support(store, second, claim)
    assert store.decision(claim)["independent_support_count"] == 2


def test_model_text_cannot_be_an_execution_pass(store):
    with pytest.raises(RrlError) as raised:
        store.add_record(
            kind="hypothesis",
            payload={"statement": "maybe crc32"},
            provenance="model_generated",
            execution_result="passed",
            applicability="valid",
            usage="support",
            verification_scope=dict(SCOPE),
        )
    assert raised.value.code == "E_MODEL_NOT_EXECUTION"


def test_counterevidence_blocks_only_inside_its_scope(store):
    claim = add_claim(store)
    good = add_observation(store, family="good")
    bad = add_observation(store, result="passed", usage="oppose", family="bad")
    support(store, good, claim)
    store.add_relation("contradicts", bad, claim, {"statement": "the opposing run completed", "method": "explicit"})
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["support_status"] == "contested"
    assert decision["execution_result"] == "failed"
    assert decision["failure_scope"]
    assert decision["not_universal"] is True


def test_content_change_stales_derived_observation(store):
    blob = store.put_blob(b"v1")
    artifact = store.add_record(
        kind="artifact",
        payload={"content_digest": blob, "size": 2},
        provenance="observed",
        execution_result="not_executed",
        applicability="valid",
        usage="background",
        verification_scope=dict(SCOPE),
    )
    evidence = add_observation(store, family="run")
    store.add_relation("derived_from", evidence, artifact, {"statement": "observation of this artifact", "method": "explicit"})
    claim = add_claim(store)
    support(store, evidence, claim)
    assert store.decision(claim)["accepted_pass"] is True
    changed = store.note_content_change(artifact, b"v2")
    assert changed["changed"] is True
    assert store.get(artifact)["payload"]["content_digest"] == blob
    assert store.get(artifact)["projection"]["applicability"] == "stale"
    assert store.get(evidence)["projection"]["applicability"] == "stale"
    assert store.decision(claim)["accepted_pass"] is False
    same = store.note_content_change(artifact, b"v1")
    assert same["changed"] is False


def test_records_are_immutable_and_crash_before_commit_is_absent(store, tmp_path):
    evidence = add_observation(store)
    with pytest.raises(sqlite3.DatabaseError):
        store.connection.execute("UPDATE records SET kind='mutated' WHERE id=?", (evidence,))
    with pytest.raises(sqlite3.DatabaseError):
        store.connection.execute("DELETE FROM records WHERE id=?", (evidence,))
    assert store.get(evidence)["kind"] == "observation"
    store.failpoint = "before_commit"
    with pytest.raises(RrlError) as raised:
        add_observation(store, family="should-not-land")
    assert raised.value.code == "E_INJECTED_CRASH"
    assert all(item["projection"]["source_family"] != "should-not-land" for item in store.list_records())
    reopened = type(store)(store.root)
    try:
        assert all(item["projection"]["source_family"] != "should-not-land" for item in reopened.list_records())
        reopened.verify_integrity()
    finally:
        reopened.close()


def test_inconsistent_pass_is_rejected(store):
    with pytest.raises(RrlError) as raised:
        store.add_record(
            kind="observation",
            payload={"summary": "bad", "truncated": False, "run": {"command": ["x"], "exit_code": 1, "observed_status": "passed"}},
            provenance="observed",
            execution_result="passed",
            applicability="valid",
            usage="support",
            verification_scope=dict(SCOPE),
        )
    assert raised.value.code == "E_INCONSISTENT_RUN"


def test_required_scope_constant_used():
    assert REQUIRED["require_complete_output"] is True
