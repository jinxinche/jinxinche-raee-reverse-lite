"""Built-in scheduler handlers. Unknown names are errors, not successes."""

from __future__ import annotations

import time

from raee_reverse.errors import CancelledTask, DeterministicTaskError, InfraTaskError


def ok(ctx) -> dict:
    return {"ok": True, "attempt": ctx.attempt, "checkpoint": ctx.checkpoint}


def deterministic_fail(ctx) -> dict:
    raise DeterministicTaskError("deterministic failure; not retried")


def infra_then_ok(ctx) -> dict:
    if ctx.checkpoint.get("tried"):
        return {"ok": True, "recovered_from_checkpoint": True}
    ctx.save_checkpoint({"tried": True})
    raise InfraTaskError("transient infrastructure failure")


def sleeper(ctx) -> dict:
    started = time.time()
    time.sleep(1.0)
    return {"ok": True, "started": started, "ended": time.time()}


def sleep_long(ctx) -> dict:
    time.sleep(30)
    return {"ok": True}


def spin_until_cancel(ctx) -> dict:
    while not ctx.cancelled():
        if time.monotonic() > ctx.deadline:
            raise InfraTaskError("cancel was not observed before the deadline")
        time.sleep(0.05)
    raise CancelledTask("cancel observed")


def checkpoint_and_wait(ctx) -> dict:
    ctx.save_checkpoint({"phase": "waiting"})
    time.sleep(30)
    return {"ok": True}


HANDLERS = {
    "ok": ok,
    "deterministic_fail": deterministic_fail,
    "infra_then_ok": infra_then_ok,
    "sleeper": sleeper,
    "sleep_long": sleep_long,
    "spin_until_cancel": spin_until_cancel,
    "checkpoint_and_wait": checkpoint_and_wait,
}
