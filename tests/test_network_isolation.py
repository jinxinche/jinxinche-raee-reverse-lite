"""Network isolation is claimed only when a connect probe confirmed it."""

import json
import socket
import subprocess
import sys
from pathlib import Path

from raee_reverse import netisolate
from raee_reverse.sandbox import run_sandboxed

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs" / "evidence" / "network_isolation.json"


def _listen():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    return listener


def test_connect_fails_only_when_isolation_is_confirmed(tmp_path):
    netisolate.reset_network_isolation_cache()
    listener = _listen()
    port = listener.getsockname()[1]
    try:
        result = run_sandboxed(
            netisolate.connect_check_argv(port),
            work_dir=tmp_path / "work",
            timeout=15,
            cpu_seconds=5,
        )
    finally:
        listener.close()
    stdout = result["stdout"]
    assert result["accepted_pass"] is False
    assert result["network_isolated"] in {True, False}
    assert isinstance(result["network_isolated"], bool)
    if result["network_isolated"]:
        assert b"CONNECT_OK" not in stdout
        assert b"CONNECT_FAIL" in stdout
        assert result["network_probe"]["confirmed"] is True
        assert result["network_probe"]["mechanism"] in {"unshare-rn", "bwrap-unshare-net", "seccomp-prctl"}
        assert result["network_probe"]["baseline_connect"] == "ok"
    else:
        assert result["network_isolated"] is False
        assert result["network_probe"]["confirmed"] is False
        assert result["network_probe"]["mechanism"] is None
    if b"CONNECT_OK" in stdout:
        assert result["network_isolated"] is False
    if result["network_namespace"]:
        assert result["network_isolated"] is True
        assert result["network_probe"]["mechanism"] in {"unshare-rn", "bwrap-unshare-net"}
    else:
        assert any("network namespace" in item for item in result["limitations"])


def test_unconfirmed_probe_records_network_isolated_false(tmp_path, monkeypatch):
    monkeypatch.setattr(
        netisolate,
        "probe_network_isolation",
        lambda: {
            "confirmed": False,
            "network_isolated": False,
            "network_namespace": False,
            "mechanism": None,
            "baseline_connect": "ok",
            "reason": "forced for the test",
            "attempts": [],
            "unshare_n": {"available": False, "detail": "forced"},
            "namespace_detail": "unshare -n available=False; forced",
        },
    )
    listener = _listen()
    port = listener.getsockname()[1]
    try:
        result = run_sandboxed(
            netisolate.connect_check_argv(port),
            work_dir=tmp_path / "open",
            timeout=15,
            cpu_seconds=5,
        )
    finally:
        listener.close()
    assert result["network_isolated"] is False
    assert result["network_namespace"] is False
    assert any("network namespace" in item for item in result["limitations"])
    assert any("network_isolated is false" in item for item in result["limitations"])
    if b"CONNECT_OK" in result["stdout"]:
        assert result["network_isolated"] is False


def test_seccomp_helper_does_not_claim_a_filter_it_failed_to_install():
    if sys.platform != "linux":
        assert sys.platform != "linux"
        return
    listener = _listen()
    port = str(listener.getsockname()[1])
    helper = Path(netisolate.helper_path())
    try:
        completed = subprocess.run(
            [sys.executable, str(helper), "--", sys.executable, "-c", netisolate.CONNECT_SOURCE, port],
            capture_output=True,
            timeout=15,
            check=False,
        )
    finally:
        listener.close()
    if completed.returncode == 3:
        assert b"seccomp filter was not installed" in completed.stderr
        return
    assert b"CONNECT_FAIL" in completed.stdout
    assert b"CONNECT_OK" not in completed.stdout


def test_committed_isolation_record_matches_its_stdout():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    stdout = record["stdout"]
    assert record["accepted_pass"] is False
    if record["network_isolated"]:
        assert "CONNECT_OK" not in stdout
        assert "CONNECT_FAIL" in stdout
        assert record["network_probe"]["confirmed"] is True
        assert record["network_probe"]["baseline_connect"] == "ok"
    else:
        assert record["network_isolated"] is False
        assert record["network_probe"]["confirmed"] is False
