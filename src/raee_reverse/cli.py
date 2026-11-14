"""Minimal CLI. Exit 0 means the command finished, except `gate`.

`gate` exits 0 only when that claim's accepted_pass is true, and exits 2
otherwise. A target program's exit code is never copied onto this process as
proof of a requirement.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from raee_reverse import __version__
from raee_reverse.errors import RrlError
from raee_reverse.scheduler import Scheduler
from raee_reverse.store import Store

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_GATE = 2
EXIT_ERROR = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rrl")
    parser.add_argument("--version", action="version", version=f"raee-reverse-lite {__version__}")
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")

    requirement = sub.add_parser("requirement")
    requirement_sub = requirement.add_subparsers(dest="action", required=True)
    requirement_add = requirement_sub.add_parser("add")
    requirement_add.add_argument("statement")

    artifact = sub.add_parser("artifact")
    artifact_sub = artifact.add_subparsers(dest="action", required=True)
    artifact_add = artifact_sub.add_parser("add")
    artifact_add.add_argument("--file", required=True)

    observation = sub.add_parser("observation")
    observation_sub = observation.add_subparsers(dest="action", required=True)
    observation_add = observation_sub.add_parser("add")
    observation_add.add_argument("--summary", required=True)
    observation_add.add_argument("--execution", required=True, choices=["passed", "failed", "uncertain", "not_executed"])
    observation_add.add_argument("--usage", default="support", choices=["support", "oppose", "qualify", "background"])
    observation_add.add_argument("--source-family", default=None)
    observation_add.add_argument("--truncated", action="store_true")
    observation_add.add_argument("--exit-code", type=int, default=None)
    observation_add.add_argument("--scope-json", required=True)

    claim = sub.add_parser("claim")
    claim_sub = claim.add_subparsers(dest="action", required=True)
    claim_add = claim_sub.add_parser("add")
    claim_add.add_argument("--statement", required=True)
    claim_add.add_argument("--scope-json", required=True)

    link = sub.add_parser("link")
    link.add_argument("rel_type")
    link.add_argument("--src", required=True)
    link.add_argument("--dst", required=True)
    link.add_argument("--basis", required=True)
    link.add_argument("--role", default=None)
    link.add_argument("--slot", default=None)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("claim_id")
    gate = sub.add_parser("gate")
    gate.add_argument("claim_id")
    retract = sub.add_parser("retract")
    retract.add_argument("record_id")
    retract.add_argument("--reason", required=True)
    stale = sub.add_parser("stale")
    stale.add_argument("record_id")
    stale.add_argument("--reason", required=True)
    show = sub.add_parser("show")
    show.add_argument("record_id")
    sub.add_parser("status")

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="action", required=True)
    task_submit = task_sub.add_parser("submit")
    task_submit.add_argument("--id", required=True)
    task_submit.add_argument("--handler", required=True)
    task_submit.add_argument("--dep", action="append", default=[])
    task_submit.add_argument("--timeout", type=float, default=5)
    task_submit.add_argument("--attempts", type=int, default=1)
    task_submit.add_argument("--class", dest="resource_class", default="dev")
    task_run = task_sub.add_parser("run")
    task_run.add_argument("--workers", type=int, default=1)
    task_cancel = task_sub.add_parser("cancel")
    task_cancel.add_argument("task_id")
    task_sub.add_parser("recover")

    audit = sub.add_parser("audit")
    audit.add_argument("path")

    args = parser.parse_args(argv)
    root = _root(args.root)
    try:
        if args.command == "init":
            store = Store(root)
            store.close()
            return _emit({"root": str(root), "created": True})
        store = Store(root)
        try:
            return _dispatch(store, args)
        finally:
            store.close()
    except RrlError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2, sort_keys=True))
        return EXIT_ERROR


def _dispatch(store: Store, args: argparse.Namespace) -> int:
    if args.command == "requirement" and args.action == "add":
        record_id = store.add_record(
            kind="requirement",
            payload={"statement": args.statement},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope={"inputs": ["requirement-text"], "behaviors": ["recorded"], "environments": ["local"]},
        )
        return _emit({"id": record_id, "kind": "requirement"})
    if args.command == "artifact" and args.action == "add":
        data = Path(args.file).read_bytes()
        digest = store.put_blob(data)
        record_id = store.add_record(
            kind="artifact",
            payload={"content_digest": digest, "size": len(data), "path_hint": str(Path(args.file).name)},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope={"inputs": [digest], "behaviors": ["hashed"], "environments": ["local"]},
        )
        return _emit({"id": record_id, "content_digest": digest})
    if args.command == "observation" and args.action == "add":
        scope = json.loads(args.scope_json)
        payload = {"summary": args.summary, "truncated": bool(args.truncated)}
        if args.exit_code is not None:
            payload["run"] = {
                "command": ["recorded-by-operator"],
                "exit_code": args.exit_code,
                "observed_status": "passed" if args.execution == "passed" else "failed",
            }
        record_id = store.add_record(
            kind="observation",
            payload=payload,
            provenance="observed",
            execution_result=args.execution,
            applicability="valid",
            usage=args.usage,
            verification_scope=scope,
            source_family=args.source_family,
        )
        return _emit(store.get(record_id))
    if args.command == "claim" and args.action == "add":
        scope = json.loads(args.scope_json)
        record_id = store.add_record(
            kind="claim",
            payload={"statement": args.statement, "required_scope": scope},
            provenance="observed",
            execution_result="not_executed",
            applicability="valid",
            usage="background",
            verification_scope={"inputs": ["claim"], "behaviors": ["recorded"], "environments": ["local"]},
        )
        return _emit(store.decision(record_id))
    if args.command == "link":
        relation_id = store.add_relation(
            args.rel_type,
            args.src,
            args.dst,
            {"statement": args.basis, "method": "explicit-cli"},
            role=args.role,
            premise_slot=args.slot,
        )
        return _emit({"relation_id": relation_id})
    if args.command == "evaluate":
        return _emit(store.evaluate(args.claim_id))
    if args.command == "gate":
        decision = store.decision(args.claim_id)
        _emit(decision)
        return EXIT_OK if decision["accepted_pass"] else EXIT_GATE
    if args.command == "retract":
        return _emit(store.retract(args.record_id, args.reason))
    if args.command == "stale":
        return _emit(store.mark_stale(args.record_id, args.reason))
    if args.command == "show":
        return _emit(store.get(args.record_id))
    if args.command == "status":
        return _emit(store.status_summary())
    if args.command == "task" and args.action == "submit":
        return _emit(
            store.submit_task(
                task_id=args.id,
                handler=args.handler,
                deps=args.dep,
                owner="cli",
                inputs_version="cli",
                timeout_seconds=args.timeout,
                max_attempts=args.attempts,
                resource_class=args.resource_class,
            )
        )
    if args.command == "task" and args.action == "run":
        report = Scheduler(store).run(max_workers=args.workers)
        return _emit(report)
    if args.command == "task" and args.action == "cancel":
        return _emit({"id": args.task_id, "state": store.request_cancel(args.task_id)})
    if args.command == "task" and args.action == "recover":
        return _emit({"actions": store.recover_running()})
    if args.command == "audit":
        return _emit(store.audit_tree(args.path))
    raise RrlError("E_USAGE", "unhandled command")


def _root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("RRL_ROOT")
    if env:
        return Path(env)
    return Path.cwd() / ".rrl"


def _emit(payload: dict) -> int:
    print(
        json.dumps(
            {
                "ok": True,
                "note": "ok means the command completed. It is not, by itself, a verification pass.",
                "result": payload,
            },
            indent=2,
            sort_keys=True,
            default=_default,
        )
    )
    return EXIT_OK


def _default(value):
    if isinstance(value, bytes):
        return {"bytes": len(value), "sha256_prefix": value[:16].hex()}
    raise TypeError(type(value).__name__)
