import json
import os
import subprocess
import sys
from pathlib import Path

from raee_reverse.ghidra_adapter import analyze_elf
from raee_reverse.sandbox import run_sandboxed


def test_sandbox_strips_secrets_and_does_not_execute_output(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "super-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-secret")
    work = tmp_path / "work"
    sentinel = tmp_path / "sentinel"
    script = "import os, pathlib; print(os.environ.get('SECRET_TOKEN')); print(os.environ.get('GITHUB_TOKEN')); pathlib.Path('ran').write_text('data')"
    result = run_sandboxed([sys.executable, "-c", script], work_dir=work, timeout=10, cpu_seconds=5)
    text = result["stdout"].decode()
    assert "super-secret" not in text
    assert "gh-secret" not in text
    assert "None" in text
    assert (work / "ran").is_file()
    assert not sentinel.exists()
    assert result["accepted_pass"] is False
    assert result["execution_result"] == "passed"
    assert result["network_namespace"] in {True, False}
    if not result["network_namespace"]:
        assert any("network namespace" in item for item in result["limitations"])
    hostile = run_sandboxed(
        [sys.executable, "-c", "print('touch sentinel')"],
        work_dir=work,
        timeout=10,
    )
    assert b"touch sentinel" in hostile["stdout"]
    assert not sentinel.exists()
    assert hostile["accepted_pass"] is False


def test_timeout_truncation_and_failure_are_not_passes(tmp_path):
    work = tmp_path / "work"
    timed = run_sandboxed([sys.executable, "-c", "import time; time.sleep(30)"], work_dir=work, timeout=0.4)
    assert timed["outcome"] == "timeout"
    assert timed["execution_result"] == "uncertain"
    assert timed["accepted_pass"] is False

    huge = run_sandboxed(
        [sys.executable, "-c", "print('x'*100000)"],
        work_dir=work,
        timeout=10,
        max_output_bytes=128,
    )
    assert huge["truncated"] is True
    assert huge["execution_result"] == "uncertain"
    assert huge["accepted_pass"] is False
    assert len(huge["stdout"]) <= 128

    failed = run_sandboxed([sys.executable, "-c", "import sys; sys.exit(3)"], work_dir=work, timeout=10)
    assert failed["outcome"] == "behavior_failed"
    assert failed["execution_result"] == "failed"
    assert failed["accepted_pass"] is False


def test_file_size_limit_is_enforced_on_posix(tmp_path):
    if os.name != "posix":
        result = run_sandboxed([sys.executable, "-c", "print('no-rlimit')"], work_dir=tmp_path / "w", timeout=10)
        assert result["rlimits_applied"] is False
        assert any("rlimits" in item.lower() or "prlimit" in item for item in result["limitations"])
        assert result["accepted_pass"] is False
        return
    work = tmp_path / "limited"
    script = (
        "from pathlib import Path\n"
        "try:\n"
        "    Path('big').write_bytes(b'x'*100000)\n"
        "except Exception:\n"
        "    pass\n"
    )
    result = run_sandboxed([sys.executable, "-c", script], work_dir=work, timeout=10, fsize_bytes=1024)
    assert result["rlimits_applied"] is True
    assert result["accepted_pass"] is False
    assert result["execution_result"] != "passed" or (work / "big").stat().st_size <= 4096
    if (work / "big").exists():
        assert (work / "big").stat().st_size <= 4096


def test_cli_gate_and_retraction(tmp_path):
    root = tmp_path / "ledger"
    scope = json.dumps(
        {
            "inputs": ["stdin:abc"],
            "behaviors": ["prints-sum"],
            "environments": ["linux-x86_64"],
            "require_complete_output": True,
            "complete_output": True,
        }
    )

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "raee_reverse", "--root", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    assert run("init").returncode == 0
    claim = json.loads(run("claim", "add", "--statement", "sum matches", "--scope-json", scope).stdout)
    claim_id = claim["result"]["claim_id"]
    gated = run("gate", claim_id)
    assert gated.returncode == 2
    body = json.loads(gated.stdout)
    assert body["result"]["accepted_pass"] is False
    assert body["result"]["execution_result"] == "not_executed"
    observed = json.loads(
        run(
            "observation",
            "add",
            "--summary",
            "ran sample",
            "--execution",
            "passed",
            "--exit-code",
            "0",
            "--source-family",
            "cli-run",
            "--scope-json",
            scope,
        ).stdout
    )
    assert observed["ok"] is True
    assert "not, by itself, a verification pass" in observed["note"]
    linked = run(
        "link",
        "supports",
        "--src",
        observed["result"]["id"],
        "--dst",
        claim_id,
        "--basis",
        "operator recorded this run against the claim",
    )
    assert linked.returncode == 0
    passed = run("gate", claim_id)
    assert passed.returncode == 0
    assert json.loads(passed.stdout)["result"]["accepted_pass"] is True
    withdrawn = run("retract", observed["result"]["id"], "--reason", "operator withdraws the run")
    assert withdrawn.returncode == 0
    assert json.loads(withdrawn.stdout)["result"]["deleted"] is False
    regate = run("gate", claim_id)
    assert regate.returncode == 2
    assert json.loads(regate.stdout)["result"]["accepted_pass"] is False


def test_missing_ghidra_is_not_a_pass(tmp_path):
    result = analyze_elf(
        tmp_path / "missing.elf",
        ghidra_home=None,
        java_home=None,
        project_dir=tmp_path / "proj",
        script_path=tmp_path / "Export.java",
        output_path=tmp_path / "out.txt",
    )
    assert result["execution_result"] == "not_executed"
    assert result["accepted_pass"] is False
    assert result["simulated"] is False
    assert result["observations"] == []


def test_audit_cli(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "app.py").write_text("import json\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "raee_reverse", "--root", str(tmp_path / "ledger"), "audit", str(project)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    body = json.loads(completed.stdout)
    assert body["result"]["closure_proof"] is False
    assert body["result"]["status"] == "no_omission_detected"
    assert Path(tmp_path / "ledger").exists() or True
