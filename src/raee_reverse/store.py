"""SQLite ledger plus a content-addressed blob store.

Raw records, relations, and events are immutable. Current conclusions live in
projections and change only by appending events. A claim is an accepted pass
only when execution, applicability, support, scope, and independent sources
all agree. Missing, uncertain, stale, truncated, and retracted inputs do not.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from raee_reverse.audit import audit_python_tree
from raee_reverse.cache import prepare_cache
from raee_reverse.canonical import canonical_dumps, digest_bytes, digest_obj
from raee_reverse.errors import RrlError
from raee_reverse.locking import FileLock
from raee_reverse.model import (
    Applicability,
    ExecutionResult,
    Kind,
    Provenance,
    RelType,
    ResourceClass,
    SupportStatus,
    TaskState,
    Usage,
    scope_covers,
    scope_explicit,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL UNIQUE,
  event_type TEXT NOT NULL,
  subject_id TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proj (
  entity_id TEXT PRIMARY KEY,
  entity_kind TEXT NOT NULL,
  provenance TEXT NOT NULL,
  execution_result TEXT NOT NULL,
  applicability TEXT NOT NULL,
  usage TEXT NOT NULL,
  verification_scope_json TEXT NOT NULL,
  support_status TEXT NOT NULL,
  independent_support_count INTEGER NOT NULL,
  source_family TEXT NOT NULL,
  extra_json TEXT NOT NULL,
  updated_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS relations (
  id TEXT PRIMARY KEY,
  rel_type TEXT NOT NULL,
  src_id TEXT NOT NULL,
  dst_id TEXT NOT NULL,
  role TEXT,
  premise_slot TEXT,
  basis_json TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_entries (
  cache_key TEXT PRIMARY KEY,
  components_json TEXT NOT NULL,
  env_complete INTEGER NOT NULL,
  reusable INTEGER NOT NULL,
  limitations_json TEXT NOT NULL,
  result_digest TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  state TEXT NOT NULL,
  owner TEXT NOT NULL,
  handler TEXT NOT NULL,
  inputs_version TEXT NOT NULL,
  deps_json TEXT NOT NULL,
  workspace TEXT,
  budget_json TEXT NOT NULL,
  resource_class TEXT NOT NULL,
  timeout_seconds REAL NOT NULL,
  max_attempts INTEGER NOT NULL,
  attempts INTEGER NOT NULL,
  started_at TEXT,
  ended_at TEXT,
  exit_status TEXT,
  failure_class TEXT,
  blocked_reason TEXT,
  artifact_json TEXT NOT NULL,
  evidence_ids_json TEXT NOT NULL,
  checkpoint_json TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  log_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rel_src ON relations(src_id);
CREATE INDEX IF NOT EXISTS idx_rel_dst ON relations(dst_id);
CREATE INDEX IF NOT EXISTS idx_rel_src_type ON relations(src_id, rel_type);
CREATE INDEX IF NOT EXISTS idx_rel_dst_type ON relations(dst_id, rel_type);
CREATE INDEX IF NOT EXISTS idx_proj_family_applicability
  ON proj(source_family, applicability, entity_kind);
CREATE TRIGGER IF NOT EXISTS records_no_update BEFORE UPDATE ON records
BEGIN SELECT RAISE(ABORT, 'immutable_record'); END;
CREATE TRIGGER IF NOT EXISTS records_no_delete BEFORE DELETE ON records
BEGIN SELECT RAISE(ABORT, 'immutable_record'); END;
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'immutable_event'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'immutable_event'); END;
CREATE TRIGGER IF NOT EXISTS relations_no_update BEFORE UPDATE ON relations
BEGIN SELECT RAISE(ABORT, 'immutable_relation'); END;
CREATE TRIGGER IF NOT EXISTS relations_no_delete BEFORE DELETE ON relations
BEGIN SELECT RAISE(ABORT, 'immutable_relation'); END;
"""

