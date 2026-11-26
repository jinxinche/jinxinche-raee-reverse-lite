"""Choose one confirmed network isolation mechanism for a target process.

Order: user and net namespaces (`unshare -rn`), bubblewrap `--unshare-net`
when `bwrap` is on PATH, then a seccomp filter that denies socket families
other than AF_UNIX. A mechanism counts only when a loopback connect succeeds
outside it and the same connect fails inside it. Otherwise the result is
network_isolated false.
"""

from __future__ import annotations

import copy
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

CONNECT_SOURCE = """\
import socket, sys
print("STARTED", flush=True)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(("127.0.0.1", int(sys.argv[1])))
except OSError as exc:
    print("CONNECT_FAIL", exc.errno, flush=True)
else:
    print("CONNECT_OK", flush=True)
"""

_ORDER = (
    ("unshare-rn", True),
    ("bwrap-unshare-net", True),
    ("seccomp-prctl", False),
)
_LOCK = threading.Lock()
_CACHED: dict | None = None


def connect_check_argv(port: int) -> list[str]:
    return [sys.executable, "-c", CONNECT_SOURCE, str(port)]


def helper_path() -> Path:
    return Path(__file__).resolve().parent / "isolation_exec.py"


def isolation_prefix(mechanism: str) -> list[str] | None:
    if mechanism == "unshare-rn":
        if sys.platform != "linux":
            return None
        binary = shutil.which("unshare")
        if not binary:
            return None
        return [binary, "-rn", "--"]
    if mechanism == "bwrap-unshare-net":
        binary = shutil.which("bwrap")
        if not binary:
            return None
        return [
            binary,
            "--unshare-net",
            "--die-with-parent",
            "--bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--",
        ]
    if mechanism == "seccomp-prctl":
        if sys.platform != "linux":
            return None
        helper = helper_path()
        if not helper.is_file():
            return None
        return [sys.executable, str(helper), "--"]
    return None


def wrap_argv(argv: list[str], mechanism: str) -> list[str]:
    prefix = isolation_prefix(mechanism)
    if prefix is None:
        raise RuntimeError(f"isolation mechanism {mechanism} is not available")
    return prefix + list(argv)


def probe_unshare_n() -> dict:
    """The historical `unshare -n` probe. It does not by itself set network_isolated."""
    if shutil.which("unshare") is None:
        return {"available": False, "detail": "unshare is not installed"}
    try:
        completed = subprocess.run(
            ["unshare", "-n", "true"],
            capture_output=True,
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return {"available": False, "detail": str(exc)}
    if completed.returncode == 0:
        return {"available": True, "detail": ""}
    detail = (completed.stderr or completed.stdout or b"").decode("utf-8", "replace")[:500]
    return {"available": False, "detail": detail or f"exit {completed.returncode}"}


def reset_network_isolation_cache() -> None:
    global _CACHED
    with _LOCK:
        _CACHED = None


def probe_network_isolation() -> dict:
    with _LOCK:
        global _CACHED
        if _CACHED is None:
            _CACHED = _probe_uncached()
        return copy.deepcopy(_CACHED)


def _spawn(argv: list[str], timeout: float) -> dict:
    try:
        completed = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": exc.stdout or b"",
            "stderr": exc.stderr or b"",
            "timed_out": True,
            "error": "timeout",
        }
    except OSError as exc:
        return {
            "returncode": None,
            "stdout": b"",
            "stderr": str(exc).encode("utf-8", "replace"),
            "timed_out": False,
            "error": str(exc),
        }
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
        "error": "",
    }


def _text(spawned: dict) -> str:
    stdout = spawned["stdout"].decode("utf-8", "replace") if isinstance(spawned["stdout"], bytes) else str(spawned["stdout"])
    stderr = spawned["stderr"].decode("utf-8", "replace") if isinstance(spawned["stderr"], bytes) else str(spawned["stderr"])
    return (stdout + ("\n" + stderr if stderr else "")).strip()


