"""Execute the synthetic dev ELF and, when present, headless Ghidra.

Writes a JSON report of this process. The default path is
docs/evidence/local/ and is gitignored. Set RRL_PHASE2_OUT to overwrite a
chosen file. A missing engine is recorded as not executed. Nothing in the
report is a universal pass.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.canonical import digest_bytes  # noqa: E402
from raee_reverse.ghidra_adapter import analyze_elf  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402
from raee_reverse.store import Store  # noqa: E402

SOURCE = ROOT / "samples" / "dev" / "checksum_cli.c"
SCRIPT = ROOT / "samples" / "dev" / "ghidra" / "ExportDevSample.java"
OUT = Path(os.environ.get("RRL_PHASE2_OUT", ROOT / "docs" / "evidence" / "local" / "phase2_dev_sample.json"))
GHIDRA = Path(os.environ.get("GHIDRA_INSTALL_DIR", "/tmp/ghidra-dl/ghidra_12.2_PUBLIC"))
JAVA = Path(os.environ.get("JAVA_HOME", "/tmp/jdk25/jdk-25.0.5+8"))
SCOPE = {
    "inputs": ["stdin:abc"],
    "behaviors": ["prints count=3 sum=294 and exits 0"],
    "environments": ["linux-x86_64"],
    "complete_output": True,
    "require_complete_output": True,
}


def _public_run(result: dict) -> dict:
    return {
        "outcome": result["outcome"],
        "execution_result": result["execution_result"],
        "accepted_pass": result["accepted_pass"],
        "returncode": result["returncode"],
        "stdout": result["stdout"].decode("utf-8", "replace"),
        "stderr": result["stderr"].decode("utf-8", "replace"),
        "truncated": result["truncated"],
        "rlimits_applied": result["rlimits_applied"],
        "network_namespace": result["network_namespace"],
        "limitations": result["limitations"],
        "duration_seconds": result["duration_seconds"],
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "kind": "phase2-dev-sample",
        "synthetic": True,
        "real_target": "zlib 1.4 minigzip is frozen and was not executed in this run",
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
    }
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"} or shutil.which("gcc") is None:
        report["executed"] = False
        report["reason"] = "dev ELF execution is recorded only on Linux x86_64 with gcc"
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"executed": False, "wrote": str(OUT)}))
        return 0
    with tempfile.TemporaryDirectory(prefix="rrl-phase2-") as temporary:
        work = Path(temporary)
        binary = work / "checksum_cli"
        compiled = subprocess.run(
            ["gcc", "-O0", "-g", "-o", str(binary), str(SOURCE)],
            capture_output=True,
            text=True,
            check=False,
        )
        if compiled.returncode != 0:
            report["executed"] = False
            report["reason"] = "gcc failed"
            report["compiler_stderr"] = compiled.stderr[-2000:]
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            return 1
        elf = binary.read_bytes()
        report["elf_sha256"] = digest_bytes(elf)
        runs = {
            "abc": run_sandboxed([str(binary)], work_dir=work / "abc", timeout=5, stdin=b"abc", cpu_seconds=2),
            "empty": run_sandboxed([str(binary)], work_dir=work / "empty", timeout=5, stdin=b"", cpu_seconds=2),
            "fail": run_sandboxed([str(binary)], work_dir=work / "fail", timeout=5, stdin=b"abc", cpu_seconds=2),
        }
        # The fail case needs --fail. Re-run it with the flag. The dict entry above is the abc-shaped
        # control without the flag; replace it.
        runs["fail"] = run_sandboxed(
            [str(binary), "--fail"], work_dir=work / "fail", timeout=5, stdin=b"abc", cpu_seconds=2
        )
        report["runs"] = {name: _public_run(result) for name, result in runs.items()}
        ghidra_out = work / "ghidra.txt"
        ghidra = analyze_elf(
            binary,
            ghidra_home=GHIDRA if GHIDRA.is_dir() else None,
            java_home=JAVA if JAVA.is_dir() else None,
            project_dir=work / "ghidra-project",
            script_path=SCRIPT,
            output_path=ghidra_out,
            timeout=300,
        )
        export_text = ghidra.get("export_text", "")
        report["ghidra"] = {
            "executed": ghidra.get("outcome") == "completed" and bool(export_text),
            "execution_result": ghidra.get("execution_result"),
            "accepted_pass": False,
            "simulated": ghidra.get("simulated", False),
            "returncode": ghidra.get("returncode"),
            "tool_version_hint": ghidra.get("tool_version_hint"),
            "java_home": str(JAVA) if JAVA.is_dir() else None,
            "saw_main": "saw_main=true" in export_text,
            "decompiled_main": "decompiled_main=true" in export_text,
            "export_sha256": digest_bytes(export_text.encode("utf-8")) if export_text else None,
            "export_text": export_text,
            "limitations": ghidra.get("limitations", []),
            "stderr_tail": ghidra.get("stderr_tail", ""),
            "stdout_tail": ghidra.get("stdout_tail", ""),
        }
        store = Store(work / "ledger")
        try:
            artifact = store.add_record(
                kind="artifact",
                payload={"content_digest": store.put_blob(elf), "size": len(elf), "path_hint": "checksum_cli"},
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            )
            abc = runs["abc"]
            observation = store.add_record(
                kind="observation",
                payload={
                    "summary": "sandboxed dev ELF stdin abc",
                    "truncated": abc["truncated"],
                    "run": {
                        "command": ["./checksum_cli"],
                        "exit_code": abc["returncode"] if abc["returncode"] is not None else -1,
                        "observed_status": "passed" if abc["execution_result"] == "passed" else "failed",
                    },
                },
                provenance="observed",
                execution_result="passed" if abc["execution_result"] == "passed" and not abc["truncated"] else "uncertain",
                applicability="valid",
                usage="support",
                verification_scope=dict(SCOPE),
                source_family="dev-elf-abc",
            )
            if report["ghidra"]["executed"]:
                ghidra_obs = store.add_record(
                    kind="observation",
                    payload={
                        "summary": "headless Ghidra export of the dev ELF",
                        "truncated": False,
                        "run": {
                            "command": ["analyzeHeadless"],
                            "exit_code": 0,
                            "observed_status": "passed",
                        },
                    },
                    provenance="observed",
                    execution_result="passed",
                    applicability="valid",
                    usage="background",
                    verification_scope={
                        "inputs": ["elf:" + report["elf_sha256"]],
                        "behaviors": ["function list and decompilation"],
                        "environments": ["linux-x86_64"],
                        "complete_output": True,
                    },
                    source_family="ghidra-dev-elf",
                )
            else:
                ghidra_obs = None
            claim = store.add_record(
                kind="claim",
                payload={
                    "statement": "On linux-x86_64, checksum_cli reads stdin abc and prints count=3 sum=294 with exit 0.",
                    "required_scope": dict(SCOPE),
                },
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=dict(SCOPE),
            )
            store.add_relation(
                "supports",
                observation,
                claim,
                {"statement": "sandboxed execution captured that stdout and a zero exit", "method": "explicit"},
            )
            store.add_relation(
                "derived_from",
                observation,
                artifact,
                {"statement": "the observation is from this ELF bytes", "method": "explicit"},
            )
            decision = store.decision(claim)
            store.verify_integrity()
            report["ledger"] = {
                "artifact": artifact,
                "observation": observation,
                "ghidra_observation": ghidra_obs,
                "claim": claim,
                "accepted_pass": decision["accepted_pass"],
                "execution_result": decision["execution_result"],
                "independent_support_count": decision["independent_support_count"],
                "not_universal": decision["not_universal"],
                "notes": decision["notes"],
            }
        finally:
            store.close()
    abc_ok = report["runs"]["abc"]["stdout"] == "count=3 sum=294\n" and report["runs"]["abc"]["returncode"] == 0
    fail_ok = report["runs"]["fail"]["returncode"] not in (0, None) and report["runs"]["fail"]["execution_result"] == "failed"
    report["executed"] = bool(abc_ok and fail_ok and report["ghidra"]["executed"])
    report["sandbox_executed"] = bool(abc_ok and fail_ok)
    report["analysis_chain_executed"] = report["executed"]
    report["limitations"] = [
        "synthetic sample only; zlib 1.4 was not built or compared",
        "accepted_pass covers stdin abc on this host only",
        "Ghidra decompilation is a static observation and does not prove the runtime claim",
        "network namespace availability is whatever the sandbox probe reported",
    ]
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "executed": report["executed"],
        "sandbox_executed": report["sandbox_executed"],
        "ghidra_executed": report["ghidra"]["executed"],
        "ghidra_result": report["ghidra"]["execution_result"],
        "accepted_pass": report["ledger"]["accepted_pass"],
        "saw_main": report["ghidra"]["saw_main"],
        "wrote": str(OUT),
    }, indent=2))
    return 0 if report["sandbox_executed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
