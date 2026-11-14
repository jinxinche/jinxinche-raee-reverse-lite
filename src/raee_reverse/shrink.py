"""Bounded counterexample shrinking.

The result is a smaller input that still fails the same predicate. It is not
a proof that the result is the shortest failure in the world.
"""

from __future__ import annotations


def shrink_bytes(data: bytes, fails) -> dict:
    if not data or not fails(data):
        return {
            "reduced": data,
            "steps": 0,
            "predicate_held": bool(data) and bool(fails(data)) if data else False,
            "global_minimum": False,
            "note": "the seed did not fail the predicate" if not data or not fails(data) else "",
        }
    current = data
    steps = 0
    chunk = max(1, len(current) // 2)
    while chunk >= 1:
        reduced = False
        index = 0
        while index < len(current):
            candidate = current[:index] + current[index + chunk :]
            steps += 1
            if candidate and fails(candidate):
                current = candidate
                reduced = True
            else:
                index += chunk
        if not reduced:
            chunk //= 2
    return {
        "reduced": current,
        "steps": steps,
        "predicate_held": True,
        "global_minimum": False,
        "note": "reduced under this deletion search only",
    }
