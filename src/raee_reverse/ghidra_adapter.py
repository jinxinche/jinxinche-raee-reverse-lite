"""Headless Ghidra adapter.

If the install or JDK is missing, the result is not_executed. A script that
does not actually launch Ghidra must not be reported as an analysis.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from raee_reverse.interfaces import missing_engine


def analyze_elf(
    elf: Path,
    *,
    ghidra_home: Path | None,
    java_home: Path | None,
    project_dir: Path,
    script_path: Path,
    output_path: Path,
    timeout: float = 180,
) -> dict:
    elf = Path(elf)
    if ghidra_home is None or java_home is None:
        return missing_engine("ghidra", "ghidra_home or java_home was not provided")
    headless = Path(ghidra_home) / "support" / "analyzeHeadless"
    java = Path(java_home) / "bin" / "java"
    if not headless.is_file() or not java.is_file() or not elf.is_file() or not script_path.is_file():
        return missing_engine(
            "ghidra",
            "analyzeHeadless, java, the ELF, or the export script is not available",
        )
    project_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
    env["RRL_GHIDRA_OUT"] = str(output_path)
    env["MAXMEM"] = "2G"
    command = [
        str(headless),
        str(project_dir),
        "rrl-dev",
        "-import",
        str(elf),
        "-scriptPath",
        str(script_path.parent),
        "-postScript",
        script_path.name,
        "-deleteProject",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
            cwd=str(project_dir),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "engine": "ghidra",
            "execution_result": "uncertain",
            "applicability": "incomplete_scope",
            "accepted_pass": False,
            "outcome": "timeout",
            "limitations": ["analyzeHeadless exceeded the timeout", str(exc)[:300]],
            "simulated": False,
            "observations": [],
        }
    except OSError as exc:
        return missing_engine("ghidra", f"failed to start analyzeHeadless: {exc}")
    stdout = completed.stdout.decode("utf-8", "replace")
    stderr = completed.stderr.decode("utf-8", "replace")
    produced = output_path.is_file()
    if completed.returncode != 0 or not produced:
        return {
            "engine": "ghidra",
            "execution_result": "failed" if completed.returncode else "uncertain",
            "applicability": "incomplete_scope",
            "accepted_pass": False,
            "outcome": "engine_error",
            "returncode": completed.returncode,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
            "limitations": ["Ghidra did not produce the export file" if not produced else "analyzeHeadless returned non-zero"],
            "simulated": False,
            "observations": [],
        }
    text = output_path.read_text(encoding="utf-8", errors="replace")
    return {
        "engine": "ghidra",
        "execution_result": "passed",
        "applicability": "valid",
        "accepted_pass": False,
        "outcome": "completed",
        "returncode": completed.returncode,
        "export_text": text,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
        "limitations": [
            "function listing and an optional decompilation are static observations, not a behavior proof",
            "accepted_pass stays false until a claim evaluation with an explicit scope says otherwise",
        ],
        "simulated": False,
        "tool_version_hint": Path(ghidra_home).name,
        "observations": [{"kind": "ghidra_export", "bytes": len(text.encode("utf-8"))}],
    }
