"""Pick a distinguishing experiment from stated predictions and costs.

Model-reported confidence is not an input. The choice is the cheapest
experiment whose predicted outcomes are not all the same.
"""

from __future__ import annotations

from raee_reverse.errors import RrlError


def select_experiment(hypotheses: list[dict], experiments: list[dict]) -> dict:
    if len(hypotheses) < 2:
        raise RrlError("E_EXPERIMENT", "selection needs at least two hypotheses")
    names = [item["name"] for item in hypotheses]
    if len(set(names)) != len(names):
        raise RrlError("E_EXPERIMENT", "hypothesis names must be unique")
    best = None
    for experiment in experiments:
        predictions = experiment.get("predictions") or {}
        missing = [name for name in names if name not in predictions]
        if missing:
            continue
        outcomes = [predictions[name] for name in names]
        if len(set(map(repr, outcomes))) < 2:
            continue
        cost = experiment.get("cost")
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
            raise RrlError("E_EXPERIMENT", "experiment cost must be a non-negative number")
        if best is None or cost < best["cost"]:
            best = {
                "experiment": experiment["name"],
                "cost": cost,
                "distinguishes": names,
                "used_model_confidence": False,
            }
    if best is None:
        return {
            "experiment": None,
            "reason": "no experiment distinguishes the hypotheses",
            "used_model_confidence": False,
        }
    return best