_LEDGER_SCOPE = {
    "inputs": ["ledger"],
    "behaviors": ["ledger-operation"],
    "environments": ["local-ledger"],
    "complete_output": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Store:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_root = self.root / "blobs"
        self.blob_root.mkdir(exist_ok=True)
        self.db_path = self.root / "ledger.sqlite"
        self._lock = threading.RLock()
        self._flock = FileLock(self.root / "ledger.lock")
        self._local = threading.local()
        self._depth = 0
        self._owner: int | None = None
        self.failpoint: str | None = None
        self._proj_cache: dict[str, dict] = {}
        self._family_retracted_cache: dict[str, bool] = {}
        # One connection is shared by worker threads. check_same_thread is false
        # so another thread may use it, but two statements at once are
        # SQLITE_MISUSE: InterfaceError, or a row whose columns come back empty.
        # _tx and _readlock are the serialization for every statement.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()
        self._flock.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[None]:
        if self._depth and self._owner == threading.get_ident():
            raise RrlError("E_NESTED_TX", "nested transaction")
        self._lock.acquire()
        self._flock.acquire()
        self._owner = threading.get_ident()
        self._local.held = getattr(self._local, "held", 0) + 1
        self._depth += 1
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            if self.failpoint == "before_commit":
                self.failpoint = None
                self._conn.rollback()
                raise RrlError("E_INJECTED_CRASH", "injected crash before commit")
            self._conn.commit()
        except Exception:
            self._proj_cache.clear()
            self._family_retracted_cache.clear()
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass
            raise
        finally:
            self._depth -= 1
            self._local.held -= 1
            if self._depth == 0:
                self._owner = None
            self._flock.release()
            self._lock.release()

    @contextmanager
    def _readlock(self) -> Iterator[None]:
        """Serialize readers with writers. Re-entrant for the thread that already holds it.

        `_depth` is process-wide state on this connection, so another thread must
        not treat an in-progress writer as its own transaction.
        """
        if getattr(self._local, "held", 0):
            self._local.held += 1
            try:
                yield
            finally:
                self._local.held -= 1
            return
        self._lock.acquire()
        self._flock.acquire()
        self._local.held = 1
        try:
            yield
        finally:
            self._local.held = 0
            self._flock.release()
            self._lock.release()

    def put_blob(self, data: bytes) -> str:
        if not isinstance(data, (bytes, bytearray)):
            raise RrlError("E_BLOB_TYPE", "blobs are raw bytes")
        data = bytes(data)
        digest = digest_bytes(data)
        path = self._blob_path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_bytes()
            if existing != data:
                raise RrlError("E_CONTENT_MISMATCH", "blob path holds different bytes", digest=digest)
            return digest
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)
        return digest

    def get_blob(self, digest: str) -> bytes:
        path = self._blob_path(digest)
        if not path.is_file():
            raise RrlError("E_MISSING_BLOB", "content-addressed blob is missing", digest=digest)
        data = path.read_bytes()
        if digest_bytes(data) != digest:
            raise RrlError("E_CONTENT_MISMATCH", "blob bytes do not match the address", digest=digest)
        return data

    def _blob_path(self, digest: str) -> Path:
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise RrlError("E_DIGEST", "digest must be 64 lowercase hex characters")
        return self.blob_root / digest[:2] / digest

    def add_record(
        self,
        *,
        kind: str,
        payload: dict,
        provenance: str,
        execution_result: str,
        applicability: str,
        usage: str,
        verification_scope: dict,
        source_family: str | None = None,
    ) -> str:
        kind_e, prov, result, applic, use, scope, payload = self._validate_new(
            kind, payload, provenance, execution_result, applicability, usage, verification_scope
        )
        with self._tx():
            record_id = self._insert_record(
                kind_e, payload, prov, result, applic, use, scope, source_family
            )
            if kind_e == Kind.CLAIM:
                self._fixpoint([record_id])
            return record_id

    def copy_same_source(self, record_id: str) -> str:
        """Duplicate a record without giving it a new independent source.

        Refuses retracted or stale records so a copy cannot launder them back
        into the support set.
        """
        current = self.get(record_id)
        applicability = current["projection"]["applicability"]
        if applicability in (Applicability.RETRACTED.value, Applicability.STALE.value):
            raise RrlError("E_COPY_NOT_CURRENT", "refusing to copy a retracted or stale record", id=record_id)
        payload = dict(current["payload"])
        payload.pop("dimensions_at_creation", None)
        payload.pop("adjustments", None)
        return self.add_record(
            kind=current["kind"],
            payload=payload,
            provenance=current["projection"]["provenance"],
            execution_result=current["projection"]["execution_result"],
            applicability=current["payload"]["dimensions_at_creation"]["applicability"],
            usage=current["projection"]["usage"],
            verification_scope=current["projection"]["verification_scope"],
            source_family=current["projection"]["source_family"],
        )

    def add_relation(
        self,
        rel_type: str,
        src_id: str,
        dst_id: str,
        basis: dict,
        *,
        role: str | None = None,
        premise_slot: str | None = None,
    ) -> str:
        rel = RelType(rel_type)
        self._check_basis(basis)
        if role not in (None, "necessary", "alternative"):
            raise RrlError("E_ROLE", "role must be necessary, alternative, or omitted")
        with self._tx():
            self._must_record(src_id)
            self._must_record(dst_id)
            src_proj = self._proj(src_id)
            if rel == RelType.SUPPORTS and src_proj["usage"] != Usage.SUPPORT.value:
                raise RrlError("E_USAGE_MISMATCH", "supports requires usage=support", src=src_id)
            if rel == RelType.CONTRADICTS and src_proj["usage"] != Usage.OPPOSE.value:
                raise RrlError("E_USAGE_MISMATCH", "contradicts requires usage=oppose", src=src_id)
            if rel == RelType.DEPENDS_ON and role == "alternative" and not premise_slot:
                raise RrlError("E_SLOT_REQUIRED", "an alternative premise needs a premise_slot")
            if rel == RelType.DEPENDS_ON and role is None:
                raise RrlError("E_ROLE", "depends_on requires role necessary or alternative")
            slot = premise_slot
            if rel == RelType.DEPENDS_ON and role == "necessary" and not slot:
                slot = f"sole:{dst_id}"
            relation_id = self._insert_relation(rel, src_id, dst_id, basis, role, slot)
            stale: set[str] = set()
            if rel == RelType.SUPERSEDES:
                self._mark_stale_in(dst_id, "superseded", {"superseded_by": src_id}, stale)
            if stale or rel in (RelType.SUPPORTS, RelType.CONTRADICTS, RelType.DEPENDS_ON):
                seeds = list(stale) if stale else [src_id, dst_id]
                self._fixpoint(self._claims_affected(seeds))
            return relation_id

    def mark_stale(self, entity_id: str, reason: str, details: dict | None = None) -> dict:
        if not isinstance(reason, str) or not reason.strip():
            raise RrlError("E_REASON", "a stale mark needs a reason")
        with self._tx():
            self._must_record(entity_id)
            stale: set[str] = set()
            self._mark_stale_in(entity_id, reason, details or {}, stale)
            self._fixpoint(self._claims_affected(list(stale)))
            return self.decision(entity_id) if self._kind(entity_id) == Kind.CLAIM.value else {"id": entity_id, "applicability": self._proj(entity_id)["applicability"]}

    def note_content_change(self, artifact_id: str, data: bytes) -> dict:
        digest = self.put_blob(data)
        record = self.get(artifact_id)
        if record["kind"] != Kind.ARTIFACT.value:
            raise RrlError("E_NOT_ARTIFACT", "content changes apply to artifacts", id=artifact_id)
        old = record["payload"].get("content_digest")
        if digest == old:
            return {"changed": False, "digest": digest, "stale": False}
        self.mark_stale(artifact_id, "content_digest_changed", {"old_digest": old, "new_digest": digest})
        return {"changed": True, "digest": digest, "stale": True}

    def retract(self, entity_id: str, reason: str, *, by: str = "operator") -> dict:
        if not isinstance(reason, str) or not reason.strip():
            raise RrlError("E_REASON", "a retraction needs a reason")
        with self._tx():
            self._must_record(entity_id)
            if self._proj(entity_id)["applicability"] == Applicability.RETRACTED.value:
                self._event("retraction_repeated", entity_id, {"reason": reason, "by": by})
                return {"status": "already_retracted", "id": entity_id, "deleted": False}
            retraction_id = self._insert_record(
                Kind.RETRACTION,
                {"target_id": entity_id, "reason": reason, "by": by},
                Provenance.OBSERVED,
                ExecutionResult.NOT_EXECUTED,
                Applicability.VALID,
                Usage.OPPOSE,
                dict(_LEDGER_SCOPE),
                f"retraction:{entity_id}:{uuid.uuid4().hex}",
            )
            self._set_proj_fields(entity_id, applicability=Applicability.RETRACTED.value)
            self._insert_relation(
                RelType.INVALIDATED_BY,
                entity_id,
                retraction_id,
                {"statement": reason, "method": "retraction", "by": by},
                None,
                None,
            )
            self._event("retracted", entity_id, {"reason": reason, "by": by, "retraction_id": retraction_id})
            self._fixpoint(self._claims_affected([entity_id, retraction_id]))
            return {"status": "retracted", "id": entity_id, "retraction_id": retraction_id, "deleted": False}

    def evaluate(self, claim_id: str) -> dict:
        with self._tx():
            analysis = self._analyze(claim_id)
            evaluation_id = self._apply_evaluation(claim_id, analysis, force=True)
            analysis["evaluation_id"] = evaluation_id
            return analysis

    def decision(self, claim_id: str) -> dict:
        with self._readlock():
            return self._analyze(claim_id)

    def get(self, entity_id: str) -> dict:
        with self._readlock():
            record = self._must_record(entity_id)
            projection = self._proj(entity_id)
            return {**record, "projection": projection}

    def list_records(self, kind: str | None = None) -> list[dict]:
        with self._readlock():
            if kind is None:
                rows = self._conn.execute("SELECT id FROM records ORDER BY created_at, id").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id FROM records WHERE kind=? ORDER BY created_at, id", (Kind(kind).value,)
                ).fetchall()
            return [self.get(row["id"]) for row in rows]

    def list_events(self) -> list[dict]:
        with self._readlock():
            rows = self._conn.execute("SELECT * FROM events ORDER BY seq").fetchall()
            return [
                {
                    "seq": row["seq"],
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "subject_id": row["subject_id"],
                    "payload": json.loads(row["payload_json"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def list_relations(self) -> list[dict]:
        with self._readlock():
            rows = self._conn.execute("SELECT * FROM relations ORDER BY created_at, id").fetchall()
            result = []
            for row in rows:
                result.append(
                    {
                        "id": row["id"],
                        "rel_type": row["rel_type"],
                        "src_id": row["src_id"],
                        "dst_id": row["dst_id"],
                        "role": row["role"],
                        "premise_slot": row["premise_slot"],
                        "basis": json.loads(row["basis_json"]),
                        "content_digest": row["content_digest"],
                        "projection": self._proj(row["id"]),
                    }
                )
            return result

    def cache_put(self, components: dict, result: bytes) -> dict:
        prepared = prepare_cache(components)
        digest = self.put_blob(result)
        with self._tx():
            self._conn.execute(
                """
                INSERT INTO cache_entries
                  (cache_key, components_json, env_complete, reusable, limitations_json, result_digest, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  components_json=excluded.components_json,
                  env_complete=excluded.env_complete,
                  reusable=excluded.reusable,
                  limitations_json=excluded.limitations_json,
                  result_digest=excluded.result_digest,
                  created_at=excluded.created_at
                """,
                (
                    prepared["key"],
                    canonical_dumps(prepared["components"]),
                    1 if prepared["components"]["env_complete"] else 0,
                    1 if prepared["reusable"] else 0,
                    canonical_dumps(prepared["limitations"]),
                    digest,
                    utcnow(),
                ),
            )
            self._event("cache_stored", None, {"cache_key": prepared["key"], "reusable": prepared["reusable"]})
        prepared["result_digest"] = digest
        return prepared

    def cache_get(self, components: dict) -> dict:
        prepared = prepare_cache(components)
        if not prepared["reusable"]:
            return {
                "hit": False,
                "reason": "conservative_invalidation",
                "cache_key": prepared["key"],
                "limitations": prepared["limitations"],
            }
        with self._readlock():
            row = self._conn.execute(
                "SELECT * FROM cache_entries WHERE cache_key=?", (prepared["key"],)
            ).fetchone()
            if row is None or not row["reusable"]:
                cached = None
            else:
                cached = {
                    "digest": row["result_digest"],
                    "limitations": json.loads(row["limitations_json"]),
                }
        if cached is None:
            return {
                "hit": False,
                "reason": "miss",
                "cache_key": prepared["key"],
                "limitations": prepared["limitations"],
            }
        return {
            "hit": True,
            "reason": "content_bound_hit",
            "cache_key": prepared["key"],
            "result": self.get_blob(cached["digest"]),
            "limitations": cached["limitations"],
        }

    def audit_tree(self, root: str | Path, declared_third_party: set[str] | None = None) -> dict:
        return audit_python_tree(Path(root), declared_third_party)

    def status_summary(self) -> dict:
        with self._readlock():
            return self._status_summary()

    def _status_summary(self) -> dict:
        counts: dict[str, int] = {}
        for row in self._conn.execute("SELECT kind, COUNT(*) AS n FROM records GROUP BY kind"):
            counts[row["kind"]] = row["n"]
        claims = []
        for record in self.list_records(Kind.CLAIM.value):
            claims.append(
                {
                    "id": record["id"],
                    "statement": record["payload"].get("statement"),
                    "accepted_pass": bool(record["projection"]["extra"].get("accepted_pass")),
                    "execution_result": record["projection"]["execution_result"],
                    "applicability": record["projection"]["applicability"],
                    "support_status": record["projection"]["support_status"],
                    "independent_support_count": record["projection"]["independent_support_count"],
                    "provenance": record["projection"]["provenance"],
                    "usage": record["projection"]["usage"],
                }
            )
        return {
            "note": "Command completion is not a verification pass. accepted_pass is scoped to the recorded inputs, behaviors, and environment.",
            "record_counts": counts,
            "claims": claims,
            "tasks": self.list_tasks(),
        }

    def verify_integrity(self) -> None:
        with self._readlock():
            self._verify_integrity()

    def _verify_integrity(self) -> None:
        record_ids = {row["id"] for row in self._conn.execute("SELECT id FROM records")}
        proj_ids = {row["entity_id"] for row in self._conn.execute("SELECT entity_id FROM proj")}
        relation_ids = {row["id"] for row in self._conn.execute("SELECT id FROM relations")}
        if not record_ids <= proj_ids or not relation_ids <= proj_ids:
            raise RrlError("E_INTEGRITY", "projection missing for a record or relation")
        sequences = [row["seq"] for row in self._conn.execute("SELECT seq FROM events ORDER BY seq")]
        if sequences != list(range(1, len(sequences) + 1)):
            raise RrlError("E_INTEGRITY", "event sequence has a gap")
        for digest_row in self._conn.execute("SELECT result_digest FROM cache_entries WHERE result_digest IS NOT NULL"):
            self.get_blob(digest_row["result_digest"])
        for record_id in sorted(record_ids):
            path_digest = json.loads(self._conn.execute("SELECT payload_json, content_digest FROM records WHERE id=?", (record_id,)).fetchone()["payload_json"])
            stored = self._conn.execute("SELECT content_digest, payload_json FROM records WHERE id=?", (record_id,)).fetchone()
            if digest_obj(json.loads(stored["payload_json"])) != stored["content_digest"]:
                raise RrlError("E_INTEGRITY", "record digest does not match payload", id=record_id)
            del path_digest
            kind = self._kind(record_id)
            projection = self._proj(record_id)
            accepted = bool(projection["extra"].get("accepted_pass"))
            if kind == Kind.CLAIM.value:
                live = self._analyze(record_id)
                if self._analysis_signature(live) != self._signature(record_id):
                    raise RrlError("E_INTEGRITY", "claim projection does not match recomputed support", id=record_id)
                if accepted:
                    if not (
                        projection["execution_result"] == ExecutionResult.PASSED.value
                        and projection["applicability"] == Applicability.VALID.value
                        and projection["support_status"] == SupportStatus.SUPPORTED.value
                        and projection["independent_support_count"] >= 1
                    ):
                        raise RrlError("E_INTEGRITY", "accepted pass is missing a required dimension", id=record_id)
                if projection["applicability"] != Applicability.VALID.value and accepted:
                    raise RrlError("E_INTEGRITY", "non-applicable claim is marked accepted", id=record_id)
                latest = projection["extra"].get("latest_evaluation_id")
                if latest:
                    if self._proj(latest)["applicability"] != Applicability.VALID.value:
                        raise RrlError("E_INTEGRITY", "current evaluation is not applicable", id=latest)
                    if record_id in (json.loads(self._conn.execute("SELECT payload_json FROM records WHERE id=?", (latest,)).fetchone()["payload_json"]).get("positive_support_ids") or []):
                        raise RrlError("E_INTEGRITY", "evaluation supports itself", id=latest)
            if "content_digest" in (self._must_record(record_id)["payload"]):
                digest = self._must_record(record_id)["payload"].get("content_digest")
                if isinstance(digest, str) and digest:
                    self.get_blob(digest)

    # --- tasks -----------------------------------------------------------------

    def submit_task(
        self,
        *,
        task_id: str,
        handler: str,
        deps: list[str],
        owner: str,
        inputs_version: str,
        timeout_seconds: float,
        max_attempts: int,
        resource_class: str,
        budget: dict | None = None,
        workspace: str | None = None,
    ) -> dict:
        if not task_id or not handler:
            raise RrlError("E_TASK", "task id and handler are required")
        if max_attempts < 1:
            raise RrlError("E_TASK", "max_attempts must be at least 1")
        if timeout_seconds <= 0:
            raise RrlError("E_TASK", "timeout_seconds must be positive")
        resource = ResourceClass(resource_class)
        with self._tx():
            if self._conn.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
                raise RrlError("E_TASK_EXISTS", "task id already exists", id=task_id)
            for dep in deps:
                if not self._conn.execute("SELECT 1 FROM tasks WHERE id=?", (dep,)).fetchone():
                    raise RrlError("E_DEPENDENCY_MISSING", "dependency task does not exist", dependency=dep)
            state, reason = self._dependency_state(deps)
            self._conn.execute(
                """
                INSERT INTO tasks (
                  id, state, owner, handler, inputs_version, deps_json, workspace, budget_json,
                  resource_class, timeout_seconds, max_attempts, attempts, exit_status, failure_class,
                  blocked_reason, artifact_json, evidence_ids_json, cancel_requested, log_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 'none', ?, '[]', '[]', 0, '[]')
                """,
                (
                    task_id,
                    state,
                    owner,
                    handler,
                    inputs_version,
                    canonical_dumps(list(deps)),
                    workspace,
                    canonical_dumps(budget or {}),
                    resource.value,
                    float(timeout_seconds),
                    int(max_attempts),
                    reason,
                ),
            )
            self._event("task_transition", task_id, {"to": state, "reason": reason, "attempt": 0})
        return self.get_task(task_id)

    def refresh_tasks(self) -> list[dict]:
        with self._tx():
            rows = self._conn.execute("SELECT * FROM tasks").fetchall()
            for row in rows:
                if row["state"] != TaskState.BLOCKED.value:
                    continue
                deps = json.loads(row["deps_json"])
                state, reason = self._dependency_state(deps)
                if state != row["state"] or reason != row["blocked_reason"]:
                    self._conn.execute(
                        "UPDATE tasks SET state=?, blocked_reason=? WHERE id=?",
                        (state, reason, row["id"]),
                    )
                    self._event("task_transition", row["id"], {"from": row["state"], "to": state, "reason": reason})
            return self.list_tasks()

    def list_tasks(self) -> list[dict]:
        with self._readlock():
            return [self._task_dict(row) for row in self._conn.execute("SELECT * FROM tasks ORDER BY id")]

    def get_task(self, task_id: str) -> dict:
        with self._readlock():
            row = self._conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise RrlError("E_NOT_FOUND", "task not found", id=task_id)
            return self._task_dict(row)

    def begin_attempt(self, task_id: str) -> dict:
        with self._tx():
            row = self._task_row(task_id)
            if row["state"] != TaskState.QUEUED.value:
                raise RrlError("E_TASK_STATE", "only a queued task can start", state=row["state"])
            if row["attempts"] >= row["max_attempts"]:
                raise RrlError("E_TASK_BUDGET", "attempt budget is exhausted")
            attempts = row["attempts"] + 1
            self._conn.execute(
                """
                UPDATE tasks
                   SET state=?, attempts=?, started_at=?, ended_at=NULL, exit_status=NULL,
                       blocked_reason=NULL
                 WHERE id=?
                """,
                (TaskState.RUNNING.value, attempts, utcnow(), task_id),
            )
            self._event("task_transition", task_id, {"from": row["state"], "to": "RUNNING", "attempt": attempts})
            # Read the row in this transaction. The lock is still held, so the
            # snapshot matches the update that commit publishes on the way out.
            return self._task_dict(self._task_row(task_id))

    def set_checkpoint(self, task_id: str, checkpoint: dict) -> None:
        with self._tx():
            self._task_row(task_id)
            self._conn.execute(
                "UPDATE tasks SET checkpoint_json=? WHERE id=?",
                (canonical_dumps(checkpoint), task_id),
            )
            self._event("task_checkpoint", task_id, {"checkpoint": checkpoint})

    def publish_success(self, task_id: str, result: dict) -> str:
        with self._tx():
            row = self._task_row(task_id)
            if row["state"] != TaskState.RUNNING.value:
                return row["state"]
            if row["cancel_requested"]:
                self._finish_task(row, TaskState.CANCELLED.value, "cancelled", "none", {"cancelled_before_publish": True})
                return TaskState.CANCELLED.value
            self._finish_task(row, TaskState.SUCCEEDED.value, "ok", "none", result)
            return TaskState.SUCCEEDED.value

    def publish_failure(self, task_id: str, failure_class: str, message: str) -> str:
        if failure_class not in ("infra", "deterministic"):
            raise RrlError("E_FAILURE_CLASS", "failure class must be infra or deterministic")
        with self._tx():
            row = self._task_row(task_id)
            if row["state"] != TaskState.RUNNING.value:
                return row["state"]
            if row["cancel_requested"]:
                self._finish_task(row, TaskState.CANCELLED.value, "cancelled", "none", {"message": message})
                return TaskState.CANCELLED.value
            if failure_class == "deterministic":
                self._finish_task(row, TaskState.FAILED.value, "deterministic", "deterministic", {"message": message})
                return TaskState.FAILED.value
            if row["attempts"] < row["max_attempts"]:
                self._conn.execute(
                    "UPDATE tasks SET state=?, failure_class=?, exit_status=?, ended_at=? WHERE id=?",
                    (TaskState.QUEUED.value, "infra", "infra", utcnow(), task_id),
                )
                self._append_log(task_id, {"event": "infra_retry", "message": message, "attempt": row["attempts"]})
                self._event("task_transition", task_id, {"from": "RUNNING", "to": "QUEUED", "failure_class": "infra", "message": message})
                return TaskState.QUEUED.value
            self._finish_task(row, TaskState.FAILED.value, "infra", "infra", {"message": message})
            return TaskState.FAILED.value

    def request_cancel(self, task_id: str) -> str:
        with self._tx():
            row = self._task_row(task_id)
            if row["state"] in (TaskState.SUCCEEDED.value, TaskState.FAILED.value, TaskState.CANCELLED.value):
                self._append_log(task_id, {"event": "cancel_ignored", "state": row["state"]})
                return row["state"]
            if row["state"] in (TaskState.QUEUED.value, TaskState.BLOCKED.value):
                self._finish_task(row, TaskState.CANCELLED.value, "cancelled", "none", {"when": "before_start"})
                return TaskState.CANCELLED.value
            self._conn.execute("UPDATE tasks SET cancel_requested=1 WHERE id=?", (task_id,))
            self._append_log(task_id, {"event": "cancel_requested"})
            self._event("task_cancel_requested", task_id, {})
            return TaskState.RUNNING.value

    def finalize_if_still_running(self, task_id: str, reason: str) -> str:
        """Timeout or kill. Does not overwrite a commit that already published success or cancel."""
        with self._tx():
            row = self._task_row(task_id)
            if row["state"] != TaskState.RUNNING.value:
                return row["state"]
            if row["cancel_requested"] or reason == "cancelled":
                self._finish_task(row, TaskState.CANCELLED.value, "cancelled", "none", {"reason": reason})
                return TaskState.CANCELLED.value
            if row["attempts"] < row["max_attempts"]:
                self._conn.execute(
                    "UPDATE tasks SET state=?, failure_class='infra', exit_status=?, ended_at=? WHERE id=?",
                    (TaskState.QUEUED.value, reason, utcnow(), task_id),
                )
                self._append_log(task_id, {"event": reason, "retry": True})
                self._event("task_transition", task_id, {"from": "RUNNING", "to": "QUEUED", "reason": reason})
                return TaskState.QUEUED.value
            self._finish_task(row, TaskState.FAILED.value, reason, "infra", {"reason": reason})
            return TaskState.FAILED.value

    def recover_running(self) -> list[dict]:
        actions = []
        with self._tx():
            rows = self._conn.execute("SELECT * FROM tasks WHERE state=?", (TaskState.RUNNING.value,)).fetchall()
            for row in rows:
                if row["cancel_requested"]:
                    new_state = TaskState.CANCELLED.value
                    self._finish_task(row, new_state, "cancelled", "none", {"recovered": True})
                elif row["attempts"] < row["max_attempts"]:
                    new_state = TaskState.QUEUED.value
                    self._conn.execute(
                        "UPDATE tasks SET state=?, failure_class='infra', exit_status='interrupted', ended_at=? WHERE id=?",
                        (new_state, utcnow(), row["id"]),
                    )
                    self._event("task_transition", row["id"], {"from": "RUNNING", "to": "QUEUED", "reason": "interrupted"})
                else:
                    new_state = TaskState.FAILED.value
                    self._finish_task(row, new_state, "interrupted", "infra", {"recovered": True})
                actions.append({"id": row["id"], "to": new_state, "accepted_pass": False})
        return actions

    # --- internals -------------------------------------------------------------

    def _validate_new(self, kind, payload, provenance, execution_result, applicability, usage, verification_scope):
        if not isinstance(payload, dict):
            raise RrlError("E_PAYLOAD", "payload must be an object")
        kind_e = Kind(kind)
        prov = Provenance(provenance)
        result = ExecutionResult(execution_result)
        applic = Applicability(applicability)
        use = Usage(usage)
        if not isinstance(verification_scope, dict):
            raise RrlError("E_SCOPE", "verification_scope must be an object")
        if kind_e in (Kind.EVALUATION, Kind.RETRACTION):
            raise RrlError("E_RESERVED_KIND", "this kind is created only by evaluate or retract", kind=kind_e.value)
        adjustments: list[str] = []
        if payload.get("truncated"):
            if applic == Applicability.VALID:
                applic = Applicability.INCOMPLETE_SCOPE
                adjustments.append("truncated_forces_incomplete_scope")
        if prov == Provenance.MODEL_GENERATED and result == ExecutionResult.PASSED:
            raise RrlError("E_MODEL_NOT_EXECUTION", "model-generated text cannot be recorded as an execution pass")
        if kind_e in (Kind.REQUIREMENT, Kind.CLAIM, Kind.HYPOTHESIS, Kind.CANDIDATE, Kind.ATTRIBUTION):
            if result != ExecutionResult.NOT_EXECUTED:
                raise RrlError("E_RESULT_NOT_DECLARABLE", "this kind cannot be inserted as an execution result", kind=kind_e.value)
        if kind_e == Kind.CLAIM and not isinstance(payload.get("statement"), str):
            raise RrlError("E_CLAIM", "a claim needs a statement")
        if kind_e == Kind.CLAIM and "required_scope" not in payload:
            raise RrlError("E_SCOPE", "a claim needs required_scope, which may still be too empty to pass")
        if kind_e == Kind.ATTRIBUTION:
            self._validate_attribution(payload)
        if kind_e == Kind.OBSERVATION and result == ExecutionResult.PASSED:
            self._require_consistent_run(payload, prov)
        if result == ExecutionResult.PASSED and applic != Applicability.VALID:
            # A partial or stale observation may describe a successful exit, but it is not
            # inserted as a clean pass. Callers record uncertain or failed instead, or a
            # passed result only with applicability valid. Truncation already forced incomplete.
            if not payload.get("truncated"):
                raise RrlError(
                    "E_PASS_APPLICABILITY",
                    "execution passed cannot be combined with a non-valid applicability at insertion",
                    applicability=applic.value,
                )
            result = ExecutionResult.UNCERTAIN
            adjustments.append("truncated_pass_demoted_to_uncertain")
        if kind_e == Kind.ARTIFACT:
            digest = payload.get("content_digest")
            if not isinstance(digest, str):
                raise RrlError("E_ARTIFACT", "artifact payload needs content_digest")
            self.get_blob(digest)
        payload = dict(payload)
        if adjustments:
            payload["adjustments"] = adjustments
        return kind_e, prov, result, applic, use, verification_scope, payload

    def _require_consistent_run(self, payload: dict, provenance: Provenance) -> None:
        key = "run" if provenance == Provenance.OBSERVED else "external_run"
        run = payload.get(key)
        if not isinstance(run, dict):
            raise RrlError("E_RUN_UNBOUND", f"a passed {provenance.value} observation needs {key}")
        if run.get("exit_code") != 0 or run.get("observed_status") != "passed":
            raise RrlError("E_INCONSISTENT_RUN", "passed observations require exit_code 0 and observed_status passed")
        if "command" not in run:
            raise RrlError("E_RUN_UNBOUND", "run.command is required")
        if provenance == Provenance.IMPORTED and not isinstance(run.get("environment"), dict):
            raise RrlError("E_IMPORT_UNBOUND", "imported passes need external_run.environment")

    def _validate_attribution(self, payload: dict) -> None:
        value = payload.get("value_function")
        if not isinstance(value, dict):
            raise RrlError("E_VALUE_FUNCTION", "attribution requires an explicit value_function")
        for key in ("argument", "baseline", "direction", "measured", "missing_value", "confounders"):
            if key not in value:
                raise RrlError("E_VALUE_FUNCTION", f"value_function.{key} is required")
        if value.get("measured") is True and not payload.get("experiment_id"):
            raise RrlError("E_VALUE_FUNCTION", "a measured attribution must name the experiment")
        if "contribution_percent" in payload or "contribution_percent" in value:
            raise RrlError("E_VALUE_FUNCTION", "an undefined contribution percent is rejected")

    def _insert_record(self, kind, payload, provenance, execution_result, applicability, usage, scope, source_family):
        record_id = uuid.uuid4().hex
        family = source_family or record_id
        body = dict(payload)
        body["dimensions_at_creation"] = {
            "provenance": provenance.value,
            "execution_result": execution_result.value,
            "applicability": applicability.value,
            "usage": usage.value,
            "verification_scope": scope,
            "source_family": family,
        }
        encoded = canonical_dumps(body)
        created = utcnow()
        self._conn.execute(
            "INSERT INTO records (id, kind, content_digest, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (record_id, kind.value, digest_obj(body), encoded, created),
        )
        extra = {"accepted_pass": False}
        support_status = SupportStatus.NOT_APPLICABLE.value
        independent = 0
        if kind == Kind.CLAIM:
            support_status = SupportStatus.UNSUPPORTED.value
        self._conn.execute(
            """
            INSERT INTO proj (
              entity_id, entity_kind, provenance, execution_result, applicability, usage,
              verification_scope_json, support_status, independent_support_count, source_family,
              extra_json, updated_seq
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                kind.value,
                provenance.value,
                execution_result.value,
                applicability.value,
                usage.value,
                canonical_dumps(scope),
                support_status,
                independent,
                family,
                canonical_dumps(extra),
                self._last_seq(),
            ),
        )
        self._event("record_added", record_id, {"kind": kind.value, "content_digest": digest_obj(body)})
        return record_id

    def _insert_relation(self, rel, src, dst, basis, role, slot) -> str:
        relation_id = uuid.uuid4().hex
        body = {
            "rel_type": rel.value,
            "src_id": src,
            "dst_id": dst,
            "role": role,
            "premise_slot": slot,
            "basis": basis,
        }
        self._conn.execute(
            """
            INSERT INTO relations (
              id, rel_type, src_id, dst_id, role, premise_slot, basis_json, content_digest, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                rel.value,
                src,
                dst,
                role,
                slot,
                canonical_dumps(basis),
                digest_obj(body),
                utcnow(),
            ),
        )
        self._conn.execute(
            """
            INSERT INTO proj (
              entity_id, entity_kind, provenance, execution_result, applicability, usage,
              verification_scope_json, support_status, independent_support_count, source_family,
              extra_json, updated_seq
            ) VALUES (?, 'relation', 'observed', 'not_executed', 'valid', 'background', ?, 'not_applicable', 0, ?, '{}', ?)
            """,
            (relation_id, canonical_dumps(_LEDGER_SCOPE), relation_id, self._last_seq()),
        )
        self._event("relation_added", relation_id, body)
        return relation_id

    def _check_basis(self, basis: dict) -> None:
        if not isinstance(basis, dict):
            raise RrlError("E_BASIS_REQUIRED", "relation basis must be an object")
        if basis.get("method") == "name_similarity":
            raise RrlError("E_SIMILARITY_NOT_COVERAGE", "name similarity is not semantic coverage")
        statement = basis.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            raise RrlError("E_BASIS_REQUIRED", "basis.statement is required")

    def _mark_stale_in(self, entity_id: str, reason: str, details: dict, seen: set[str]) -> None:
        if entity_id in seen:
            return
        seen.add(entity_id)
        if self._conn.execute("SELECT 1 FROM records WHERE id=?", (entity_id,)).fetchone() is None:
            return
        projection = self._proj(entity_id)
        if projection["applicability"] == Applicability.RETRACTED.value:
            self._event("stale_ignored_retracted", entity_id, {"reason": reason})
            return
        if projection["applicability"] == Applicability.STALE.value:
            self._event("stale_repeated", entity_id, {"reason": reason, **details})
            return
        self._set_proj_fields(entity_id, applicability=Applicability.STALE.value)
        self._event("marked_stale", entity_id, {"reason": reason, **details})
        for relation in self._rels(dst=entity_id, rel_type=RelType.DERIVED_FROM.value):
            self._mark_stale_in(relation["src_id"], "upstream_stale", {"upstream": entity_id}, seen)

    def _set_proj_fields(self, entity_id: str, **fields: Any) -> None:
        current = self._proj(entity_id)
        extra = dict(current["extra"])
        column_map = {
            "applicability": "applicability",
            "execution_result": "execution_result",
            "support_status": "support_status",
            "independent_support_count": "independent_support_count",
            "usage": "usage",
            "provenance": "provenance",
        }
        assignments = []
        values: list[Any] = []
        for key, column in column_map.items():
            if key in fields:
                assignments.append(f"{column}=?")
                values.append(fields[key])
        if "extra" in fields:
            extra.update(fields["extra"])
        if "accepted_pass" in fields:
            extra["accepted_pass"] = bool(fields["accepted_pass"])
        if "latest_evaluation_id" in fields:
            extra["latest_evaluation_id"] = fields["latest_evaluation_id"]
        assignments.append("extra_json=?")
        values.append(canonical_dumps(extra))
        assignments.append("updated_seq=?")
        values.append(self._last_seq())
        values.append(entity_id)
        self._conn.execute(f"UPDATE proj SET {', '.join(assignments)} WHERE entity_id=?", values)
        self._family_retracted_cache.pop(current["source_family"], None)
        self._proj_cache.pop(entity_id, None)

    def _analyze(self, claim_id: str) -> dict:
        record = self._must_record(claim_id)
        if record["kind"] != Kind.CLAIM.value:
            raise RrlError("E_NOT_A_CLAIM", "only a claim has a support decision", id=claim_id)
        projection = self._proj(claim_id)
        required = record["payload"].get("required_scope") or {}
        explicit = scope_explicit(required)
        excluded: list[dict] = []
        positive: list[dict] = []
        counters: list[str] = []
        uncertain_counters: list[str] = []
        if projection["applicability"] == Applicability.RETRACTED.value:
            return self._decision_dict(
                claim_id,
                ExecutionResult.UNCERTAIN.value,
                Applicability.RETRACTED.value,
                SupportStatus.DOWNGRADED.value,
                0,
                False,
                [{"id": claim_id, "reason": "claim_retracted"}],
                [],
                [],
                [],
                ["a retracted claim is not a current pass"],
                None,
            )
        for relation in self._rels(dst=claim_id, rel_type=RelType.SUPPORTS.value):
            blocker = self._positive_blocker(relation["src_id"], required, explicit)
            if blocker is None:
                positive.append(self._proj(relation["src_id"]))
            else:
                excluded.append({"id": relation["src_id"], "reason": blocker})
        for relation in self._rels(dst=claim_id, rel_type=RelType.CONTRADICTS.value):
            src = self._proj(relation["src_id"])
            raw = self._must_record(relation["src_id"])
            if src["applicability"] != Applicability.VALID.value:
                excluded.append({"id": relation["src_id"], "reason": f"counter_{src['applicability']}"})
                continue
            if raw["payload"].get("truncated"):
                uncertain_counters.append(relation["src_id"])
                excluded.append({"id": relation["src_id"], "reason": "counter_truncated"})
                continue
            if src["execution_result"] == ExecutionResult.PASSED.value and src["usage"] == Usage.OPPOSE.value:
                counters.append(relation["src_id"])
            elif src["execution_result"] in (ExecutionResult.UNCERTAIN.value, ExecutionResult.NOT_EXECUTED.value):
                uncertain_counters.append(relation["src_id"])
            else:
                excluded.append({"id": relation["src_id"], "reason": f"counter_{src['execution_result']}"})
        families: dict[str, str] = {}
        for src in positive:
            families.setdefault(src["source_family"], src["entity_id"])
        missing_slots = self._missing_necessary(claim_id)
        notes = ["a matching finite scope is not equivalence on all inputs"]
        failure_scope = None
        if not explicit:
            notes.append("required_scope does not list inputs, behaviors, and environments")
        if counters:
            execution = ExecutionResult.FAILED.value
            status = SupportStatus.CONTESTED.value
            applicability = Applicability.VALID.value
            accepted = False
            failure_scope = [self._proj(item)["verification_scope"] for item in counters]
            notes.append("counterevidence rejects a pass inside the counterevidence scope only")
        elif missing_slots or not explicit:
            execution = ExecutionResult.UNCERTAIN.value
            status = SupportStatus.DOWNGRADED.value if missing_slots else SupportStatus.INSUFFICIENT.value
            applicability = Applicability.INCOMPLETE_SCOPE.value
            accepted = False
            if missing_slots:
                notes.append("a necessary premise has no remaining valid filler")
        elif uncertain_counters:
            execution = ExecutionResult.UNCERTAIN.value
            status = SupportStatus.CONTESTED.value
            applicability = Applicability.INCOMPLETE_SCOPE.value
            accepted = False
            notes.append("unresolved counterevidence blocks a pass")
        elif families:
            execution = ExecutionResult.PASSED.value
            status = SupportStatus.SUPPORTED.value
            applicability = Applicability.VALID.value
            accepted = True
        else:
            reasons = {item["reason"] for item in excluded}
            if "failed" in reasons:
                execution = ExecutionResult.FAILED.value
                status = SupportStatus.UNSUPPORTED.value
                applicability = Applicability.VALID.value
            elif not excluded:
                execution = ExecutionResult.NOT_EXECUTED.value
                status = SupportStatus.UNSUPPORTED.value
                applicability = Applicability.VALID.value
            elif reasons & {"uncertain", "not_executed", "truncated", "scope_mismatch", "incomplete_scope", "stale", "retracted"} or any(
                "truncated" in reason or "scope" in reason for reason in reasons
            ):
                execution = ExecutionResult.NOT_EXECUTED.value if reasons <= {"not_executed"} else ExecutionResult.UNCERTAIN.value
                status = SupportStatus.INSUFFICIENT.value if execution == ExecutionResult.UNCERTAIN.value else SupportStatus.UNSUPPORTED.value
                applicability = (
                    Applicability.INCOMPLETE_SCOPE.value
                    if any(token in reason for reason in reasons for token in ("truncated", "scope", "incomplete", "stale"))
                    else Applicability.VALID.value
                )
            else:
                execution = ExecutionResult.UNCERTAIN.value
                status = SupportStatus.UNSUPPORTED.value
                applicability = Applicability.VALID.value
            accepted = False
        if projection["applicability"] == Applicability.STALE.value:
            applicability = Applicability.STALE.value
            accepted = False
            if execution == ExecutionResult.PASSED.value:
                execution = ExecutionResult.UNCERTAIN.value
            notes.append("a stale claim is not a current pass")
        positive_ids = sorted(src["entity_id"] for src in positive)
        family_names = sorted(families)
        counters = sorted(counters)
        return self._decision_dict(
            claim_id,
            execution,
            applicability,
            status,
            len(family_names) if positive_ids else 0,
            accepted,
            excluded,
            positive_ids,
            counters,
            family_names,
            notes,
            failure_scope,
        )

    def _decision_dict(self, claim_id, execution, applicability, status, independent, accepted, excluded, positive_ids, counters, families, notes, failure_scope):
        return {
            "claim_id": claim_id,
            "execution_result": execution,
            "applicability": applicability,
            "support_status": status,
            "independent_support_count": independent,
            "accepted_pass": bool(accepted),
            "excluded": excluded,
            "positive_support_ids": positive_ids,
            "counter_ids": counters,
            "source_families": families,
            "notes": notes,
            "failure_scope": failure_scope,
            "not_universal": True,
        }

    def _positive_blocker(self, evidence_id: str, required: dict, explicit: bool) -> str | None:
        src = self._proj(evidence_id)
        raw = self._must_record(evidence_id)
        if raw["payload"].get("truncated"):
            return "truncated"
        if src["applicability"] != Applicability.VALID.value:
            return src["applicability"]
        if src["usage"] != Usage.SUPPORT.value:
            return f"usage_{src['usage']}"
        if src["provenance"] == Provenance.MODEL_GENERATED.value:
            return "model_generated"
        if self._family_retracted(src["source_family"]):
            return "source_family_retracted"
        if src["execution_result"] != ExecutionResult.PASSED.value:
            return src["execution_result"]
        if not explicit:
            return "required_scope_not_explicit"
        if not scope_covers(src["verification_scope"], required):
            return "scope_mismatch"
        return None

    def _missing_necessary(self, claim_id: str) -> list[str]:
        slots: dict[str, list[dict]] = {}
        for relation in self._rels(src=claim_id, rel_type=RelType.DEPENDS_ON.value):
            slot = relation["premise_slot"] or f"sole:{relation['dst_id']}"
            slots.setdefault(slot, []).append(relation)
        missing = []
        for slot, relations in slots.items():
            if not any(item["role"] == "necessary" for item in relations):
                continue
            if not any(self._premise_ok(item["dst_id"]) for item in relations):
                missing.append(slot)
        return missing

    def _family_retracted(self, family: str) -> bool:
        cached = self._family_retracted_cache.get(family)
        if cached is not None:
            return cached
        row = self._conn.execute(
            """
            SELECT 1 FROM proj
            WHERE source_family=? AND applicability=?
              AND entity_kind NOT IN ('retraction', 'evaluation')
            LIMIT 1
            """,
            (family, Applicability.RETRACTED.value),
        ).fetchone()
        value = row is not None
        self._family_retracted_cache[family] = value
        return value

    def _premise_ok(self, evidence_id: str) -> bool:
        src = self._proj(evidence_id)
        raw = self._must_record(evidence_id)
        if src["applicability"] != Applicability.VALID.value or raw["payload"].get("truncated"):
            return False
        if src["provenance"] == Provenance.MODEL_GENERATED.value:
            return False
        if self._family_retracted(src["source_family"]):
            return False
        if raw["kind"] == Kind.CLAIM.value:
            return bool(src["extra"].get("accepted_pass")) and src["execution_result"] == ExecutionResult.PASSED.value
        return src["execution_result"] == ExecutionResult.PASSED.value

    def _fixpoint(self, claim_ids: list[str]) -> None:
        unique = []
        for claim_id in claim_ids:
            if claim_id not in unique and self._kind_or_none(claim_id) == Kind.CLAIM.value:
                unique.append(claim_id)
        if not unique:
            return
        for _ in range(len(unique) + 2):
            changed = False
            for claim_id in unique:
                before = self._signature(claim_id)
                analysis = self._analyze(claim_id)
                if self._analysis_signature(analysis) != before:
                    self._apply_evaluation(claim_id, analysis, force=False)
                    changed = True
            if not changed:
                return
        raise RrlError("E_EVAL_UNSTABLE", "support reevaluation did not converge")

    def _apply_evaluation(self, claim_id: str, analysis: dict, *, force: bool) -> str:
        current = self._proj(claim_id)
        previous = current["extra"].get("latest_evaluation_id")
        if previous:
            self._set_proj_fields(previous, applicability=Applicability.STALE.value)
        evaluation_id = uuid.uuid4().hex
        payload = {
            "claim_id": claim_id,
            "accepted_pass": analysis["accepted_pass"],
            "execution_result": analysis["execution_result"],
            "applicability": analysis["applicability"],
            "support_status": analysis["support_status"],
            "independent_support_count": analysis["independent_support_count"],
            "positive_support_ids": analysis["positive_support_ids"],
            "excluded": analysis["excluded"],
            "counter_ids": analysis["counter_ids"],
            "source_families": analysis["source_families"],
            "notes": analysis["notes"],
            "failure_scope": analysis["failure_scope"],
            "not_universal": True,
            "forced": force,
        }
        body = dict(payload)
        body["dimensions_at_creation"] = {
            "provenance": Provenance.OBSERVED.value,
            "execution_result": analysis["execution_result"],
            "applicability": Applicability.VALID.value,
            "usage": Usage.BACKGROUND.value,
            "verification_scope": _LEDGER_SCOPE,
            "source_family": f"evaluation:{evaluation_id}",
        }
        self._conn.execute(
            "INSERT INTO records (id, kind, content_digest, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (evaluation_id, Kind.EVALUATION.value, digest_obj(body), canonical_dumps(body), utcnow()),
        )
        self._conn.execute(
            """
            INSERT INTO proj (
              entity_id, entity_kind, provenance, execution_result, applicability, usage,
              verification_scope_json, support_status, independent_support_count, source_family,
              extra_json, updated_seq
            ) VALUES (?, 'evaluation', 'observed', ?, 'valid', 'background', ?, 'not_applicable', ?, ?, '{}', ?)
            """,
            (
                evaluation_id,
                analysis["execution_result"],
                canonical_dumps(_LEDGER_SCOPE),
                analysis["independent_support_count"],
                f"evaluation:{evaluation_id}",
                self._last_seq(),
            ),
        )
        self._event("evaluated", claim_id, {"evaluation_id": evaluation_id, "accepted_pass": analysis["accepted_pass"]})
        self._set_proj_fields(
            claim_id,
            execution_result=analysis["execution_result"],
            applicability=analysis["applicability"],
            support_status=analysis["support_status"],
            independent_support_count=analysis["independent_support_count"],
            accepted_pass=analysis["accepted_pass"],
            latest_evaluation_id=evaluation_id,
            extra={
                "positive_support_ids": list(analysis["positive_support_ids"]),
                "counter_ids": list(analysis["counter_ids"]),
            },
        )
        return evaluation_id

    def _signature(self, claim_id: str) -> tuple:
        projection = self._proj(claim_id)
        extra = projection["extra"]
        return (
            projection["execution_result"],
            projection["applicability"],
            projection["support_status"],
            projection["independent_support_count"],
            bool(extra.get("accepted_pass")),
            tuple(extra.get("positive_support_ids") or []),
            tuple(extra.get("counter_ids") or []),
        )

    def _analysis_signature(self, analysis: dict) -> tuple:
        return (
            analysis["execution_result"],
            analysis["applicability"],
            analysis["support_status"],
            analysis["independent_support_count"],
            bool(analysis["accepted_pass"]),
            tuple(analysis["positive_support_ids"]),
            tuple(analysis["counter_ids"]),
        )

    def _claims_affected(self, seeds: list[str]) -> list[str]:
        """Claims whose stored decision can change because one of ``seeds`` changed.

        A claim reads an entity when that entity supports or contradicts the
        claim, or when the claim depends on that entity. Dependents of those
        claims are included. ``derived_from`` is not a decision edge: staleness
        walks it first and the caller passes every id that walk marked.
        """
        pending = list(seeds)
        seen: set[str] = set()
        claims: list[str] = []
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            if self._kind_or_none(node) == Kind.CLAIM.value and node not in claims:
                claims.append(node)
            pending.extend(self._decision_readers(node))
        return sorted(claims)

    def _decision_readers(self, entity_id: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT dst_id AS claim_id FROM relations
            WHERE src_id=? AND rel_type IN ('supports', 'contradicts')
            UNION
            SELECT src_id AS claim_id FROM relations
            WHERE dst_id=? AND rel_type='depends_on'
            """,
            (entity_id, entity_id),
        ).fetchall()
        return [row["claim_id"] for row in rows]

    def _rels(self, *, src: str | None = None, dst: str | None = None, rel_type: str | None = None) -> list[dict]:
        clauses = []
        values: list[str] = []
        if src is not None:
            clauses.append("src_id=?")
            values.append(src)
        if dst is not None:
            clauses.append("dst_id=?")
            values.append(dst)
        if rel_type is not None:
            clauses.append("rel_type=?")
            values.append(rel_type)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self._conn.execute(f"SELECT * FROM relations WHERE {where}", values).fetchall()
        return [dict(row) for row in rows]

    def _must_record(self, entity_id: str) -> dict:
        row = self._conn.execute("SELECT * FROM records WHERE id=?", (entity_id,)).fetchone()
        if row is None:
            raise RrlError("E_NOT_FOUND", "record not found", id=entity_id)
        return {
            "id": row["id"],
            "kind": row["kind"],
            "content_digest": row["content_digest"],
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
        }

    def _kind(self, entity_id: str) -> str:
        return self._must_record(entity_id)["kind"]

    def _kind_or_none(self, entity_id: str) -> str | None:
        row = self._conn.execute("SELECT kind FROM records WHERE id=?", (entity_id,)).fetchone()
        return None if row is None else row["kind"]

    def _proj(self, entity_id: str) -> dict:
        cached = self._proj_cache.get(entity_id)
        if cached is not None:
            return cached
        row = self._conn.execute("SELECT * FROM proj WHERE entity_id=?", (entity_id,)).fetchone()
        if row is None:
            raise RrlError("E_NOT_FOUND", "projection not found", id=entity_id)
        loaded = {
            "entity_id": row["entity_id"],
            "entity_kind": row["entity_kind"],
            "provenance": row["provenance"],
            "execution_result": row["execution_result"],
            "applicability": row["applicability"],
            "usage": row["usage"],
            "verification_scope": json.loads(row["verification_scope_json"]),
            "support_status": row["support_status"],
            "independent_support_count": row["independent_support_count"],
            "source_family": row["source_family"],
            "extra": json.loads(row["extra_json"]),
            "updated_seq": row["updated_seq"],
        }
        self._proj_cache[entity_id] = loaded
        return loaded

    def _event(self, event_type: str, subject_id: str | None, payload: dict) -> None:
        self._conn.execute(
            "INSERT INTO events (event_id, event_type, subject_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, event_type, subject_id, canonical_dumps(payload), utcnow()),
        )

    def _last_seq(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(seq), 0) AS seq FROM events").fetchone()
        return int(row["seq"])

    def _dependency_state(self, deps: list[str]) -> tuple[str, str | None]:
        if not deps:
            return TaskState.QUEUED.value, None
        states = []
        for dep in deps:
            row = self._conn.execute("SELECT state FROM tasks WHERE id=?", (dep,)).fetchone()
            if row is None:
                return TaskState.BLOCKED.value, "dependency_missing"
            states.append(row["state"])
        if any(state in (TaskState.FAILED.value, TaskState.CANCELLED.value) for state in states):
            return TaskState.BLOCKED.value, "dependency_not_succeeded"
        if all(state == TaskState.SUCCEEDED.value for state in states):
            return TaskState.QUEUED.value, None
        return TaskState.BLOCKED.value, "dependencies_pending"

    def _task_row(self, task_id: str) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise RrlError("E_NOT_FOUND", "task not found", id=task_id)
        return row

    def _task_dict(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "state": row["state"],
            "owner": row["owner"],
            "handler": row["handler"],
            "inputs_version": row["inputs_version"],
            "deps": json.loads(row["deps_json"]),
            "workspace": row["workspace"],
            "budget": json.loads(row["budget_json"]),
            "resource_class": row["resource_class"],
            "timeout_seconds": row["timeout_seconds"],
            "max_attempts": row["max_attempts"],
            "attempts": row["attempts"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "exit_status": row["exit_status"],
            "failure_class": row["failure_class"],
            "blocked_reason": row["blocked_reason"],
            "artifact": json.loads(row["artifact_json"]),
            "evidence_ids": json.loads(row["evidence_ids_json"]),
            "checkpoint": None if row["checkpoint_json"] is None else json.loads(row["checkpoint_json"]),
            "cancel_requested": bool(row["cancel_requested"]),
            "log": json.loads(row["log_json"]),
            "evidence_accepted_pass": False,
            "schedule_succeeded": row["state"] == TaskState.SUCCEEDED.value,
        }

    def _finish_task(self, row: sqlite3.Row, state: str, exit_status: str, failure_class: str, artifact: dict) -> None:
        self._conn.execute(
            """
            UPDATE tasks
               SET state=?, ended_at=?, exit_status=?, failure_class=?, artifact_json=?, blocked_reason=NULL
             WHERE id=?
            """,
            (state, utcnow(), exit_status, failure_class, canonical_dumps(artifact), row["id"]),
        )
        self._append_log(row["id"], {"event": "finished", "state": state, "exit_status": exit_status})
        self._event(
            "task_transition",
            row["id"],
            {"from": row["state"], "to": state, "exit_status": exit_status, "failure_class": failure_class},
        )

    def _append_log(self, task_id: str, entry: dict) -> None:
        row = self._task_row(task_id)
        log = json.loads(row["log_json"])
        log.append({"at": utcnow(), **entry})
        self._conn.execute("UPDATE tasks SET log_json=? WHERE id=?", (canonical_dumps(log), task_id))
