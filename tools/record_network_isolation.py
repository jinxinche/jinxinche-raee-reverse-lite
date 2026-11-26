"""Record one sandboxed connect attempt and the isolation probe that wrapped it."""

from __future__ import annotations

import json
import platform
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.netisolate import connect_check_argv  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "network_isolation.json"


def main() -> int:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    try:
        work = Path(tempfile.mkdtemp(prefix="rrl-net-isolation-"))
        result = run_sandboxed(
            connect_check_argv(port),
            work_dir=work,
            timeout=15,
            cpu_seconds=5,
        )
    finally:
        listener.close()
    stdout = result["stdout"].decode("utf-8", "replace")
    record = {
        "kind": "network-isolation-probe",
        "accepted_pass": False,
        "host": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "network_isolated": bool(result["network_isolated"]),
        "network_namespace": bool(result["network_namespace"]),
        "stdout": stdout,
        "stderr": result["stderr"].decode("utf-8", "replace"),
        "returncode": result["returncode"],
        "execution_result": result["execution_result"],
        "rlimits_applied": result["rlimits_applied"],
        "limitations": result["limitations"],
        "network_probe": result["network_probe"],
    }
    if record["network_isolated"] and "CONNECT_OK" in stdout:
        record["contradiction"] = "network_isolated was true and the target connected"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    if record.get("contradiction"):
        return 1
    if record["network_isolated"] and "CONNECT_FAIL" not in stdout:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
