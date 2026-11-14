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
- `d38e889`, `0a74bed`, `345c7f8`, `45eff3c`, `772dfac`, `c661219`, `746addd`, and `27f9dde` Actions: 12 of 12 jobs succeeded on both the push run and the pull_request run for each of those commits. `docs/ci/27f9dde.md`.
- Dev ELF and zlib `minigzip` headless Ghidra runs, including a decompiled `crc32`.
- Baseline dev check without reading the final-acceptance file, then `accept.py`: 8/8 final inputs matched collected surfaces. Non-blind. Level `-9` stayed `not_compared`.
- LTO candidate: decompress median 99.6% of baseline. Enhancement not met.
- REA 6.9.0 `analyze` and `function checksum` on the same ELF. Both static runs showed modulus `0xfff1`. Sample size 1.
- Standard-tier load stopped at 10,041 relations and 21,000 records. Not a pass. `docs/a19/standard_tier.json`.
- A second probe, declared in `docs/a19/ATTEMPT2_BUDGET.md` before it ran, inserted 2,000 supports in 9.649 seconds and did not start the full tier. `standard_tier_pass` is false. `docs/a19/attempt2.json`.
- After the ledger change, a third budget was declared in `docs/a19/ATTEMPT3_BUDGET.md`. The probe projected 1,940 seconds, under the 2,700 second cap. `python3 tools/run_standard_tier.py /tmp/a19-standard-v3 /tmp/a19-standard-v3-result.json /tmp/checksum_cli` then exited 0. `standard_tier_executed` is true and `standard_tier_pass` is true. Load 19.814 seconds, mixed phase 1800.035 seconds, 50,003 relations, 20 target runs, retraction cleared `accepted_pass`, cancel state `CANCELLED`. `docs/a19/standard_tier_v3.json`. The earlier failure files were not changed.

**Unverified.** Whether another compiler emits the same gzip bytes. Whether REA and this tool differ on a larger task set. Latency percentiles for the standard tier were not recorded.

**Not done.** A faster zlib. A blind acceptance set. The extended stress tier. Optional REA engines (Hopper, IDA, JADX, Kuna) were not installed. Network namespaces were not available (`unshare` returned operation not permitted). REA was not asked to execute the ELF, so runtime behavior is not a compared surface. The five routing policies in the decision-unit spec were not executed (`docs/a18/routing_comparison.json`, `executed` false). No savings percentage is claimed.

## Commands run on the c661219 tree

These ran on the working tree that was committed as `c6612192b5e05d2a5c4c84daa57c0bb3d35099f7`, before that commit. Hosted pytest for that SHA is the Actions result above, not this local run.

- `python3 -m pip install .`
- `python3 -m raee_reverse --version` printed `raee-reverse-lite 0.1.0`.
- `python3 -m pytest -q` : 54 passed in 4.38s.
- `python3 -m raee_reverse --root /tmp/rrl-a20 init`, then `claim add` for the README statement. Claim id `a3ff1af276f8405aad230b79b13e013d`. `gate` on that id exited 2. `report --out /tmp/rrl-a20/report.html` wrote 901 bytes starting with `<!DOCTYPE html>`.
- `python3 /tmp/a19-attempt2-probe.py`. The same bytes are `tools/probe_a19_attempt2.py`, SHA-256 `c3afa1f8cd001986070c03725912974b5207f0bb1e98cd4db03c96a70008dffa`. It inserted 2,000 supports in 9.649 seconds and did not start the full tier.

## Known gaps

- The 10,041-relation stop and the second probe remain failures. They are not this run. Support rates before and after the ledger change are in `docs/a19/ledger_fix_rates.json`.
- Review target `746addd657822b01ec6a328ebfb5cf925c8d139e` has green Actions on both runs: push https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591930851 and pull request https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591936161. Six jobs succeeded in each run. That commit reviews `c661219` and does not change Python code. The commit that adds this paragraph is newer than `746addd`.
- `c6612192b5e05d2a5c4c84daa57c0bb3d35099f7` also has green Actions: push https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591711285 and pull request https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43591714049. The commands below were run on the working tree that became `c661219`, before that commit.
- Final acceptance is non-blind (`targets/zlib/NON_BLIND.md`).
- REA remains one static sample. No optional engines were installed, and no ranking was computed.
