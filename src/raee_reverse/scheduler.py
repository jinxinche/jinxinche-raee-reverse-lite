"""Lightweight scheduler. It is not a cluster, and it does not invent workers.

Exclusive resource classes (native analysis, model, performance) never share
a batch with other tasks. Infrastructure failures retry up to max_attempts.
Deterministic failures do not. Timeout and cancel do not become success.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from raee_reverse.model import EXCLUSIVE_RESOURCE_CLASSES
from raee_reverse.store import Store

_EXCLUSIVE = {item.value for item in EXCLUSIVE_RESOURCE_CLASSES}


def _child_env(root: Path) -> dict[str, str]:
    allow = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TZ"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allow}
    import raee_reverse

    package_root = str(Path(raee_reverse.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = package_root
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONUTF8"] = "1"
    env["RRL_TASK_ROOT"] = str(root)
    return env


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


class Scheduler:
    def __init__(self, store: Store) -> None:
        self.store = store

    def run(self, *, max_workers: int = 1) -> dict:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        peak = 0
        steps = []
        for _ in range(64):
            self.store.refresh_tasks()
            batch = self._select(max_workers)
            if not batch:
                break
            peak = max(peak, len(batch))
            steps.append(self._execute(batch))
        return {
            "actual_concurrency": peak,
            "batches": len(steps),
            "steps": steps,
            "tasks": self.store.list_tasks(),
            "note": "actual_concurrency is the largest batch this call started, not a claim about other agents",
        }

    def _select(self, max_workers: int) -> list[dict]:
        tasks = self.store.list_tasks()
        running = [task for task in tasks if task["state"] == "RUNNING"]
        queued = [task for task in tasks if task["state"] == "QUEUED"]
        if any(task["resource_class"] in _EXCLUSIVE for task in running):
            return []
        if not queued:
            return []
        exclusive = [task for task in queued if task["resource_class"] in _EXCLUSIVE]
        if exclusive:
            if running:
                return []
            return [exclusive[0]]
        if running:
            return []
        return queued[:max_workers]

    def _execute(self, batch: list[dict]) -> list[dict]:
        procs = []
        for task in batch:
            started = self.store.begin_attempt(task["id"])
            proc = subprocess.Popen(
                [sys.executable, "-m", "raee_reverse.taskproc", "--root", str(self.store.root), "--task", task["id"]],
                cwd=self.store.root,
                env=_child_env(self.store.root),
                start_new_session=(os.name == "posix"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append((started, proc))
        results = []
        for started, proc in procs:
            timeout = float(started["timeout_seconds"]) + 1.0
            timed_out = False
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill(proc)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            if timed_out:
                state = self.store.finalize_if_still_running(started["id"], "timeout")
            else:
                current = self.store.get_task(started["id"])
                if current["state"] == "RUNNING":
                    state = self.store.finalize_if_still_running(started["id"], "interrupted")
                else:
                    state = current["state"]
            results.append(
                {
                    "id": started["id"],
                    "state": state,
                    "returncode": proc.returncode,
                    "schedule_succeeded": state == "SUCCEEDED",
                    "evidence_accepted_pass": False,
                }
            )
        return results
