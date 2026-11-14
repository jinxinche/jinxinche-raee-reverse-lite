# Frozen v1 scope

Frozen on 2026-11-14, before implementation of the evidence ledger. Later phases may not widen this to chase an easier target or a softer gate.

## Product

- New repository. `jinxinche/RAEE` is a read-only method reference. It was cloned to `/tmp/raee-ref` at `86eefae793fa1c67b69716690b01cf0dece8dc03` and not modified.
- v1 analyzes Linux x86-64 ELF programs that are controllable from a CLI, plus functions that can be isolated from those programs.
- Interfaces in scope for the whole project: CLI, MCP, and an offline HTML report. This tree implements a minimal CLI. MCP and HTML are specified and not implemented.
- First native static engine: Ghidra. It was installed and executed headless on the synthetic dev sample (Phase 2 evidence). It was not run on the frozen real target.
- JS/Electron, unknown file formats, and SDK wrappers are extension boundaries. `raee_reverse.interfaces` defines adapter results that stay `not_executed` when the engine is missing. They are not implemented.

## Python and CI

- Minimum: CPython 3.11. 3.10 is outside support because its last release was 3.10.22 on 2026-10-01 and the series is end of life.
- Maximum stable: CPython 3.15 (3.15.2 observed). 3.16 is alpha and is excluded.
- Declared range: `>=3.11,<3.16`.
- Core CI matrix, required: `ubuntu-latest`, `windows-latest`, and `macos-latest`, each on Python 3.11 and 3.15. Workflow: `.github/workflows/core.yml`.
- Local execution of that matrix: **not done**. This VM ran CPython 3.12.3 only. A green local run is not a hosted CI result.
- Native Ghidra is not part of the core matrix. It runs only where JDK 25 and Ghidra 12.2 are actually installed.

## Stress tiers

- Standard tier (1,000 conclusions, 10,000 evidence rows, 50,000 relations, concurrency 1/2/4/8/16, 30 minutes, 20 target runs) is required in Phase 6. It was **not** executed.
- Extended tier (10,000 / 100,000 / 250,000) is **not required** for v1. This VM has 4 CPUs and a memory balloon; the extended tier is recorded as out of v1 scope rather than as a pass.

## Out of scope for the claims this tree makes

- A compatible reimplementation of zlib.
- An improvement over zlib.
- A comparison against REA.
- Cross-OS proof. Core tests are written to run on the matrix; only 3.12.3/Linux has been executed here.
- Blind final acceptance. The same agent wrote the tests and the implementation.
