import ast
from pathlib import Path

import pytest

from raee_reverse.attribution import exact_shapley, group_removal, interaction, sample_shapley
from raee_reverse.audit import audit_python_tree
from raee_reverse.canonical import digest_bytes
from raee_reverse.errors import RrlError
from raee_reverse.store import Store


def _components(**overrides):
    base = {
        "content_digests": [digest_bytes(b"target")],
        "dependency_digests": [digest_bytes(b"dep")],
        "tool_name": "ghidra",
        "tool_version": "12.2",
        "params": {"script": "export"},
        "config": {"analysis": "default"},
        "env": {"os": "linux", "arch": "x86_64"},
        "env_complete": True,
    }
    base.update(overrides)
    return base


def test_cache_ignores_path_and_mtime_and_binds_real_inputs(store):
    store.cache_put(_components(), b"analysis")
    assert store.cache_get(_components(path="/tmp/a", mtime=1))["hit"] is True
    assert store.cache_get(_components(path="/tmp/b", mtime=99))["hit"] is True
    for field, value in (
        ("content_digests", [digest_bytes(b"other")]),
        ("dependency_digests", [digest_bytes(b"other-dep")]),
        ("tool_version", "11.0"),
        ("params", {"script": "other"}),
        ("config", {"analysis": "other"}),
        ("env", {"os": "windows", "arch": "x86_64"}),
    ):
        assert store.cache_get(_components(**{field: value}))["hit"] is False


def test_incomplete_environment_is_not_reused(store):
    stored = store.cache_put(_components(env_complete=False), b"do-not-reuse")
    assert stored["reusable"] is False
    looked = store.cache_get(_components(env_complete=False, path="/same"))
    assert looked["hit"] is False
    assert looked["reason"] == "conservative_invalidation"
    assert looked["limitations"]


def test_static_omission_dynamic_and_clean_scan(tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "mod.py").write_text("import json\n", encoding="utf-8")
    report = audit_python_tree(clean, set())
    assert report["status"] == "no_omission_detected"
    assert report["closure_proof"] is False
    assert report["accepted_pass"] is False

    omitted = tmp_path / "omitted"
    omitted.mkdir()
    (omitted / "mod.py").write_text("import requests\n", encoding="utf-8")
    missing = audit_python_tree(omitted, set())
    assert missing["status"] == "incomplete_scope"
    assert missing["missing_declarations"] == ["requests"]
    assert missing["accepted_pass"] is False

    dynamic = tmp_path / "dynamic"
    dynamic.mkdir()
    (dynamic / "mod.py").write_text("import importlib\nimportlib.import_module('json')\n", encoding="utf-8")
    uncertain = audit_python_tree(dynamic, set())
    assert uncertain["status"] == "uncertain"
    assert uncertain["dynamic_imports"]
    assert uncertain["closure_proof"] is False

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "mod.py").write_text("def (\n", encoding="utf-8")
    assert audit_python_tree(broken, set())["status"] == "uncertain"


def test_unreadable_file_is_uncertain(tmp_path):
    root = tmp_path / "hidden"
    root.mkdir()
    target = root / "mod.py"
    target.write_text("import json\n", encoding="utf-8")
    target.chmod(0)
    try:
        report = audit_python_tree(root, set())
    finally:
        target.chmod(0o644)
    assert report["status"] == "uncertain"
    assert report["unreadable"]
    assert report["accepted_pass"] is False


def test_package_audit_is_not_a_closure_proof():
    root = Path(__file__).resolve().parents[1] / "src"
    report = audit_python_tree(root, set())
    assert report["closure_proof"] is False
    assert report["accepted_pass"] is False
    assert report["status"] == "no_omission_detected"
    assert report["files_scanned"] > 0


