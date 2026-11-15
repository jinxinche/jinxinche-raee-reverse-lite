# Delivery report

One agent. The speed goal in `docs/phase4/GOAL.md` stays closed and missed. A different crc32 goal was frozen in `docs/phase4/GOAL_CRC32.md` before its measurement.

## Versions

- Tool: `raee-reverse-lite` 0.1.0.
- Python for the commands below: CPython 3.12.3 (`3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]`). Supported range `>=3.11,<3.16`.
- Host for the measurements: `Linux 6.12.113+ #1 SMP PREEMPT_DYNAMIC Fri Nov 13 20:22:28 UTC 2026 x86_64`, gcc 13, 4 CPUs, Intel Xeon.
- zlib: tag `v1.4`, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`.
- Ghidra: 12.2 public, with Temurin JDK 25.0.5. Not re-run on this slice.
- REA: `rea-agents` 6.9.0. `rea --version` printed `6.9.0`.
- GDB used only for the runtime attempt: `GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1`. `rizin` was not on `PATH`.

## Four-way status

**Implemented.** The ledger, sandbox, Ghidra adapter, CLI, MCP stdio server, offline HTML report, zlib 1.4 baseline, the five-policy comparison harness, the held-out checker and path guard, the crc32 PCLMULQDQ candidate, and the extended-tier probe and runner.

**Executed.**

- `12735f05` Actions: failure. Ubuntu passed; Windows and macOS failed. `docs/ci/12735f05.md`.
- `d38e889`, `0a74bed`, `345c7f8`, `45eff3c`, `772dfac`, `c661219`, `746addd`, and `27f9dde` Actions: 12 of 12 jobs succeeded on both the push run and the pull_request run for each of those commits. `docs/ci/27f9dde.md`.
- `31c3e00` push Actions: `macos-latest / py3.15` failed `tests/test_ledger_speed.py::test_support_batch_does_not_collapse` at about 8x. The pull_request run for that commit succeeded. `docs/ci/31c3e00.md`. The test was not deleted.
- Standard-tier load stopped at 10,041 relations and 21,000 records. Not a pass. `docs/a19/standard_tier.json`.
- Attempt 2 inserted 2,000 supports in 9.649 seconds and did not start the full tier. `docs/a19/attempt2.json`.
- Standard-tier v3 passed its own floors: load 19.814 seconds, mixed 1800.035 seconds, 50,003 relations. `docs/a19/standard_tier_v3.json`.
- LTO candidate missed the closed speed goal: decompress median ratio 0.9956544893408726 against 0.90, compress 1.0022963782068877 against 1.05. `docs/evidence/zlib_enhancement.json`.
- crc32 goal, second build, `make` exit 0 for both trees. Command: `python3 tools/measure_zlib_crc32.py /tmp/zlib-crc32-work /tmp/zlib-crc32-result.json`. Baseline median 0.00280024 seconds, candidate median 0.000744777 seconds, ratio 0.2659689883724252. Correct, including `cbf43926` for `123456789` and identical `minigzip` stdout for empty, `abc`, and `hello`. `enhancement_met` true for this one sample. `stable_improvement` false. `docs/evidence/zlib_crc32_goal.json`.
- An earlier candidate `make` exited 2 because the shared library did not link `crc32_z_pclmul_try`. That run is recorded in the same file and is not the acceptance measurement. Its ratio was 0.25433241847325494.
- Held-out check: `python3 tools/check_held_out.py /tmp/zlib-crc32-work/candidate/zlib-1.4/minigzip /tmp/zlib-crc32-work/candidate/zlib-1.4/crc32_bench /tmp/held-out-check.json`. `pass` true, `blind` false. Python zlib 1.3 agreed with `cbf43926`. GNU gzip 1.12 decompressed all five candidate gzip streams. `docs/evidence/held_out_check.json`.
- Routing availability: `python3 tools/record_routing_availability.py`. `executed` false, `savings_percent` null. `docs/a18/routing_comparison_2026-11-15.json`. No live model was called.
- REA runtime attempt: `python3 tools/run_rea_runtime.py /tmp/rea-runtime /tmp/rea-runtime.json /tmp/checksum_cli`. `comparison_complete` false. `docs/a18/rea_runtime_2026-11-15.json`.
- Extended probe: `python3 tools/probe_extended_tier.py /tmp/a19-extended-probe /tmp/a19-extended-probe.json`. Finished in 2.851 seconds. Projected 2336.889 seconds and 2,719,779,400 directory bytes. `start_allowed` true. `docs/a19/extended_probe.json`.
- Extended tier: `python3 tools/run_extended_tier.py /tmp/a19-extended /tmp/a19-extended-result.json /tmp/checksum_cli /tmp/a19-extended-probe.json`. `extended_tier_executed` true and `extended_tier_pass` true. Load 170.475 seconds, mixed 1801.876 seconds, 250,006 relations, 10,002 claims, 100,032 observations, 20 target runs, directory 682,324,385 bytes. Load P50/P95/P99 seconds: 0.000200465, 0.001171793, 0.004716798 (sample size 360,000). Mixed P50/P95/P99 seconds: 0.000451200, 0.518006233, 2.978321967 (sample size 13,081). `docs/a19/extended_tier.json`.

**Unverified.** Whether another compiler or another machine emits the same crc32 ratio. The ratio is one pair of 21-run medians on this host. Whether REA and this tool differ on a scored runtime task set. Whether a live five-policy comparison would change cost. Hosted CI for this commit is not this local pytest run.

**Not done.** A live five-policy comparison. A completed REA runtime comparison. A blind acceptance set. Optional REA engines were not installed. Network namespaces were not available. No savings percentage is claimed. The closed zlib wall-time goal was not met and was not reopened.

## Live models

No. `config/model_profiles.json` has no available model profile and no endpoint. `config/prices.json` is empty and `observed_at` is null. None of the checked provider API key variables were set. Local ports 11434, 1234, and 8080 did not accept a connection. The harness in `src/raee_reverse/routing_compare.py` is covered by unit tests with a scripted transport. Those tests set `counts_as_project_comparison` false. They are not the comparison.

## New zlib goal

`docs/phase4/GOAL_CRC32.md`. Median in-process `crc32()` time on one 16 MiB buffer, candidate at most 90% of the zlib 1.4 baseline, one thread, same tarball, default `./configure && make`, not `CFLAGS="-O3 -flto"`. Outcome on the clean rebuild: pass for this sample, ratio 0.2659689883724252. Not a stable improvement. The closed goal remains missed.

## Acceptance

Not blind. One agent wrote the inputs, the checker, and the candidate. Isolation is the path guard in the measurement process, a manifest hash in `targets/zlib/held_out/SEAL.sha256`, and the absence of stored expected gzip bytes. The published CRC `cbf43926` and GNU gzip 1.12 are external checks. An injected CRC `00000000` fails `judge_crc`. `targets/zlib/NON_BLIND.md` is unchanged.

## Extended tier

Budget and floors were written in `docs/a19/EXTENDED_TIER_BUDGET.md` before the probe. Cap: projected seconds at most 4,200 and directory at most 4 GiB. The probe was inside the cap, so the full run started. It passed the declared floors. The 10,041-relation stop and attempt 2 stay failures. The standard-tier v3 pass stays a pass of the standard floors.

## REA

`rea-agents` 6.9.0. Task: `/tmp/checksum_cli` with stdin `abc`, contract line `count=3 sum=294`. Sample size of scored pairs: 0. `capture-process` returned signal 9 `idle_timeout` and did not show the contract line. `debug-with-gdb run` reported that no executable was loaded. This is an uncompleted comparison, not a ranking.

## Local tests on this tree

Commands, in order, on this host with CPython 3.12.3:

- `python3 -m pip install .`
- `python3 -m pytest -q --tb=line` : 1 failed, 92 passed, 1 warning, in 6.70s. `tests/test_scheduler.py::test_dependencies_retries_cancel_and_exclusivity` asserted `RUNNING == CANCELLED`. The scheduler thread then raised `task not found` while the fixture was closing the store. The test was not changed and was not skipped.
- `python3 -m pytest tests/test_scheduler.py::test_dependencies_retries_cancel_and_exclusivity -q --tb=line` : 1 passed in 0.43s.
- `python3 -m pytest -q --tb=line` : 93 passed in 6.79s.
- `python3 tools/check_collection_floor.py` printed `collection floor matches 93 tests`.
- `python3 -m raee_reverse --version` printed `raee-reverse-lite 0.1.0`.

Hosted CI for `52d4a9e8b4918f75653b2912602a23d1cf510088`:

- Push: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43695797385 failure.
- Pull request: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43695808476 failure.

On the pull request run, Ubuntu and macOS passed for 3.11 and 3.15. Both Windows jobs failed in `python -m pytest`. `tests/test_frozen_records.py::test_closed_failures_are_unchanged` saw SHA-256 `fb477586213a3b73dc55aeee71d0e78f93d2dc986da4c00d41257eed36de79d8` for `docs/phase4/GOAL.md` instead of `d20552ca4b56fb3db6c2ca8e498e0cde1fd0712d0f3700b791793650998bf2eb`. `tests/test_held_out.py::test_manifest_is_not_blind_and_the_seal_matches` saw the seal miss. Windows checkout rewrote those text files to CRLF. The tests were not deleted. The checker and the frozen-record test now hash LF text, and `.gitattributes` asks Git to keep those files as LF. `docs/ci/52d4a9e.md`.

The 31c3e00 macOS Python 3.15 failure stays on the record.
