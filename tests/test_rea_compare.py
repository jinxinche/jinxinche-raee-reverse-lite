"""Pair scoring. An unobserved side is not a comparison and is not a ranking."""

from raee_reverse.rea_compare import TASKS, score_observation, summarize_pairs


def _row(task, rea_stdout, tool_stdout, rea_code=0, tool_code=0):
    return {
        "task_id": task["id"],
        "rea_seconds": 0.2,
        "rea": score_observation(task["stdout"], rea_stdout, rea_code),
        "this_tool": score_observation(task["stdout"], tool_stdout, tool_code),
    }


def test_unobserved_side_is_not_a_scored_pair():
    task = TASKS[0]
    row = _row(task, None, task["stdout"], rea_code=None)
    summary = summarize_pairs([row], model_cost={"status": "unknown", "amount": None})
    assert summary["sample_size_scored_pairs"] == 0
    assert summary["comparison_complete"] is False
    assert summary["ranking"] is False
    assert summary["metrics"]["correct_completion_rate"] == "not_collected"


def test_zero_scored_pairs_is_not_a_comparison():
    summary = summarize_pairs([], model_cost={"status": "unknown", "amount": None, "reason": "no usage report"})
    assert summary["comparison_complete"] is False
    assert summary["executed"] is False
    assert summary["sample_size_scored_pairs"] == 0
    assert summary["model_cost"]["amount"] is None
    assert summary["savings_percent"] is None
    assert summary["promotes_static_sample"] is False


def test_scored_pairs_do_not_invent_a_ranking_or_a_zero_model_cost():
    rows = [_row(task, task["stdout"], task["stdout"]) for task in TASKS]
    summary = summarize_pairs(rows, model_cost={"status": "unknown", "amount": None, "reason": "no usage report"})
    assert summary["comparison_complete"] is True
    assert summary["sample_size_scored_pairs"] == len(TASKS)
    assert summary["ranking"] is False
    assert summary["model_cost"]["status"] == "unknown"
    assert summary["model_cost"]["amount"] is None
    assert summary["metrics"]["rea_correct_completion_rate"] == 1.0
    assert summary["savings_percent"] is None