def test_group_removal_interaction_and_missing_values():
    factors = ["i", "j"]
    single = group_removal({"i": 1.0, "": 0.0}, ["i"])
    assert single["deltas"]["i"]["value"] == 1.0
    assert single["causal_claim"] is False
    assert single["not_independent_cause"] is True

    both = {"i,j": 1.0, "i": 0.0, "j": 0.0, "": 0.0}
    assert interaction(both, factors, "i", "j")["value"] == 1.0
    xor = {"i,j": 0.0, "i": 1.0, "j": 1.0, "": 0.0}
    assert interaction(xor, factors, "i", "j")["value"] == -2.0
    redundant = {"i,j": 1.0, "i": 1.0, "j": 1.0, "": 0.0}
    assert interaction(redundant, factors, "i", "j")["value"] == -1.0
    negative = group_removal({"i,j": 0.0, "j": 1.0, "i": 1.0, "": 0.0}, factors)
    assert negative["deltas"]["i"]["value"] == -1.0

    missing = group_removal({"i,j": 1.0}, factors)
    assert missing["deltas"]["i"]["status"] == "missing"
    assert missing["deltas"]["i"]["value"] is None
    assert missing["treated_missing_as_zero"] is False
    shapley = exact_shapley({"i,j": 1.0, "i": 1.0}, factors)
    assert shapley["status"] == "uncertain"
    assert shapley["values"] is None
    assert 0 not in (shapley["values"] or [])


def test_shapley_symmetry_noise_and_constraint():
    factors = ["i", "j"]
    # v depends only on coalition size, so the factors are symmetric.
    values = {"": 0.0, "i": 2.0, "j": 2.0, "i,j": 3.0}
    report = exact_shapley(values, factors)
    assert report["status"] == "computed"
    assert report["values"]["i"] == pytest.approx(report["values"]["j"])
    assert report["causal_claim"] is False
    constrained = exact_shapley(values, ["i"], excluded_factors=["j"], constrained_explanation=None)
    assert constrained["status"] == "uncertain"
    assert constrained["values"] is None
    explained = exact_shapley(
        {"": 0.0, "i": 2.0},
        ["i"],
        excluded_factors=["j"],
        constrained_explanation="j cannot be executed; this is not the unconstrained game",
    )
    assert explained["status"] == "computed"
    assert explained["same_as_unconstrained_shapley"] is False
    sampled = sample_shapley(values, factors, sample_count=32, seed=7)
    again = sample_shapley(values, factors, sample_count=32, seed=7)
    assert sampled["values"] == again["values"]
    assert sampled["seed"] == 7
    assert sampled["stopping_condition"] == "sample_count reached"
    blocked = sample_shapley({"i": 1.0}, factors, sample_count=4, seed=1)
    assert blocked["status"] == "uncertain"
    assert blocked["values"] is None
    assert blocked["treated_missing_as_zero"] is False


def test_attribution_record_requires_a_value_function(tmp_path):
    store = Store(tmp_path / "ledger")
    try:
        with pytest.raises(RrlError):
            store.add_record(
                kind="attribution",
                payload={"contribution_percent": 40},
                provenance="model_generated",
                execution_result="not_executed",
                applicability="incomplete_scope",
                usage="background",
                verification_scope={"inputs": ["n/a"], "behaviors": ["n/a"], "environments": ["n/a"]},
            )
        record_id = store.add_record(
            kind="attribution",
            payload={
                "statement": "arithmetic example, not a measured target effect",
                "value_function": {
                    "argument": "evidence set",
                    "baseline": "empty set",
                    "direction": "higher is more covered scope",
                    "measured": False,
                    "missing_value": "null, not zero",
                    "confounders": ["shared source family"],
                },
            },
            provenance="model_generated",
            execution_result="not_executed",
            applicability="incomplete_scope",
            usage="background",
            verification_scope={"inputs": ["synthetic"], "behaviors": ["arithmetic"], "environments": ["unit"]},
        )
        stored = store.get(record_id)
        assert stored["projection"]["execution_result"] == "not_executed"
        assert stored["projection"]["extra"]["accepted_pass"] is False
        store.verify_integrity()
    finally:
        store.close()


def test_audit_module_parses():
    source = Path(__file__).resolve().parents[1] / "src" / "raee_reverse" / "audit.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    assert isinstance(tree, ast.Module)
