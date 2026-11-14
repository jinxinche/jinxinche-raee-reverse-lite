import threading

from raee_reverse.errors import RrlError
from tests.helpers import add_claim, add_observation, support


def test_necessary_premise_retraction_downgrades_without_delete(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="only")
    support(store, evidence, claim)
    store.add_relation(
        "depends_on",
        claim,
        evidence,
        {"statement": "this run is a necessary premise", "method": "explicit"},
        role="necessary",
    )
    assert store.decision(claim)["accepted_pass"] is True
    before_ids = {item["id"] for item in store.list_records()}
    result = store.retract(evidence, "premise withdrawn")
    assert result["deleted"] is False
    after = store.list_records()
    assert before_ids < {item["id"] for item in after}
    assert evidence in before_ids
    assert any(item["kind"] == "retraction" for item in after)
    assert store.get(evidence)["kind"] == "observation"
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert decision["support_status"] == "downgraded"
    assert store.get(claim)["kind"] == "claim"


def test_alternative_support_survives_one_retraction(store):
    claim = add_claim(store)
    first = add_observation(store, family="a")
    second = add_observation(store, family="b")
    support(store, first, claim)
    support(store, second, claim)
    store.add_relation(
        "depends_on", claim, first,
        {"statement": "first filler", "method": "explicit"},
        role="necessary", premise_slot="run",
    )
    store.add_relation(
        "depends_on", claim, second,
        {"statement": "alternative filler", "method": "explicit"},
        role="alternative", premise_slot="run",
    )
    store.retract(first, "first filler withdrawn")
    decision = store.decision(claim)
    assert decision["accepted_pass"] is True
    assert second in decision["positive_support_ids"]
    assert first not in decision["positive_support_ids"]
    assert decision["independent_support_count"] == 1


def test_same_source_retraction_blocks_the_whole_family(store):
    claim = add_claim(store)
    first = add_observation(store, family="same")
    second = store.copy_same_source(first)
    support(store, first, claim)
    support(store, second, claim)
    assert store.decision(claim)["independent_support_count"] == 1
    store.retract(first, "source withdrawn")
    decision = store.decision(claim)
    assert decision["accepted_pass"] is False
    assert store.get(second)["projection"]["applicability"] == "valid"
    assert any(item["reason"] == "source_family_retracted" for item in decision["excluded"])
    other = add_observation(store, family="other")
    support(store, other, claim)
    restored = store.decision(claim)
    assert restored["accepted_pass"] is True
    assert restored["independent_support_count"] == 1
    assert restored["source_families"] == ["other"]


def test_chain_downgrades_dependents_and_keeps_records(store):
    left = add_observation(store, family="left")
    right = add_observation(store, family="right")
    claim_a = add_claim(store, statement="A")
    claim_b = add_claim(store, statement="B")
    support(store, left, claim_a)
    support(store, right, claim_b)
    store.add_relation(
        "depends_on", claim_b, claim_a,
        {"statement": "B needs A", "method": "explicit"},
        role="necessary",
    )
    assert store.decision(claim_a)["accepted_pass"] is True
    assert store.decision(claim_b)["accepted_pass"] is True
    store.retract(left, "A's only support")
    assert store.decision(claim_a)["accepted_pass"] is False
    assert store.decision(claim_b)["accepted_pass"] is False
    assert store.get(right)["projection"]["applicability"] == "valid"
    assert store.get(claim_b)["kind"] == "claim"


def test_repeated_retraction_is_idempotent(store):
    claim = add_claim(store)
    evidence = add_observation(store)
    support(store, evidence, claim)
    store.retract(evidence, "once")
    again = store.retract(evidence, "twice")
    assert again["status"] == "already_retracted"
    assert store.get(evidence)["projection"]["applicability"] == "retracted"
    kinds = [item["kind"] for item in store.list_records()]
    assert kinds.count("retraction") == 1
    assert any(event["event_type"] == "retraction_repeated" for event in store.list_events())
    assert store.decision(claim)["accepted_pass"] is False


def test_historical_evaluation_stays_readable_but_not_current(store):
    claim = add_claim(store)
    evidence = add_observation(store)
    support(store, evidence, claim)
    first = store.evaluate(claim)
    assert first["accepted_pass"] is True
    store.retract(evidence, "withdrawn")
    old = store.get(first["evaluation_id"])
    assert old["payload"]["accepted_pass"] is True
    assert old["projection"]["applicability"] == "stale"
    assert store.decision(claim)["accepted_pass"] is False
    assert store.get(claim)["projection"]["extra"]["latest_evaluation_id"] != first["evaluation_id"]


def test_retract_and_read_do_not_tear_a_decision(store):
    claim = add_claim(store)
    evidence = add_observation(store, family="only")
    support(store, evidence, claim)
    barrier = threading.Barrier(2)
    seen = []

    def reader():
        barrier.wait()
        for _ in range(40):
            decision = store.decision(claim)
            seen.append(decision["accepted_pass"])
            if decision["accepted_pass"]:
                assert decision["applicability"] == "valid"
                assert decision["positive_support_ids"]
                assert decision["support_status"] == "supported"
            else:
                assert decision["execution_result"] != "passed"

    def writer():
        barrier.wait()
        store.retract(evidence, "concurrent withdraw")

    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.decision(claim)["accepted_pass"] is False
    assert seen
    assert store.get(evidence)["id"] == evidence


def test_copy_of_retracted_record_is_refused(store):
    evidence = add_observation(store, family="same")
    store.retract(evidence, "no")
    try:
        store.copy_same_source(evidence)
    except RrlError as exc:
        assert exc.code == "E_COPY_NOT_CURRENT"
    else:
        raise AssertionError("copy laundered a retracted record")
