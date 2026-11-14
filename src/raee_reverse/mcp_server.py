"""Minimal MCP stdio server for the ledger.

Tools return the ledger's dimensions. A tool result is not itself accepted_pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from raee_reverse.errors import RrlError
from raee_reverse.store import Store

PROTOCOL = "2025-06-18"


def serve(root: Path, stdin=None, stdout=None) -> None:
    reader = sys.stdin.buffer if stdin is None else stdin
    writer = sys.stdout.buffer if stdout is None else stdout
    store = Store(root)
    try:
        while True:
            message = _read(reader)
            if message is None:
                return
            response = _handle(store, message)
            if response is not None:
                _write(writer, response)
    finally:
        store.close()


def _handle(store: Store, message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized" or request_id is None and method and method.startswith("notifications/"):
        return None
    try:
        result = _dispatch(store, method, message.get("params") or {})
    except RrlError as exc:
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": exc.message, "data": exc.to_dict()}}
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _dispatch(store: Store, method: str, params: dict) -> dict:
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "raee-reverse-lite", "version": "0.1.0"},
        }
    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "ledger_status",
                    "description": "List claim projections. accepted_pass is scoped, not universal.",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "gate_claim",
                    "description": "Return the current decision for one claim id.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"claim_id": {"type": "string"}},
                        "required": ["claim_id"],
                    },
                },
            ]
        }
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "ledger_status":
            payload = store.status_summary()
        elif name == "gate_claim":
            payload = store.decision(str(arguments.get("claim_id") or ""))
        else:
            raise RrlError("E_MCP_TOOL", "unknown tool", name=name)
        return {
            "content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
            "isError": False,
        }
    raise RrlError("E_MCP_METHOD", "unsupported method", method=method)


def _read(reader) -> dict | None:
    headers = {}
    while True:
        line = reader.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("ascii", "replace")
        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = reader.read(length)
    return json.loads(body.decode("utf-8"))


def _write(writer, payload: dict) -> None:
    raw = json.dumps(payload).encode("utf-8")
    writer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    writer.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="raee-reverse-mcp")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    serve(Path(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
