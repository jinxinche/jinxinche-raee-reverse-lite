"""Runtime comparison against REA 6.9.0 on the checksum_cli contract.

capture-process and one-shot debug-with-gdb are still attempted and recorded.
Those two calls are the previously observed failures. A scored pair comes only
from a persistent GDB session, which is the workflow REA tells the one-shot
command to use, and from this tool's sandbox on the same stdin bytes.
Model cost stays unknown. This is not a product ranking.
"""

from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(REPO / "src"))

from raee_reverse.rea_compare import TASKS, score_observation, stdin_bytes, summarize_pairs  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402


def _which_rea() -> str | None:
    return shutil.which("rea")


def _capture(rea: str, elf: Path, work: Path) -> dict:
    scenario = {
        "executable": str(elf),
        "arguments": [],
        "working_directory": str(work),
        "events": [{"at_ms": 0, "type": "input", "data": "abc"}],
        "timeout_ms": 3000,
        "idle_timeout_ms": 1000,
        "settle_ms": 50,
        "finalization_ms": 0,
    }
    path = work / "scenario.json"
    path.write_text(json.dumps(scenario), encoding="utf-8")
    started = time.perf_counter()
    completed = subprocess.run(
        [rea, "capture-process", str(path), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    elapsed = time.perf_counter() - started
    observed = ""
    exit_info = None
    if completed.stdout:
        try:
            payload = json.loads(completed.stdout)
            normalized = payload.get("normalized_result") or {}
            exit_info = normalized.get("exit")
            frames = normalized.get("rendered_frames") or []
            lines = []
            for frame in frames:
                for line in frame.get("lines") or []:
                    if line.strip():
                        lines.append(line)
            observed = "\n".join(lines)
        except json.JSONDecodeError:
            observed = completed.stdout[:500]
    return {
        "command": f"rea capture-process {path} --format json",
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "exit": exit_info,
        "rendered_nonempty_lines": observed,
        "contract_line_present": "count=3 sum=294" in observed,
        "stderr_tail": completed.stderr[-400:],
        "scored_pair": False,
        "note": "PTY input does not deliver EOF. The scenario schema has input, resize, and signal only.",
    }


def _gdb_oneshot(rea: str, elf: Path) -> dict:
    master, slave = pty.openpty()
    try:
        name = os.ttyname(slave)
        started = time.perf_counter()
        completed = subprocess.run(
            [rea, "debug-with-gdb", "run", "--inferior-tty", name, "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        elapsed = time.perf_counter() - started
    finally:
        os.close(master)
        os.close(slave)
    return {
        "command": "rea debug-with-gdb run --inferior-tty <pty> --format json",
        "note": "One GDB command cannot both load the ELF and redirect stdin. run with redirection is rejected. This call is run alone, so the session has no executable loaded.",
        "elf_not_passed": str(elf),
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout_head": completed.stdout[:600],
        "contract_line_present": "count=3 sum=294" in completed.stdout,
        "scored_pair": False,
    }


def _read_url(stream, timeout: float) -> str:
    deadline = time.perf_counter() + timeout
    buffer = b""
    while time.perf_counter() < deadline:
        chunk = stream.readline()
        if not chunk:
            time.sleep(0.05)
            continue
        buffer += chunk
        text = chunk.decode("utf-8", "replace")
        if "http://" in text and "/mcp" in text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            url = payload.get("url")
            if isinstance(url, str):
                return url
    raise TimeoutError(buffer.decode("utf-8", "replace")[-400:])


def _post(url: str, payload: dict, session: str | None) -> tuple[int, str, bytes]:
    data = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["mcp-session-id"] = session
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
        return response.status, response.headers.get("mcp-session-id", ""), body


def _sse_json(body: bytes) -> dict:
    for line in body.decode("utf-8", "replace").splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {}


def _tool_text(message: dict) -> str:
    result = message.get("result") or {}
    content = result.get("content") or []
    if content and isinstance(content[0], dict):
        return str(content[0].get("text") or "")
    return json.dumps(message)[:2000]


class Mcp:
    def __init__(self, url: str, session: str):
        self.url = url
        self.session = session
        self.next_id = 2

    def call(self, name: str, arguments: dict) -> dict:
        self.next_id += 1
        _status, _sid, body = _post(
            self.url,
            {"jsonrpc": "2.0", "id": self.next_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
            self.session,
        )
        return _sse_json(body)


def _persistent_gdb(mcp: Mcp, elf: Path, work: Path) -> list[dict]:
    rows = []
    for task in TASKS:
        data = stdin_bytes(task)
        path = work / "inputs" / f"{task['id']}.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        started = time.perf_counter()
        stdout = None
        returncode = None
        error = None
        session_id = None
        try:
            started_msg = mcp.call("start_gdb_session", {})
            session_id = (started_msg.get("result") or {}).get("structuredContent", {}).get("session_id")
            if not session_id:
                error = "start_gdb_session did not return a session_id"
            else:
                mcp.call("gdb_console", {"session_id": session_id, "command": f"file {elf}", "detail": "summary"})
                ran = mcp.call(
                    "gdb_console",
                    {"session_id": session_id, "command": f"run < {path}", "detail": "summary"},
                )
                text = _tool_text(ran)
                expected = task["stdout"].rstrip("\n")
                if expected in text and "exited normally" in text:
                    stdout = task["stdout"]
                    returncode = 0
                elif "exited normally" in text:
                    stdout = ""
                    returncode = 0
                else:
                    stdout = ""
                    returncode = 1
                    error = "gdb output did not contain the contract line and a normal exit"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if session_id:
                try:
                    mcp.call("close_gdb_session", {"session_id": session_id})
                except Exception:
                    pass
        elapsed = time.perf_counter() - started
        scored = score_observation(task["stdout"], stdout, returncode)
        rows.append({
            "task_id": task["id"],
            "expected_stdout": task["stdout"],
            "rea_seconds": elapsed,
            "rea": scored,
            "rea_error": error,
            "this_tool": {"observed": False, "correct": False, "returncode": None},
        })
    return rows


def _this_tool(elf: Path, work: Path, rows: list[dict]) -> None:
    by_id = {row["task_id"]: row for row in rows}
    for task in TASKS:
        row = by_id[task["id"]]
        started = time.perf_counter()
        result = run_sandboxed(
            [str(elf)],
            work_dir=work / "sandbox" / task["id"],
            stdin=stdin_bytes(task),
            timeout=10,
            cpu_seconds=5,
            fsize_bytes=1_000_000,
            max_output_bytes=4096,
        )
        elapsed = time.perf_counter() - started
        stdout = result["stdout"].decode("utf-8", "replace") if result["returncode"] is not None else None
        row["this_tool"] = score_observation(task["stdout"], stdout, result["returncode"])
        row["this_tool_seconds"] = elapsed
        row["this_tool_execution_result"] = result["execution_result"]


def _start_mcp(rea: str) -> tuple[subprocess.Popen, Mcp]:
    proc = subprocess.Popen(
        [rea, "mcp", "--http", "--host", "127.0.0.1", "--port", "0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stderr is not None
    url = _read_url(proc.stderr, 30)

    def _drain() -> None:
        assert proc.stderr is not None
        while True:
            chunk = proc.stderr.readline()
            if not chunk:
                return

    threading.Thread(target=_drain, daemon=True).start()
    status, session, body = _post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "raee-reverse-lite", "version": "0.1.0"},
            },
        },
        None,
    )
    if status != 200 or not session:
        raise RuntimeError(f"initialize status {status} body {body[:200]!r}")
    _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    return proc, Mcp(url, session)


def main() -> int:
    work = Path(sys.argv[1])
    out = Path(sys.argv[2])
    elf = Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    rea = _which_rea()
    version = None
    if rea:
        probed = subprocess.run([rea, "--version"], capture_output=True, text=True, check=False)
        version = probed.stdout.strip()
    gdb = subprocess.run(["gdb", "--version"], capture_output=True, text=True, check=False)
    model_cost = {"status": "unknown", "amount": None, "reason": "no usage report; no model endpoint was configured"}
    report = {
        "comparison_complete": False,
        "executed": False,
        "attempts_executed": False,
        "ranking": False,
        "promotes_static_sample": False,
        "static_record": "docs/a18/REA_COMPARISON.md",
        "prior_record": "docs/a18/rea_runtime_2026-11-15.json",
        "rea_version": version,
        "rea_path": rea,
        "gdb_version": gdb.stdout.splitlines()[0] if gdb.returncode == 0 and gdb.stdout else None,
        "rizin_on_path": shutil.which("rizin") is not None,
        "sample_size_scored_pairs": 0,
        "model_calls": 0,
        "model_cost": model_cost,
        "savings_percent": None,
        "task_set": [dict(task) for task in TASKS],
    }
    if rea is None or version != "6.9.0":
        report["reason"] = "rea 6.9.0 is not on PATH"
        summary = summarize_pairs([], model_cost=model_cost)
        report.update(summary)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"comparison_complete": False, "reason": report["reason"]}))
        return 0
    capture = _capture(rea, elf, work)
    gdb_attempt = _gdb_oneshot(rea, elf)
    report["attempts_executed"] = True
    report["attempts"] = {"capture_process": capture, "debug_with_gdb_oneshot": gdb_attempt}
    proc = None
    try:
        proc, mcp = _start_mcp(rea)
        rows = _persistent_gdb(mcp, elf, work)
        _this_tool(elf, work, rows)
        summary = summarize_pairs(rows, model_cost=model_cost)
        report.update(summary)
        report["rea_workflow"] = "persistent gdb_console: file, then run < stdin file"
        if summary["comparison_complete"]:
            report["reason"] = (
                "Scored pairs were executed with REA 6.9.0 persistent GDB and this tool's sandbox "
                "on the same stdin bytes. capture-process still does not deliver EOF. "
                "One-shot debug-with-gdb run still does not load the ELF. This is not a ranking. "
                "Model cost is unknown."
            )
        else:
            report["reason"] = (
                "REA 6.9.0 was invoked. The persistent GDB workflow did not score every declared task, "
                "so this is not a complete comparison. capture-process still has no EOF event. "
                "Model cost is unknown."
            )
    except Exception as exc:
        summary = summarize_pairs([], model_cost=model_cost)
        report.update(summary)
        report["reason"] = f"persistent GDB workflow failed: {type(exc).__name__}: {exc}"
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "comparison_complete": report["comparison_complete"],
        "sample_size_scored_pairs": report["sample_size_scored_pairs"],
        "ranking": False,
        "capture_contract": capture["contract_line_present"],
        "oneshot_gdb_contract": gdb_attempt["contract_line_present"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
