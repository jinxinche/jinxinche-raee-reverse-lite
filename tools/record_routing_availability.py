"""Write the live-routing availability record. Does not call a model."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from raee_reverse.decision import load_profiles  # noqa: E402
from raee_reverse.routing_compare import LOCAL_PORTS, availability_record, local_port_open  # noqa: E402


def main() -> int:
    profiles = load_profiles(REPO / "config" / "model_profiles.json", REPO / "config" / "prices.json")
    prices = json.loads((REPO / "config" / "prices.json").read_text(encoding="utf-8"))
    ports = {port: local_port_open(port) for port in LOCAL_PORTS}
    record = availability_record(profiles, prices, dict(os.environ), ports)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "docs" / "a18" / "routing_comparison_2026-11-15.json"
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"executed": record["executed"], "savings_percent": record["savings_percent"], "missing": len(record["missing_conditions"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
