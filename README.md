# RAEE Reverse Lite

Local evidence ledger for a small reverse-engineering workflow. Version 0.1.0 records requirements, artifacts, observations, claims, retractions, and task state. It does not reimplement zlib. A one-sample static comparison with REA 6.9.0 is in `docs/a18/REA_COMPARISON.md`. That comparison is not a suite score.

The method reference is [jinxinche/RAEE](https://github.com/jinxinche/RAEE) (read-only). This repository does not modify that one.

## Install

These commands were run on this VM with CPython 3.12.3:

```bash
python3 -m pip install .
python3 -m raee_reverse --version
```

`python3 -m raee_reverse --version` printed `raee-reverse-lite 0.1.0`.

Python range: 3.11 up to, and not including, 3.16. The core CI matrix is Linux, Windows, and macOS on 3.11 and 3.15. Hosted results are per commit: `docs/ci/12735f05.md` is a failure, and `docs/ci/0a74bed.md`, `docs/ci/45eff3c.md`, and `docs/ci/772dfac.md` are successes for those SHAs.

There are no runtime dependencies. `pytest` is a test extra (`pip install ".[dev]"`).

## Minimal CLI

`ok: true` means the command finished. It is not a verification pass. `rrl gate` exits 0 only when that claim's `accepted_pass` is true, and exits 2 otherwise.

This flow was run with `--root /tmp/rrl-readme`. The gate exited 2 because the new claim had no support:

```bash
python3 -m raee_reverse --root /tmp/rrl-readme init
python3 -m raee_reverse --root /tmp/rrl-readme claim add \
  --statement "stdin abc prints count=3 sum=294" \
  --scope-json '{"inputs":["stdin:abc"],"behaviors":["prints-sum"],"environments":["linux-x86_64"],"require_complete_output":true,"complete_output":true}'
python3 -m raee_reverse --root /tmp/rrl-readme gate CLAIM_ID
python3 -m raee_reverse --root /tmp/rrl-readme report --out /tmp/rrl-readme/report.html
```

`tests/test_sandbox_cli.py::test_cli_gate_and_retraction` also runs a linked observation, a passing gate, and a retraction.

## What was executed

- Phase 0 notes: `docs/phase0/`.
- `python3 -m pytest -q` on this VM, on the tree that added the second A19 probe: 54 passed in 4.38s.
- Synthetic ELF plus headless Ghidra 12.2: `docs/phase2/DEV_SAMPLE.md`.
- zlib 1.4 sandbox build and sealed surfaces: `docs/phase2/ZLIB.md`. Acceptance is non-blind.
- Compatible baseline: `generated/zlib-baseline/`. It matched the sealed surfaces. Reproduction copy: `repro/zlib-baseline/`.
- LTO candidate missed the frozen speed goal: `docs/evidence/zlib_enhancement.json`.
- REA 6.9.0 static comparison: `docs/a18/REA_COMPARISON.md`.
- Standard stress tier: not completed. The stopped load remains in `docs/a19/standard_tier.json`. A later probe did not start the full tier: `docs/a19/attempt2.json`.

Task states: `docs/tasks/graph.json`. One agent wrote them. A scheduler `SUCCEEDED` is not `accepted_pass`.
