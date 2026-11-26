"""Backup static engine behind the analysis adapter.

r2pipe drives radare2 when that binary is on PATH. If radare2 is absent and
rizin is present, r2pipe is pointed at rizin through a temporary directory
whose `radare2` name is a symlink, because r2pipe 2.1 launches a binary named
`radare2`. angr is not selected. A missing binary or a missing r2pipe import
is not_executed and is not a pass.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from raee_reverse.interfaces import missing_engine

_COMMANDS = ("aa", "aflj", "iej")


def _load_r2pipe():
    try:
        import r2pipe
    except ImportError as exc:
        return None, str(exc)
    return r2pipe, r2pipe.version()


def locate_backend() -> dict:
    r2pipe, detail = _load_r2pipe()
    radare2 = shutil.which("radare2")
    rizin = shutil.which("rizin")
    kind = None
    path = None
    if r2pipe is not None and radare2:
        kind, path = "radare2", radare2
    elif r2pipe is not None and rizin:
        kind, path = "rizin", rizin
    return {
        "installed": bool(kind and path),
        "interface": "r2pipe" if r2pipe is not None else None,
        "r2pipe_version": detail if r2pipe is not None else None,
        "r2pipe_error": None if r2pipe is not None else detail,
        "binary": kind,
        "binary_path": path,
        "rizin_on_path": bool(rizin),
        "radare2_on_path": bool(radare2),
        "angr_selected": False,
    }


class BackupEngine:
    name = "r2pipe"

    def analyze(self, artifact: Path, *, budget: dict) -> dict:
        located = locate_backend()
        artifact = Path(artifact)
        if not located["installed"]:
            if located["r2pipe_error"]:
                detail = "r2pipe is not importable: " + located["r2pipe_error"]
            else:
                detail = "radare2 and rizin were not on PATH"
            result = missing_engine("r2pipe", detail)
            result.update(located)
            result["functions"] = []
            result["program_entry"] = None
            result["analysis_commands"] = list(_COMMANDS)
            return result
        self.name = str(located["binary"])
        if not artifact.is_file():
            result = missing_engine(self.name, f"artifact is not a file: {artifact}")
            result.update(located)
            result["installed"] = True
            result["functions"] = []
            result["program_entry"] = None
            result["analysis_commands"] = list(_COMMANDS)
            return result
        timeout = float(budget.get("timeout", 180))
        version = _binary_version(str(located["binary_path"]))
        started = time.monotonic()
        try:
            functions, program_entry, limitations, execution = _analyze_open(
                artifact,
                located,
                timeout=timeout,
            )
        except Exception as exc:
            result = missing_engine(self.name, f"r2pipe failed: {exc}")
            result["execution_result"] = "failed"
            result.update(located)
            result["installed"] = True
            result["binary_version"] = version
            result["functions"] = []
            result["program_entry"] = None
            result["analysis_commands"] = list(_COMMANDS)
            result["duration_seconds"] = time.monotonic() - started
            return result
        passed = execution == "passed"
        return {
            "engine": self.name,
            "interface": "r2pipe",
            "execution_result": execution,
            "applicability": "valid" if passed else "incomplete_scope",
            "provenance": "observed",
            "accepted_pass": False,
            "installed": True,
            "binary": located["binary"],
            "binary_path": located["binary_path"],
            "binary_version": version,
            "r2pipe_version": located["r2pipe_version"],
            "rizin_on_path": located["rizin_on_path"],
            "radare2_on_path": located["radare2_on_path"],
            "angr_selected": False,
            "rizin_via_symlink": located["binary"] == "rizin",
            "analysis_commands": list(_COMMANDS),
            "open_flags": ["-e", "bin.relocs.apply=true"],
            "functions": functions,
            "program_entry": program_entry,
            "duration_seconds": time.monotonic() - started,
            "observations": [{"kind": "function_list", "count": len(functions)}] if passed else [],
            "limitations": limitations
            + [
                "a function list is a static observation, not a behavior proof",
                "accepted_pass stays false until a claim evaluation with an explicit scope says otherwise",
            ],
            "simulated": False,
        }


def analyze_backup(elf: Path, *, budget: dict | None = None) -> dict:
    return BackupEngine().analyze(elf, budget=budget or {})


def _binary_version(path: str) -> str:
    try:
        completed = subprocess.run([path, "-v"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else f"exit {completed.returncode}"


def _analyze_open(artifact: Path, located: dict, *, timeout: float):
    r2pipe, _detail = _load_r2pipe()
    if r2pipe is None:
        return [], None, ["r2pipe import failed while opening"], "not_executed"
    home = None
    if located["binary"] == "rizin":
        home = tempfile.mkdtemp(prefix="rrl-rizin-")
        os.symlink(located["binary_path"], os.path.join(home, "radare2"))
    state = {"timed_out": False}
    opened = None
    try:
        open_flags = ["-e", "bin.relocs.apply=true"]
        if home:
            opened = r2pipe.open(str(artifact), flags=open_flags, radare2home=home)
        else:
            opened = r2pipe.open(str(artifact), flags=open_flags)

        def _kill():
            state["timed_out"] = True
            process = getattr(opened, "process", None)
            if process is not None and process.poll() is None:
                process.kill()

        timer = threading.Timer(timeout, _kill)
        timer.start()
        try:
            opened.cmd("aa")
            if state["timed_out"]:
                return [], None, ["analysis exceeded the timeout"], "uncertain"
            raw_functions = opened.cmd("aflj")
            raw_entries = opened.cmd("iej")
        finally:
            timer.cancel()
        if state["timed_out"]:
            return [], None, ["analysis exceeded the timeout"], "uncertain"
        functions, function_error = _parse_functions(raw_functions)
        program_entry, entry_error = _parse_entry(raw_entries)
        limitations = [item for item in (function_error, entry_error) if item]
        if function_error:
            return [], program_entry, limitations, "uncertain"
        return functions, program_entry, limitations, "passed"
    finally:
        if opened is not None:
            try:
                opened.quit()
            except Exception:
                process = getattr(opened, "process", None)
                if process is not None and process.poll() is None:
                    process.kill()
        if home is not None:
            shutil.rmtree(home, ignore_errors=True)


def _parse_functions(raw: str | None) -> tuple[list[dict], str | None]:
    if raw is None or not str(raw).strip():
        return [], "aflj returned no JSON"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], f"aflj was not JSON: {exc}"
    if not isinstance(parsed, list):
        return [], "aflj JSON was not a list"
    functions = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("realname") or item.get("fullname")
        if not isinstance(name, str) or not name.strip():
            continue
        entry = None
        for key in ("offset", "addr", "vaddr"):
            entry = _as_int(item.get(key))
            if entry is not None:
                break
        if entry is None:
            continue
        functions.append({"name": name.strip(), "entry": entry})
    if parsed and not functions:
        sample = parsed[0]
        keys = list(sample)[:12] if isinstance(sample, dict) else type(sample).__name__
        return [], f"aflj entries had no usable name and address; sample={keys}"
    return functions, None


def _as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def _parse_entry(raw: str | None) -> tuple[int | None, str | None]:
    if raw is None or not str(raw).strip():
        return None, "iej returned no JSON"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"iej was not JSON: {exc}"
    if not isinstance(parsed, list):
        return None, "iej JSON was not a list"
    for item in parsed:
        if isinstance(item, dict) and item.get("type") == "program":
            entry = _as_int(item.get("vaddr"))
            if entry is None:
                entry = _as_int(item.get("addr"))
            if entry is not None:
                return entry, None
    return None, "iej had no program entry"
