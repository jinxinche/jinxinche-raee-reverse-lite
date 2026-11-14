"""Write the environment facts this process can observe. It does not guess."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else f"exit {completed.returncode}"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "docs" / "phase0" / "environment.observed.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    keys = [key for key in os.environ if any(part in key.upper() for part in ("API_KEY", "OPENAI", "ANTHROPIC", "AZURE_OPENAI"))]
    report = {
        "observed": True,
        "assumed": False,
        "system": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_executable": shutil.which("python3"),
        "java_resolved_by_path": _run(["java", "-version"]),
        "java_usr_bin": _run(["/usr/bin/java", "-version"]),
        "javac_resolved_by_path": _run(["javac", "-version"]),
        "gcc": _run(["gcc", "--version"]),
        "node": _run(["node", "--version"]),
        "tools": {
            "prlimit": shutil.which("prlimit"),
            "unshare": shutil.which("unshare"),
            "bwrap": shutil.which("bwrap"),
            "ghidra_on_path": shutil.which("ghidra") or shutil.which("analyzeHeadless"),
        },
        "cpu_count": os.cpu_count(),
        "model_api_env_names_present": keys,
        "note": "This file is a probe of the process that ran the script. Disk and memory figures belong in ENVIRONMENT.md because they come from the shell commands recorded there.",
    }
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
