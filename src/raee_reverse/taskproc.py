"""Child process for one scheduler attempt. A kill leaves the task RUNNING."""

from __future__ import annotations

import argparse

from raee_reverse.errors import CancelledTask, DeterministicTaskError, InfraTaskError, RrlError
from raee_reverse.handlers import HANDLERS
from raee_reverse.store import Store


class TaskContext:
    def __init__(self, store: Store, task: dict) -> None:
        self.store = store
        self.task = task
        self.attempt = task["attempts"]
        self.checkpoint = task["checkpoint"] or {}
        import time

        self.deadline = time.monotonic() + float(task["timeout_seconds"])

    def save_checkpoint(self, data: dict) -> None:
        self.checkpoint = data
        self.store.set_checkpoint(self.task["id"], data)

    def cancelled(self) -> bool:
        return bool(self.store.get_task(self.task["id"])["cancel_requested"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raee_reverse.taskproc")
    parser.add_argument("--root", required=True)
    parser.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    store = Store(args.root)
    try:
        task = store.get_task(args.task)
        if task["state"] != "RUNNING":
            return 2
        handler = HANDLERS.get(task["handler"])
        if handler is None:
            store.publish_failure(args.task, "deterministic", f"unknown handler {task['handler']}")
            return 10
        try:
            result = handler(TaskContext(store, task))
            if not isinstance(result, dict):
                result = {"result": result}
            store.publish_success(args.task, result)
            return 0
        except DeterministicTaskError as exc:
            store.publish_failure(args.task, "deterministic", exc.message)
            return 10
        except InfraTaskError as exc:
            store.publish_failure(args.task, "infra", exc.message)
            return 11
        except CancelledTask as exc:
            store.request_cancel(args.task)
            store.publish_failure(args.task, "infra", exc.message)
            return 12
    except RrlError:
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
