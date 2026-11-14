"""Extension points. A missing engine is an explicit non-result, not a pass."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AnalysisAdapter(Protocol):
    name: str

    def analyze(self, artifact: Path, *, budget: dict) -> dict:
        """Return execution_result, applicability, limitations, and accepted_pass."""


class ExecutionAdapter(Protocol):
    name: str

    def run(self, argv: list[str], *, work_dir: Path, timeout: float) -> dict:
        """Return outcome and execution_result. accepted_pass stays false here;
        only a claim evaluation can accept a pass, and only inside its scope."""


def missing_engine(name: str, detail: str) -> dict:
    return {
        "engine": name,
        "execution_result": "not_executed",
        "applicability": "incomplete_scope",
        "provenance": "observed",
        "accepted_pass": False,
        "observations": [],
        "limitations": [detail],
        "simulated": False,
    }
