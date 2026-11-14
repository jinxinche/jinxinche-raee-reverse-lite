"""Run a target in a restricted working directory.

This strips credentials and applies POSIX rlimits when the platform allows
them. It is not a virtual machine. A timeout, a truncated capture, or a
resource-limit stop is not a pass. Target output is returned as bytes and is
not executed.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

_ALLOW = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TZ"}
_DENY_PARTS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "AWS_",
    "GITHUB",
    "GH_",
    "CURSOR",
    "OPENAI",
    "ANTHROPIC",
    "AZURE",
    "PRIVATE",
)


def probe_network_namespace() -> dict:
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


def run_sandboxed(
    argv: list[str],
    *,
    work_dir: str | Path,
    timeout: float,
    stdin: bytes = b"",
    max_output_bytes: int = 16_384,
    cpu_seconds: int | None = 2,
    fsize_bytes: int | None = 1_048_576,
    as_bytes: int | None = None,
) -> dict:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_output_bytes < 1:
        raise ValueError("max_output_bytes must be positive")
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    network = probe_network_namespace()
    limitations = [
        "process rlimits and a credential-stripped environment are not a hypervisor boundary",
        "target stdout and stderr are data and are not interpreted as instructions",
    ]
    rlimits_applied = False
    if os.name != "posix":
        limitations.append("POSIX rlimits are unavailable on this platform")
    if not network["available"]:
        limitations.append("network namespace was not applied: " + (network["detail"] or "unavailable"))
    env = {key: value for key, value in os.environ.items() if key.upper() in _ALLOW and not any(part in key.upper() for part in _DENY_PARTS)}
    env["PATH"] = env.get("PATH", "/usr/bin:/bin")
    env["HOME"] = str(work)
    env["TMPDIR"] = str(work)
    env["LANG"] = "C"
    command = list(argv)
    prlimit = shutil.which("prlimit") if os.name == "posix" else None
    if prlimit is not None:
        prefix = [prlimit]
        if cpu_seconds is not None:
            prefix.append(f"--cpu={int(cpu_seconds)}")
        if fsize_bytes is not None:
            prefix.append(f"--fsize={int(fsize_bytes)}")
        if as_bytes is not None:
            prefix.append(f"--as={int(as_bytes)}")
        prefix.extend(["--nofile=64", "--nproc=128", "--"])
        command = prefix + command
        rlimits_applied = True
    else:
        limitations.append("prlimit is not available; resource limits were not applied by this runner")
    proc = subprocess.Popen(
        command,
        cwd=work,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name == "posix"),
    )
    stdout_box: list[bytes] = []
    stderr_box: list[bytes] = []
    truncated = {"stdout": False, "stderr": False}

    def _reader(stream, box, key):
        data, hit = _read_capped(stream, max_output_bytes)
        box.append(data)
        truncated[key] = hit

    out_thread = threading.Thread(target=_reader, args=(proc.stdout, stdout_box, "stdout"))
    err_thread = threading.Thread(target=_reader, args=(proc.stderr, stderr_box, "stderr"))
    out_thread.start()
    err_thread.start()
    started = time.monotonic()
    timed_out = False
    try:
        if stdin:
            assert proc.stdin is not None
            proc.stdin.write(stdin)
        if proc.stdin is not None:
            proc.stdin.close()
    except BrokenPipeError:
        pass
    try:
        while proc.poll() is None:
            if time.monotonic() - started > timeout:
                timed_out = True
                _kill(proc)
                break
            if truncated["stdout"] or truncated["stderr"]:
                _kill(proc)
                break
            time.sleep(0.01)
    finally:
        _kill_if_running(proc)
        out_thread.join(timeout=2)
        err_thread.join(timeout=2)
    duration = time.monotonic() - started
    stdout = stdout_box[0] if stdout_box else b""
    stderr = stderr_box[0] if stderr_box else b""
    was_truncated = bool(truncated["stdout"] or truncated["stderr"])
    returncode = proc.returncode
    outcome, execution = _classify(returncode, timed_out, was_truncated)
    if was_truncated:
        limitations.append("captured output hit the byte cap and is not a complete observation")
    return {
        "outcome": outcome,
        "execution_result": execution,
        "accepted_pass": False,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "truncated": was_truncated,
        "duration_seconds": duration,
        "rlimits_applied": rlimits_applied,
        "network_namespace": bool(network["available"]),
        "network_probe": network,
        "work_dir": str(work),
        "limitations": limitations,
        "argv": list(argv),
    }


def make_work_dir(parent: str | Path) -> Path:
    return Path(tempfile.mkdtemp(prefix="rrl-sandbox-", dir=parent))


def _classify(returncode: int | None, timed_out: bool, truncated: bool) -> tuple[str, str]:
    if timed_out:
        return "timeout", "uncertain"
    if truncated:
        return "truncated", "uncertain"
    if returncode is None:
        return "infra_error", "uncertain"
    if returncode < 0:
        sig = -returncode
        if sig in {getattr(signal, name) for name in ("SIGXCPU", "SIGXFSZ") if hasattr(signal, name)}:
            return "resource_limit", "uncertain"
        return "infra_error", "uncertain"
    if returncode == 0:
        return "completed", "passed"
    return "behavior_failed", "failed"


def _read_capped(stream, limit: int) -> tuple[bytes, bool]:
    chunks = []
    total = 0
    while total <= limit:
        block = stream.read(min(65536, limit - total + 1))
        if not block:
            return b"".join(chunks), False
        chunks.append(block)
        total += len(block)
        if total > limit:
            return b"".join(chunks)[:limit], True
    return b"".join(chunks)[:limit], True


def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            proc.kill()
    else:
        proc.kill()


def _kill_if_running(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        _kill(proc)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
