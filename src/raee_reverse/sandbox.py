"""Run a target in a restricted working directory.

This strips credentials and applies POSIX rlimits when the platform allows
them. It is not a virtual machine. Network isolation is recorded only after
a connect probe confirms the mechanism that wraps the target. A timeout, a
truncated capture, or a resource-limit stop is not a pass. Target output is
returned as bytes and is not executed.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from raee_reverse import netisolate

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
    """Whether `unshare -n` itself succeeded. This is not `network_isolated`."""
    return netisolate.probe_unshare_n()


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
    probe = dict(netisolate.probe_network_isolation())
    if not probe.get("mechanism"):
        probe["confirmed"] = False
        probe["network_isolated"] = False
        probe["network_namespace"] = False
    isolated = bool(probe.get("confirmed"))
    namespace = bool(isolated and probe.get("network_namespace"))
    limitations = [
        "process rlimits and a credential-stripped environment are not a hypervisor boundary",
        "target stdout and stderr are data and are not interpreted as instructions",
    ]
    if os.name != "posix":
        limitations.append("POSIX rlimits are unavailable on this platform")
    if not namespace:
        limitations.append("network namespace was not applied: " + str(probe.get("namespace_detail") or probe.get("reason") or "unavailable"))
    if isolated:
        limitations.append("network_isolated is true only because a connect probe failed inside " + str(probe.get("mechanism")))
    else:
        limitations.append("network_isolated is false: " + str(probe.get("reason") or "no mechanism was confirmed"))
    env = {key: value for key, value in os.environ.items() if key.upper() in _ALLOW and not any(part in key.upper() for part in _DENY_PARTS)}
    env["PATH"] = env.get("PATH", "/usr/bin:/bin")
    env["HOME"] = str(work)
    env["TMPDIR"] = str(work)
    env["LANG"] = "C"
    command = list(argv)
    if isolated:
        command = netisolate.wrap_argv(command, str(probe["mechanism"]))
    command, rlimits_applied, limit_note, limit_env = _limit_command(
        command,
        cpu_seconds=cpu_seconds,
        fsize_bytes=fsize_bytes,
        as_bytes=as_bytes,
        isolated_by_helper=isolated and probe.get("mechanism") == "seccomp-prctl",
    )
    if limit_note:
        limitations.append(limit_note)
    env.update(limit_env)
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
        "network_namespace": namespace,
        "network_isolated": isolated,
        "network_probe": probe,
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


_RLIMIT_WRAPPER = """
import json, os, resource
spec = json.loads(os.environ["RRL_RLIMITS"])
names = {
    "cpu": "RLIMIT_CPU",
    "fsize": "RLIMIT_FSIZE",
    "as": "RLIMIT_AS",
    "nofile": "RLIMIT_NOFILE",
    "nproc": "RLIMIT_NPROC",
}
for key, value in spec.items():
    limit = getattr(resource, names[key], None)
    if limit is None:
        continue
    try:
        resource.setrlimit(limit, (int(value), int(value)))
    except (OSError, ValueError):
        pass
argv = json.loads(os.environ["RRL_ARGV"])
os.execv(argv[0], argv)
"""


def _rlimit_spec(cpu_seconds, fsize_bytes, as_bytes) -> str:
    spec = {"nofile": 64, "nproc": 128}
    if cpu_seconds is not None:
        spec["cpu"] = int(cpu_seconds)
    if fsize_bytes is not None:
        spec["fsize"] = int(fsize_bytes)
    if as_bytes is not None:
        spec["as"] = int(as_bytes)
    return json.dumps(spec)


def _limit_command(argv, *, cpu_seconds, fsize_bytes, as_bytes, isolated_by_helper=False):
    """Return (command, applied, limitation note, extra env).

    Linux uses prlimit. Other POSIX hosts set the limits in a short-lived
    Python process that then execs the target. A missing mechanism is recorded
    and is not described as applied.
    """
    if os.name != "posix":
        return list(argv), False, None, {}
    spec = _rlimit_spec(cpu_seconds, fsize_bytes, as_bytes)
    prlimit = shutil.which("prlimit")
    if prlimit is not None:
        prefix = [prlimit]
        if cpu_seconds is not None:
            prefix.append(f"--cpu={int(cpu_seconds)}")
        if fsize_bytes is not None:
            prefix.append(f"--fsize={int(fsize_bytes)}")
        if as_bytes is not None:
            prefix.append(f"--as={int(as_bytes)}")
        prefix.extend(["--nofile=64", "--nproc=128", "--"])
        return prefix + list(argv), True, None, {}
    note = "rlimits were applied with resource.setrlimit before exec because prlimit is absent"
    if isolated_by_helper:
        return list(argv), True, note, {"RRL_RLIMITS": spec, "RRL_SECCOMP": "1"}
    return [sys.executable, "-c", _RLIMIT_WRAPPER], True, note, {"RRL_RLIMITS": spec, "RRL_ARGV": json.dumps(list(argv))}


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


def _kill_if_running(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        _kill(proc)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
