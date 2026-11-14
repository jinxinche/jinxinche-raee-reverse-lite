# Delivery report

One agent. The speed goal in `docs/phase4/GOAL.md` stays closed and missed. No new enhancement goal was opened.

## Versions

- Tool: `raee-reverse-lite` 0.1.0. On the working tree committed as `c661219`, `python3 -m raee_reverse --version` printed that string.
- Python for that command: CPython 3.12.3 (`3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]`). Supported range `>=3.11,<3.16`.
- zlib: tag `v1.4`, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`. Not rebuilt on `c661219`.
- Ghidra: 12.2 public, with Temurin JDK 25.0.5. Distro JDK 21 cannot launch it. Not re-run on `c661219`.
- REA: `rea-agents` 6.9.0. `rea --version` printed `6.9.0` in the earlier install. Not re-run on `c661219`.
- Node used for that install: v22.23.4.

## Four-way status

**Implemented.** The ledger, sandbox, Ghidra adapter, minimal CLI, MCP stdio server, offline HTML report, zlib 1.4 baseline, reproduction pack, and attribution helpers.

**Executed.**

- `12735f05` Actions: failure. Ubuntu passed; Windows and macOS failed. `docs/ci/12735f05.md`.
- `d38e889`, `0a74bed`, `345c7f8`, `45eff3c`, `772dfac`, and `c661219` Actions: 12 of 12 jobs succeeded on both the push run and the pull_request run for each of those commits. `docs/ci/772dfac.md` and `docs/ci/c661219.md`.
- Dev ELF and zlib `minigzip` headless Ghidra runs, including a decompiled `crc32`.
- Baseline dev check without reading the final-acceptance file, then `accept.py`: 8/8 final inputs matched collected surfaces. Non-blind. Level `-9` stayed `not_compared`.
- LTO candidate: decompress median 99.6% of baseline. Enhancement not met.
- REA 6.9.0 `analyze` and `function checksum` on the same ELF. Both static runs showed modulus `0xfff1`. Sample size 1.
- Standard-tier load stopped at 10,041 relations and 21,000 records. Not a pass. `docs/a19/standard_tier.json`.
- A second probe, declared in `docs/a19/ATTEMPT2_BUDGET.md` before it ran, inserted 2,000 supports in 9.649 seconds and did not start the full tier. `standard_tier_pass` is false. `docs/a19/attempt2.json`.

**Unverified.** Whether another compiler emits the same gzip bytes. Whether REA and this tool differ on a larger task set. Whether the ledger can finish 50,000 relations if the reevaluation cost is reduced.

**Not done.** A faster zlib. A blind acceptance set. The standard stress tier and the extended tier. Optional REA engines (Hopper, IDA, JADX, Kuna) were not installed. Network namespaces were not available (`unshare` returned operation not permitted). REA was not asked to execute the ELF, so runtime behavior is not a compared surface.

## Commands run on the c661219 tree

These ran on the working tree that was committed as `c6612192b5e05d2a5c4c84daa57c0bb3d35099f7`, before that commit. Hosted pytest for that SHA is the Actions result above, not this local run.

- `python3 -m pip install .`
- `python3 -m raee_reverse --version` printed `raee-reverse-lite 0.1.0`.
- `python3 -m pytest -q` : 54 passed in 4.38s.
- `python3 -m raee_reverse --root /tmp/rrl-a20 init`, then `claim add` for the README statement. Claim id `a3ff1af276f8405aad230b79b13e013d`. `gate` on that id exited 2. `report --out /tmp/rrl-a20/report.html` wrote 901 bytes starting with `<!DOCTYPE html>`.
- `python3 /tmp/a19-attempt2-probe.py`. The same bytes are `tools/probe_a19_attempt2.py`, SHA-256 `c3afa1f8cd001986070c03725912974b5207f0bb1e98cd4db03c96a70008dffa`. It inserted 2,000 supports in 9.649 seconds and did not start the full tier.

## Known gaps

- A19 remains queued. The standard tier did not reach its declared floors. The 10,041-relation stop remains a failure. The second probe did not start the 1,800 second phase or the 20 target runs.
- Review target `c6612192b5e05d2a5c4c84daa57c0bb3d35099f7` has green Actions on both runs: push https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591711285 and pull request https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591714049. Six jobs succeeded in each run. The commit that adds this paragraph is newer than `c661219` and is not that result.
- `772dfac504843adc33d336167dc464de7fb4284b` also has green Actions: push https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43588199093 and pull request https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43588204438. A review that named only `45eff3c` was not a review of `772dfac`.
- Final acceptance is non-blind (`targets/zlib/NON_BLIND.md`).
- REA remains one static sample. No optional engines were installed, and no ranking was computed.
