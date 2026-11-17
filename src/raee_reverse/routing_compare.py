"""Five-policy routing comparison.

A high-tier answer is not the oracle. Missing prices and missing usage stay
unknown, including on cancelled calls. This module does not invent a savings
percentage. A transport with live=False is not the project comparison.
"""

from __future__ import annotations

import json
import socket
import time
from decimal import Decimal
from typing import Any

from raee_reverse.decision import compress_context, route

POLICIES = (
    "fixed_high_tier",
    "fixed_economy",
    "fixed_by_task_type",
    "auto_difficulty_routing",
    "auto_routing_plus_context_optimization",
)
TIER_ORDER = ("T1", "T2", "T3")
TYPE_TIER = {
    "locate": "T1",
    "structure": "T1",
    "explain": "T2",
    "conflict": "T3",
    "counterexample": "T3",
}
KEY_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "MISTRAL_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "DEEPSEEK_API_KEY",
    "XAI_API_KEY",
)
LOCAL_PORTS = (11434, 1234, 8080)
PROVIDER_TCP_TARGETS = (
    ("api.openai.com", 443),
    ("api.anthropic.com", 443),
    ("generativelanguage.googleapis.com", 443),
    ("api.groq.com", 443),
    ("api.mistral.ai", 443),
    ("api.x.ai", 443),
    ("openrouter.ai", 443),
    ("api.deepseek.com", 443),
    ("api.together.xyz", 443),
    ("api.fireworks.ai", 443),
)


def _profiles_for(profiles: list[dict[str, Any]], tier: str) -> list[dict[str, Any]]:
    return [
        item
        for item in profiles
        if item.get("tier") == tier and item.get("available", True) and item.get("tier") != "T0"
    ]


def _select(profiles: list[dict[str, Any]], tier: str) -> dict[str, Any] | None:
    found = _profiles_for(profiles, tier)
    return found[0] if found else None


def _higher(profiles: list[dict[str, Any]], tier: str) -> dict[str, Any] | None:
    if tier not in TIER_ORDER:
        return None
    index = TIER_ORDER.index(tier)
    for name in TIER_ORDER[index + 1 :]:
        found = _select(profiles, name)
        if found is not None:
            return found
    return None


def _parse_answer(text: str) -> tuple[str, list]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text, []
    if not isinstance(parsed, dict):
        return text, []
    answer = parsed.get("answer")
    refs = parsed.get("evidence_refs")
    if not isinstance(answer, str):
        answer = text
    if not isinstance(refs, list):
        refs = []
    return answer, refs


def _call_cost(result: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    price = profile.get("price") if profile.get("price_status") == "known" else None
    input_tokens = result.get("input_tokens")
    output_tokens = result.get("output_tokens")
    other_tokens = result.get("other_billed_tokens")
    if not isinstance(price, dict) or input_tokens is None or output_tokens is None:
        return {"status": "unknown", "amount": None}
    if other_tokens is None:
        return {"status": "unknown", "amount": None, "reason": "other billed token count is missing"}
    if int(other_tokens) > 0 and "other_per_million" not in price:
        return {"status": "unknown", "amount": None, "reason": "other-token price is missing"}
    other_price = price.get("other_per_million", "0")
    amount = (
        Decimal(int(input_tokens)) * Decimal(str(price["input_per_million"]))
        + Decimal(int(output_tokens)) * Decimal(str(price["output_per_million"]))
        + Decimal(int(other_tokens)) * Decimal(str(other_price))
    ) / Decimal(1_000_000)
    return {"status": "known", "amount": format(amount, "f")}


def _blank_task(task: dict[str, Any], policy: str, reason: str) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "policy": policy,
        "finished": False,
        "correct": False,
        "conclusion": False,
        "evidence_refs": 0,
        "calls": [],
        "routing_overhead_seconds": 0.0,
        "wrong_downgrade": False,
        "unnecessary_upgrade": False,
        "upgraded": False,
        "upgrade_succeeded": False,
        "reason": reason,
    }


