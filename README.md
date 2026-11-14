# RAEE Reverse Lite

Local evidence ledger for a small reverse-engineering workflow. Version 0.1.0 records requirements, artifacts, observations, claims, retractions, and task state. It does not reimplement a target program, and it has not been compared with REA.

The method reference is [jinxinche/RAEE](https://github.com/jinxinche/RAEE) (read-only). This repository does not modify that one.

## Install

```bash
python -m pip install .
python -m raee_reverse --version
```

Python range: 3.11 up to, and not including, 3.16. This VM executed the tests on CPython 3.12.3. The core CI matrix is Linux, Windows, and macOS on 3.11 and 3.15; a hosted run is a property of GitHub Actions for a specific commit, not of this README.

There are no runtime dependencies. `pytest` is a test extra (`pip install ".[dev]"`).

## Minimal CLI

`ok: true` means the command finished. It is not a verification pass. `rrl gate` exits 0 only when that claim's `accepted_pass` is true, and exits 2 otherwise.

```bash
python -m raee_reverse --root /tmp/rrl-demo init
python -m raee_reverse --root /tmp/rrl-demo claim add \
  --statement "stdin abc prints count=3 sum=294" \
  --scope-json '{"inputs":["stdin:abc"],"behaviors":["prints-sum"],"environments":["linux-x86_64"],"require_complete_output":true,"complete_output":true}'
python -m raee_reverse --root /tmp/rrl-demo gate CLAIM_ID
```

`tests/test_sandbox_cli.py::test_cli_gate_and_retraction` runs init, a failing gate, a linked observation, a passing gate, a retraction, and a failing gate again.

## What was executed

- Phase 0 notes: `docs/phase0/`.
- Unit tests: `python -m pytest`.
- Synthetic ELF plus headless Ghidra 12.2: `docs/phase2/DEV_SAMPLE.md` and `docs/evidence/phase2_dev_sample.json`.

## What is not in this tree

- MCP server, offline HTML report, zlib 1.4 build, any improved clone, REA comparison, standard stress tier, hosted CI result (until Actions runs on the commit you are looking at).

Task states: `docs/tasks/graph.json`. One agent wrote them. `SUCCEEDED` on a scheduler task is not `accepted_pass`.