def _connect_failed(spawned: dict) -> bool:
    if spawned["timed_out"] or spawned["error"]:
        return False
    text = _text(spawned)
    return (
        spawned["returncode"] == 0
        and "STARTED" in text
        and "CONNECT_FAIL" in text
        and "CONNECT_OK" not in text
    )


def _connect_ok(spawned: dict) -> bool:
    if spawned["timed_out"] or spawned["error"] or spawned["returncode"] != 0:
        return False
    text = _text(spawned)
    return "STARTED" in text and "CONNECT_OK" in text and "CONNECT_FAIL" not in text


def _probe_uncached() -> dict:
    unshare_n = probe_unshare_n()
    attempts: list[dict] = []
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        port = listener.getsockname()[1]
    except OSError as exc:
        listener.close()
        return _negative(
            unshare_n,
            attempts,
            baseline="not_run",
            reason=f"could not bind a loopback listener: {exc}",
        )
    try:
        baseline = _spawn(connect_check_argv(port), 8)
        if not _connect_ok(baseline):
            return _negative(
                unshare_n,
                attempts,
                baseline="fail",
                reason="baseline connect did not succeed, so no mechanism was confirmed: " + _text(baseline)[:300],
            )
        for mechanism, is_namespace in _ORDER:
            prefix = isolation_prefix(mechanism)
            if prefix is None:
                attempts.append(
                    {
                        "mechanism": mechanism,
                        "result": "unavailable",
                        "network_namespace": False,
                        "detail": "not installed or not supported on this platform",
                        "returncode": None,
                    }
                )
                continue
            spawned = _spawn(prefix + connect_check_argv(port), 8)
            confirmed = _connect_failed(spawned)
            attempts.append(
                {
                    "mechanism": mechanism,
                    "result": "confirmed" if confirmed else "not_confirmed",
                    "network_namespace": bool(confirmed and is_namespace),
                    "detail": _text(spawned)[:500],
                    "returncode": spawned["returncode"],
                }
            )
            if confirmed:
                started = False
                for later, _later_namespace in _ORDER:
                    if later == mechanism:
                        started = True
                        continue
                    if not started:
                        continue
                    attempts.append(
                        {
                            "mechanism": later,
                            "result": "not_tried",
                            "network_namespace": False,
                            "detail": f"not tried because {mechanism} was confirmed",
                            "returncode": None,
                        }
                    )
                return {
                    "confirmed": True,
                    "network_isolated": True,
                    "network_namespace": bool(is_namespace),
                    "mechanism": mechanism,
                    "baseline_connect": "ok",
                    "reason": f"connect failed inside {mechanism}",
                    "attempts": attempts,
                    "unshare_n": unshare_n,
                    "namespace_detail": _namespace_detail(unshare_n, attempts),
                }
        return _negative(
            unshare_n,
            attempts,
            baseline="ok",
            reason="no mechanism kept the loopback connect from succeeding",
        )
    finally:
        listener.close()


def _namespace_detail(unshare_n: dict, attempts: list[dict]) -> str:
    parts = [f"unshare -n available={unshare_n['available']}"]
    if unshare_n.get("detail"):
        parts.append(str(unshare_n["detail"]).replace("\n", " ")[:200])
    for attempt in attempts:
        if attempt["mechanism"] == "seccomp-prctl":
            continue
        parts.append(f"{attempt['mechanism']} {attempt['result']}")
    return "; ".join(parts)[:500]


def _negative(unshare_n: dict, attempts: list[dict], *, baseline: str, reason: str) -> dict:
    return {
        "confirmed": False,
        "network_isolated": False,
        "network_namespace": False,
        "mechanism": None,
        "baseline_connect": baseline,
        "reason": reason,
        "attempts": attempts,
        "unshare_n": unshare_n,
        "namespace_detail": _namespace_detail(unshare_n, attempts),
    }
