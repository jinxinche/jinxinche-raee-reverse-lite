from raee_reverse.canonical import digest_bytes

SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["prints-sum"],
    "environments": ["linux-x86_64"],
    "complete_output": True,
}
REQUIRED = {
    "inputs": ["stdin:abc"],
    "behaviors": ["prints-sum"],
    "environments": ["linux-x86_64"],
    "require_complete_output": True,
}


def add_observation(store, *, result="passed", family=None, scope=None, truncated=False, usage="support", provenance="observed"):
    payload = {"summary": f"{usage}:{result}", "truncated": truncated}
    if result == "passed":
        run = {"command": ["sample"], "exit_code": 0, "observed_status": "passed"}
        if provenance == "imported":
            run["environment"] = {"os": "linux", "arch": "x86_64"}
            payload["external_run"] = run
        else:
            payload["run"] = run
    elif result == "failed":
        payload["run"] = {"command": ["sample"], "exit_code": 1, "observed_status": "failed"}
    return store.add_record(
        kind="observation",
        payload=payload,
        provenance=provenance,
        execution_result=result,
        applicability="valid",
        usage=usage,
        verification_scope=dict(scope or SCOPE),
        source_family=family,
    )


def add_claim(store, scope=None, statement="the recorded sum matches"):
    return store.add_record(
        kind="claim",
        payload={"statement": statement, "required_scope": dict(scope or REQUIRED)},
        provenance="observed",
        execution_result="not_executed",
        applicability="valid",
        usage="background",
        verification_scope=dict(SCOPE),
    )


def support(store, evidence, claim, statement="explicit recorded run"):
    return store.add_relation(
        "supports",
        evidence,
        claim,
        {"statement": statement, "method": "explicit"},
    )


def digest() -> str:
    return digest_bytes(b"content")
