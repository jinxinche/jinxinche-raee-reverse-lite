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

Python range: 3.11 up to, and not including, 3.16. The core CI matrix is Linux, Windows, and macOS on 3.11 and 3.15. Hosted results are per commit: `docs/ci/12735f05.md` is a failure, and `docs/ci/0a74bed.md`, `docs/ci/c661219.md`, `docs/ci/746addd.md`, and `docs/ci/dce3995.md` are successes for those SHAs.

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
- `python3 -m pip install .` and `python3 -m pytest -q` on this VM after the ledger change: 57 passed in 6.49s.
- Synthetic ELF plus headless Ghidra 12.2: `docs/phase2/DEV_SAMPLE.md`.
- zlib 1.4 sandbox build and sealed surfaces: `docs/phase2/ZLIB.md`. Acceptance is non-blind.
- Compatible baseline: `generated/zlib-baseline/`. It matched the sealed surfaces. Reproduction copy: `repro/zlib-baseline/`.
- LTO candidate missed the frozen speed goal: `docs/evidence/zlib_enhancement.json`. That goal stays missed.
- A separate crc32 goal is in `docs/phase4/GOAL_CRC32.md`. Its measurement is `docs/evidence/zlib_crc32_goal.json`.
- Minigzip attempt 2 missed the same wall-time bar: `docs/phase4/ATTEMPT2_RESULT.md`. `stable_improvement` is false.
- REA 6.9.0 static comparison: `docs/a18/REA_COMPARISON.md`. The 2026-11-15 runtime attempt did not become a comparison. A 2026-11-17 run scored four pairs and is not a ranking: `docs/a18/REA_RUNTIME_2026-11-17.md`.
- The five routing policies were not executed. `docs/a18/routing_comparison_2026-11-17.json` has `executed` false and `savings_percent` null.
- Standard stress tier: the stopped load remains a failure in `docs/a19/standard_tier.json`. A later run passed the declared floors: `docs/a19/standard_tier_v3.json`.
- Held-out zlib inputs are in `targets/zlib/held_out/`. They are not blind. `targets/zlib/NON_BLIND.md` is unchanged.
- The Canterbury corpus under `targets/zlib/published_acceptance/` is a separate check. It is not blind. Expected gzip bytes are not stored.
- Extended stress tier passed the floors declared in `docs/a19/EXTENDED_TIER_BUDGET.md`. The earlier standard-tier failures stay failures. Result: `docs/a19/extended_tier.json`.
- `python3 -m raee_reverse --root /tmp/rrl-route route --task-json /tmp/route-task.json --profiles config/model_profiles.json --prices config/prices.json` chose `deterministic_tool` at T0. `accepted_pass` in that result was false. Record id `d5ead1c546af4d1398f43f7daf259908`.

Task states: `docs/tasks/graph.json`. One agent wrote them. A scheduler `SUCCEEDED` is not `accepted_pass`.
