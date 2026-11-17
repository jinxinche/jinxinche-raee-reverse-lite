"""Record whether a live five-policy comparison can run on this host.

TCP probes do not send model requests and do not copy prices. The historical
records under docs/a18/routing_comparison.json and
docs/a18/routing_comparison_2026-11-15.json are not this file's default output.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.decision import load_profiles  # noqa: E402
from raee_reverse.routing_compare import (  # noqa: E402
    LOCAL_PORTS,
    PROVIDER_TCP_TARGETS,
    local_port_open,
    probe_record,
    tcp_probe,
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: record_routing_probe.py OUTPUT.json")
    profiles = load_profiles(REPO / "config" / "model_profiles.json", REPO / "config" / "prices.json")
    prices = json.loads((REPO / "config" / "prices.json").read_text(encoding="utf-8"))
    ports = {port: local_port_open(port) for port in LOCAL_PORTS}
    with ThreadPoolExecutor(max_workers=len(PROVIDER_TCP_TARGETS)) as pool:
        tcp_results = list(pool.map(lambda item: tcp_probe(item[0], item[1]), PROVIDER_TCP_TARGETS))
    binaries = {
        name: shutil.which(name)
        for name in ("ollama", "llama-server", "llama-cli", "vllm")
    }
    record = probe_record(profiles, prices, dict(os.environ), ports, tcp_results, binaries)
    uname = subprocess.run(["uname", "-srvm"], capture_output=True, text=True, check=False)
    record["observed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record["environment"] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uname": uname.stdout.strip(),
    }
    record["note"] = (
        "No model request was sent. Connected TCP ports are not endpoints configured "
        "for this project, and no price was copied into config/prices.json."
    )
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "executed": record["executed"],
        "savings_percent": record["savings_percent"],
        "tcp_hosts_connected": record["tcp_hosts_connected"],
        "model_calls": record["model_calls"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
