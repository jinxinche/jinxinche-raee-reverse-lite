# Phase 2 dev-sample run

This is one executed chain on the synthetic ELF, not a zlib analysis and not a REA comparison.

Command that produced `docs/evidence/phase2_dev_sample.json` on this VM:

```bash
RRL_PHASE2_OUT=docs/evidence/phase2_dev_sample.json \
  GHIDRA_INSTALL_DIR=/tmp/ghidra-dl/ghidra_12.2_PUBLIC \
  JAVA_HOME=/tmp/jdk25/jdk-25.0.5+8 \
  python3 tools/run_phase2_dev_sample.py
```

The script's default output path is `docs/evidence/local/`, which is gitignored, so a later run does not overwrite the committed record unless `RRL_PHASE2_OUT` points at it.

## What the record contains

- Host: Linux x86_64, CPython 3.12.3.
- ELF SHA-256 `89f0c6003fe2846b6d3b88d71f031340457c4977dc070130c7d8b518a561d9ae` for that build. A rebuild is not expected to hash the same, because the binary includes paths and debug info. `tests/test_phase2_evidence.py` recompiles and checks stdout, not that hash.
- Sandbox stdin `abc`: stdout `count=3 sum=294`, exit 0, rlimits applied, network namespace **not** applied.
- `--fail`: same stdout, exit 3, `execution_result` `failed`.
- Ghidra 12.2 public, Temurin 25.0.5, `analyzeHeadless` exit 0. The export lists `checksum` and `main` and decompiles the modulus as `0xfff1`. `ghidra.accepted_pass` is false. The decompilation is a static observation.
- Ledger `accepted_pass` is true only for the claim "stdin abc prints count=3 sum=294 and exits 0" on linux-x86_64. `not_universal` is true. Independent support count is 1 (the sandbox run). The Ghidra observation is `usage=background` and is not that support.

## Gate

Phase 2's gate is one real chain from input to a report, with a simulated adapter not counting. This chain used the Ghidra 12.2 process and the compiled ELF. The gate is met for the dev sample. It is not met for zlib 1.4, which has not been built.