def _invoke(task: dict[str, Any], profile: dict[str, Any], transport: Any, prompt: str, *, upgrade: bool) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = transport.call(profile=profile, prompt=prompt, task_id=task.get("task_id"))
    except Exception as exc:
        result = {
            "text": "",
            "input_tokens": None,
            "output_tokens": None,
            "other_billed_tokens": None,
            "latency_seconds": time.perf_counter() - started,
            "cancelled": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(result, dict):
        result = {"text": "", "error": "transport returned a non-dict"}
    latency = result.get("latency_seconds")
    if not isinstance(latency, (int, float)):
        latency = time.perf_counter() - started
    answer, refs = _parse_answer(str(result.get("text") or ""))
    oracle = task.get("oracle")
    passed = bool(oracle(answer)) if callable(oracle) and not result.get("error") else False
    cost = _call_cost(result, profile)
    return {
        "tier": profile.get("tier"),
        "profile_id": profile.get("id"),
        "provider": profile.get("provider"),
        "model": profile.get("model"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "other_billed_tokens": result.get("other_billed_tokens"),
        "latency_seconds": float(latency),
        "cancelled": bool(result.get("cancelled")),
        "error": result.get("error"),
        "cost_status": cost["status"],
        "cost": cost.get("amount"),
        "upgrade": upgrade,
        "oracle_pass": passed,
        "evidence_refs": len(refs),
        "answer": answer,
    }


def run_policy(policy: str, tasks: list[dict[str, Any]], profiles: list[dict[str, Any]], transport: Any) -> dict[str, Any]:
    if policy not in POLICIES:
        raise ValueError(policy)
    rows = []
    for task in tasks:
        overhead_started = time.perf_counter()
        prompt = str(task.get("prompt") or task.get("statement") or "")
        profile: dict[str, Any] | None
        if policy == "fixed_high_tier":
            profile = _select(profiles, "T3")
        elif policy == "fixed_economy":
            profile = _select(profiles, "T1")
        elif policy == "fixed_by_task_type":
            profile = _select(profiles, TYPE_TIER.get(str(task.get("task_type")), ""))
        else:
            plan = route(task, profiles)
            if policy == "auto_routing_plus_context_optimization":
                compressed = compress_context(task.get("context") or {})
                if not compressed.get("ok"):
                    row = _blank_task(task, policy, compressed.get("reason") or "context compression refused")
                    row["routing_overhead_seconds"] = time.perf_counter() - overhead_started
                    rows.append(row)
                    continue
                prompt = json.dumps(compressed.get("kept"), sort_keys=True)
            if plan.get("action") != "call_model":
                row = _blank_task(task, policy, f"router action {plan.get('action')} did not call a model")
                row["routing_overhead_seconds"] = time.perf_counter() - overhead_started
                rows.append(row)
                continue
            profile = next((item for item in profiles if item.get("id") == plan.get("profile_id")), None)
        overhead = time.perf_counter() - overhead_started
        if profile is None:
            rows.append(_blank_task(task, policy, "no available profile for the chosen tier"))
            continue
        first = _invoke(task, profile, transport, prompt, upgrade=False)
        calls = [first]
        unnecessary = False
        upgraded = False
        upgrade_succeeded = False
        final = first
        if first["oracle_pass"] and task.get("upgrade_even_if_correct"):
            nxt = _higher(profiles, str(profile.get("tier")))
            if nxt is not None:
                second = _invoke(
                    task,
                    nxt,
                    transport,
                    prompt + "\nupgrade-without-failure",
                    upgrade=True,
                )
                calls.append(second)
                unnecessary = True
                upgraded = True
                upgrade_succeeded = bool(second["oracle_pass"])
                final = second
        elif not first["oracle_pass"] and not first.get("error") and not first.get("cancelled"):
            nxt = _higher(profiles, str(profile.get("tier")))
            if nxt is not None and int(task.get("max_upgrades") or 0) > 0:
                second = _invoke(
                    task,
                    nxt,
                    transport,
                    prompt + "\nfailure: independent check failed",
                    upgrade=True,
                )
                calls.append(second)
                upgraded = True
                upgrade_succeeded = bool(second["oracle_pass"])
                final = second
        hard = bool(task.get("clearly_hard")) or (task.get("error_cost") or {}).get("level") == "high"
        t3_available = _select(profiles, "T3") is not None
        answered = not bool(final.get("error")) and not bool(final.get("cancelled"))
        wrong = bool(hard and t3_available and answered and calls[-1].get("tier") != "T3")
        rows.append(
            {
                "task_id": task.get("task_id"),
                "policy": policy,
                "finished": answered,
                "correct": bool(final["oracle_pass"]) and answered,
                "conclusion": answered,
                "evidence_refs": int(final.get("evidence_refs") or 0),
                "calls": calls,
                "routing_overhead_seconds": overhead,
                "wrong_downgrade": wrong,
                "unnecessary_upgrade": unnecessary,
                "upgraded": upgraded,
                "upgrade_succeeded": upgrade_succeeded,
                "reason": "",
            }
        )
    return summarize(policy, rows, live=bool(getattr(transport, "live", False)))


def _sum_tokens(calls: list[dict[str, Any]], key: str) -> int | None:
    total = 0
    for call in calls:
        value = call.get(key)
        if value is None:
            return None
        total += int(value)
    return total


def _sum_cost(calls: list[dict[str, Any]]) -> dict[str, Any]:
    if any(call.get("cost_status") != "known" or call.get("cost") is None for call in calls):
        return {"status": "unknown", "amount": None}
    amount = sum((Decimal(str(call["cost"])) for call in calls), Decimal(0))
    return {"status": "known", "amount": format(amount, "f")}


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def summarize(policy: str, rows: list[dict[str, Any]], *, live: bool) -> dict[str, Any]:
    calls = [call for row in rows for call in row["calls"]]
    finished = [row for row in rows if row["finished"]]
    conclusions = [row for row in finished if row["conclusion"]]
    correct = [row for row in rows if row["correct"]]
    no_evidence = [row for row in conclusions if row["evidence_refs"] <= 0]
    upgrades = [row for row in rows if row["upgraded"]]
    cost = _sum_cost(calls) if calls else {"status": "known", "amount": "0"}
    if not calls:
        cost = {"status": "known", "amount": "0"}
    latencies = [float(call["latency_seconds"]) for call in calls if isinstance(call.get("latency_seconds"), (int, float))]
    per_success = None
    if cost["status"] == "known" and correct:
        per_success = format(Decimal(cost["amount"]) / Decimal(len(correct)), "f")
    elif cost["status"] != "known":
        per_success = None
    overhead = sum(float(row["routing_overhead_seconds"]) for row in rows)
    return {
        "policy": policy,
        "executed_harness": True,
        "counts_as_project_comparison": bool(live),
        "live_models": bool(live),
        "savings_percent": None,
        "high_tier_answers_are_ground_truth": False,
        "tasks": len(rows),
        "correct_completion_rate": _rate(len(correct), len(rows)),
        "unsupported_conclusion_rate": _rate(len(no_evidence), len(conclusions)),
        "coverage": _rate(len(conclusions), len(rows)),
        "unfinished_rate": _rate(len(rows) - len(finished), len(rows)),
        "total_cost": cost,
        "input_tokens": _sum_tokens(calls, "input_tokens"),
        "output_tokens": _sum_tokens(calls, "output_tokens"),
        "other_billed_tokens": _sum_tokens(calls, "other_billed_tokens"),
        "cost_per_success": per_success,
        "latency_seconds": latencies,
        "routing_overhead_seconds": overhead,
        "upgrade_rate": _rate(len(upgrades), len(rows)),
        "upgrade_success_rate": _rate(sum(1 for row in upgrades if row["upgrade_succeeded"]), len(upgrades)),
        "wrong_downgrade_rate": _rate(sum(1 for row in rows if row["wrong_downgrade"]), len(rows)),
        "unnecessary_upgrade_rate": _rate(sum(1 for row in rows if row["unnecessary_upgrade"]), len(rows)),
        "cancelled_calls": sum(1 for call in calls if call.get("cancelled")),
        "rows": rows,
    }


def local_port_open(port: int, host: str = "127.0.0.1") -> bool:
    probe = socket.socket()
    probe.settimeout(0.2)
    try:
        return probe.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        probe.close()


def tcp_probe(host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    """Open a TCP connection and close it. This does not send an API request."""
    started = time.perf_counter()
    probe = socket.socket()
    probe.settimeout(timeout)
    try:
        code = probe.connect_ex((host, port))
    except OSError as exc:
        return {
            "host": host,
            "port": port,
            "connected": False,
            "error": f"{type(exc).__name__}: {exc}",
            "seconds": time.perf_counter() - started,
        }
    finally:
        probe.close()
    return {
        "host": host,
        "port": port,
        "connected": code == 0,
        "connect_errno": code,
        "seconds": time.perf_counter() - started,
    }


def probe_record(
    profiles: list[dict[str, Any]],
    prices: dict[str, Any],
    env: dict[str, str],
    ports: dict[int, bool],
    tcp_results: list[dict[str, Any]],
    local_binaries: dict[str, str | None],
) -> dict[str, Any]:
    """Availability plus what this host could actually reach. Never a savings claim."""
    record = availability_record(profiles, prices, env, ports)
    connected = [item["host"] for item in tcp_results if item.get("connected")]
    record["counts_as_project_comparison"] = False
    record["model_calls"] = 0
    record["prices_copied_from_the_network"] = False
    record["tcp_probes"] = tcp_results
    record["tcp_hosts_connected"] = connected
    record["local_binaries"] = local_binaries
    record["missing_conditions"] = list(record["missing_conditions"])
    record["missing_conditions"].append(
        "TCP reachability is not a model endpoint and no model request was sent"
    )
    if not connected and not any(local_binaries.values()):
        record["missing_conditions"].append(
            "no checked provider host accepted TCP and no local model binary was found"
        )
    return record


def availability_record(profiles: list[dict[str, Any]], prices: dict[str, Any], env: dict[str, str], ports: dict[int, bool]) -> dict[str, Any]:
    """Record whether a live five-policy comparison can run. Does not call a model."""
    model_profiles = [item for item in profiles if item.get("tier") != "T0"]
    available = [item for item in model_profiles if item.get("available")]
    priced = [item for item in model_profiles if item.get("price_status") == "known"]
    endpoints = [item.get("id") for item in model_profiles if item.get("endpoint")]
    keys_set = sorted(name for name in KEY_NAMES if env.get(name))
    open_ports = sorted(port for port, is_open in ports.items() if is_open)
    missing = []
    if not available:
        missing.append("no model profile has available=true")
    if not priced or not (prices.get("prices") or {}):
        missing.append("config/prices.json has no prices; an empty price is unknown, not zero")
    if prices.get("observed_at") in (None, ""):
        missing.append("prices.observed_at is null")
    if not endpoints:
        missing.append("no profile has an endpoint URL")
    if not keys_set:
        missing.append("none of the checked provider API key variables are set")
    if not open_ports:
        missing.append("no local model port among 11434, 1234, and 8080 accepted a connection")
    return {
        "executed": False,
        "savings_percent": None,
        "high_tier_answers_are_ground_truth": False,
        "policies": list(POLICIES),
        "metrics": {
            "correct_completion_rate": "not_collected",
            "unsupported_conclusion_rate": "not_collected",
            "coverage": "not_collected",
            "unfinished_rate": "not_collected",
            "total_cost": "not_collected",
            "input_tokens": "not_collected",
            "output_tokens": "not_collected",
            "other_billed_tokens": "not_collected",
            "cost_per_success": "not_collected",
            "latency_distribution": "not_collected",
            "routing_overhead": "not_collected",
            "upgrade_rate": "not_collected",
            "upgrade_success_rate": "not_collected",
            "wrong_downgrade_rate": "not_collected",
            "unnecessary_upgrade_rate": "not_collected",
        },
        "missing_conditions": missing,
        "profiles_available": [item.get("id") for item in available],
        "profiles_with_known_price": [item.get("id") for item in priced],
        "provider_key_variables_set": keys_set,
        "local_ports_open": open_ports,
        "checked_key_variables": list(KEY_NAMES),
        "checked_local_ports": list(LOCAL_PORTS),
    }


def measured_cost_ratio(left: dict[str, Any], right: dict[str, Any]) -> str | None:
    """Ratio of two known totals. None when either total is unknown. Not a target savings."""
    if left.get("total_cost", {}).get("status") != "known" or right.get("total_cost", {}).get("status") != "known":
        return None
    right_amount = Decimal(str(right["total_cost"]["amount"]))
    if right_amount == 0:
        return None
    return format(Decimal(str(left["total_cost"]["amount"])) / right_amount, "f")
