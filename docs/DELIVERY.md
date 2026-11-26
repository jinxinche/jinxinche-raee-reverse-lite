# Delivery report

One agent. The speed goal in `docs/phase4/GOAL.md` stays closed and missed. A different crc32 goal was frozen in `docs/phase4/GOAL_CRC32.md` before its measurement. A second minigzip wall-time goal was frozen in `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md` before its candidate was built. That attempt is closed as missed.

## Versions

- Tool: `raee-reverse-lite` 0.1.0.
- Python for the commands on this slice: CPython 3.12.3. Supported range `>=3.11,<3.16`.
- Host for the measurements on this slice: `Linux 6.12.113+ #1 SMP PREEMPT_DYNAMIC Mon Nov 16 16:06:22 UTC 2026 x86_64`, gcc 13, 4 CPUs, Intel Xeon.
- zlib: tag `v1.4`, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`.
- Ghidra: 12.2 public, with Temurin JDK 25.0.5. Not re-run on this slice.
- REA: `rea-agents` 6.9.0 from `/tmp/rea-6.9.0`. `rea --version` printed `6.9.0`.
- GDB: `GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1`. `rizin` was not on `PATH`. Apt has no `rizin` package. Radare2 was not substituted.
- GNU gzip 1.12. CPython's zlib is 1.3, which is not the zlib 1.4 under test.

## Four-way status

**Implemented.** The ledger, sandbox, Ghidra adapter, CLI, MCP stdio server, offline HTML report, zlib 1.4 baseline, the five-policy comparison harness, the held-out checker and path guard, the crc32 PCLMULQDQ candidate, the extended-tier probe and runner, a published-corpus acceptance checker, and the minigzip attempt-2 measurement script.

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
- REA runtime attempt: `python3 tools/run_rea_runtime.py /tmp/rea-runtime /tmp/rea-runtime.json /tmp/checksum_cli`. `comparison_complete` false. `docs/a18/rea_runtime_2026-11-15.json`. Scored pairs on that date: 0.
- Routing probe on 2026-11-17: `python3 tools/record_routing_probe.py docs/a18/routing_comparison_2026-11-17.json`. `executed` false, `savings_percent` null, `model_calls` 0. Ten provider hosts accepted TCP on port 443. No API key, no endpoint, and no price were present, so no model request was sent. `docs/a18/ROUTING_2026-11-17.md`.
- Published-corpus check, stock zlib 1.4 `minigzip`: `python3 tools/check_published_acceptance.py /tmp/zlib-base/zlib-1.4/minigzip /tmp/zlib-base/zlib-1.4/crc32_bench docs/evidence/published_acceptance_stock.json`. `pass` true, `blind` false, sample size 11. GNU gzip 1.12 and CPython zlib 1.3 agreed with the candidate bytes.
- The same check on the attempt-2 candidate: `pass` true, `blind` false, sample size 11. `docs/evidence/published_acceptance_attempt2.json`. The set was not used to edit the candidate.
- REA runtime on 2026-11-17: `python3 tools/run_rea_runtime.py /tmp/rea-runtime-2026 /tmp/rea-runtime-2026.json /tmp/checksum_cli`. `comparison_complete` true for four scored pairs. `ranking` false. `capture-process` still ended with signal 9 `idle_timeout` and did not show the contract line. One-shot `debug-with-gdb run` still reported `No executable file specified`. `docs/a18/rea_runtime_2026-11-17.json`.
- Minigzip attempt 2: `python3 tools/measure_zlib_minigzip_attempt2.py /tmp/zlib-minigzip-attempt2 /tmp/zlib-minigzip-attempt2.json`. Decompress median ratio 1.003810222421081 against 0.90. Compress median ratio 1.0277633298808058 against 1.05. Correct. `enhancement_met` false. `stable_improvement` false. `attempt_status` `closed_missed`. `docs/evidence/zlib_minigzip_attempt2.json`.
- Minigzip attempt 3: `python3 tools/measure_zlib_minigzip_attempt3.py /tmp/zlib-minigzip-attempt3 /tmp/zlib-minigzip-attempt3.json`. Decompress median ratio 0.9977490944434495 against 0.90. Compress median ratio 0.9976791199422619 against 1.05. Correct. `enhancement_met` false. `stable_improvement` false. `attempt_status` `closed_missed`. `docs/evidence/zlib_minigzip_attempt3.json`.
- Minigzip attempt 4: `python3 tools/measure_zlib_minigzip_attempt4.py /tmp/zlib-minigzip-attempt4 /tmp/zlib-minigzip-attempt4.json`. The metric is in-process gzip inflate and deflate, not sandboxed wall time. Decompress median ratio 1.1347656764517347 against 0.90. Compress median ratio 1.005786271052055 against 1.05. Correct. `enhancement_met` false. `stable_improvement` false. `attempt_status` `closed_missed`. `docs/evidence/zlib_minigzip_attempt4.json`. Changing that metric did not turn the earlier wall-time misses into passes.
- Extended probe: `python3 tools/probe_extended_tier.py /tmp/a19-extended-probe /tmp/a19-extended-probe.json`. Finished in 2.851 seconds. Projected 2336.889 seconds and 2,719,779,400 directory bytes. `start_allowed` true. `docs/a19/extended_probe.json`.
- Extended tier: `python3 tools/run_extended_tier.py /tmp/a19-extended /tmp/a19-extended-result.json /tmp/checksum_cli /tmp/a19-extended-probe.json`. `extended_tier_executed` true and `extended_tier_pass` true. Load 170.475 seconds, mixed 1801.876 seconds, 250,006 relations, 10,002 claims, 100,032 observations, 20 target runs, directory 682,324,385 bytes. Load P50/P95/P99 seconds: 0.000200465, 0.001171793, 0.004716798 (sample size 360,000). Mixed P50/P95/P99 seconds: 0.000451200, 0.518006233, 2.978321967 (sample size 13,081). `docs/a19/extended_tier.json`.

**Unverified.** Whether another compiler or another machine emits the same crc32 ratio or the same attempt-2 minigzip ratio. Each ratio is one pair of medians on this host. Whether the four-task REA sample would look the same on another host. Whether a live five-policy comparison would change cost. Whether the attempt-3 16-byte copy reduces inflate CPU time. That CPU time was not clocked. Hosted CI for `dce3995` is recorded below. This paragraph is a later commit, so it is not itself that green SHA. Attempt 4 later clocked in-process inflate and deflate on one host. That ratio is `docs/evidence/zlib_minigzip_attempt4.json`. It does not replace the attempt-3 wall-time result.

**Not done.** A live five-policy comparison. Prices and a callable model endpoint were missing, so savings stays null. A blind acceptance set. The Canterbury check is explicitly not blind: the same agent selected the corpus, wrote the harness, and wrote the attempt-2 candidate. `rizin` is still absent. Network namespaces were not available. No savings percentage is claimed. The closed zlib wall-time goal was not met and was not reopened. Attempt 2 on the same metric was also missed and was not turned into a pass. Attempt 3 on that metric was missed and was not turned into a pass. Attempt 4 changed the clock to in-process time and missed that bar. Changing the metric did not turn those three misses into passes. This attempt did not run the held-out or Canterbury checkers and did not invent a blind-set result.

## Live models

No comparison was executed. `config/model_profiles.json` has no available model profile and no endpoint. `config/prices.json` is empty and `observed_at` is null. None of the checked provider API key variables were set. Local ports 11434, 1234, and 8080 did not accept a connection. No local model binary was on `PATH`. Ten public API hosts accepted TCP on port 443 on 2026-11-17. That is not an endpoint this project can call, and no price was invented from it. The harness in `src/raee_reverse/routing_compare.py` is covered by unit tests with a scripted transport. Those tests set `counts_as_project_comparison` false. They are not the comparison. The 2026-11-15 record is unchanged.

## New zlib goal

`docs/phase4/GOAL_CRC32.md`. Median in-process `crc32()` time on one 16 MiB buffer, candidate at most 90% of the zlib 1.4 baseline, one thread, same tarball, default `./configure && make`, not `CFLAGS="-O3 -flto"`. Outcome on the clean rebuild: pass for this sample, ratio 0.2659689883724252. Not a stable improvement. The closed goal remains missed.

`docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md` is the same minigzip wall-time metric as the closed goal: 4 MiB buffer, sandboxed process, 21-run median, decompress ratio at most 0.90, compress ratio at most 1.05. Both trees use `./configure && make` with no `CFLAGS` or `LDFLAGS` override. The candidate changes `minigzip` buffering and hooks the existing PCLMULQDQ crc32 path. Outcome: closed as missed. Decompress ratio 1.003810222421081. Compress ratio 1.0277633298808058. `stable_improvement` false.

`docs/phase4/GOAL_MINIGZIP_ATTEMPT3.md` keeps that metric and those bars. The candidate is a 16-byte SSE2 copy on the direct match path in `inflate_fast`. Outcome: closed as missed. Decompress ratio 0.9977490944434495. Compress ratio 0.9976791199422619. `stable_improvement` false.

`docs/phase4/GOAL_MINIGZIP_ATTEMPT4.md` is a different metric: median in-process gzip inflate time of the same 4 MiB buffer, with the same 0.90 and 1.05 bars. The candidate is that same 16-byte copy, not retuned. Outcome: closed as missed. Decompress ratio 1.1347656764517347. Compress ratio 1.005786271052055. `stable_improvement` false. The three wall-time attempts stay missed.

## Acceptance

The held-out set is not blind. One agent wrote those inputs, the checker, and the candidate. Isolation is the path guard in the measurement process, a manifest hash in `targets/zlib/held_out/SEAL.sha256`, and the absence of stored expected gzip bytes. The published CRC `cbf43926` and GNU gzip 1.12 are external checks. An injected CRC `00000000` fails `judge_crc`. `targets/zlib/NON_BLIND.md` is unchanged.

The Canterbury set under `targets/zlib/published_acceptance/` is also not blind. The inputs are the published corpus (`cantrbry.tar.gz`, SHA-256 `f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb`), not bytes invented for this candidate. Expected gzip bytes are not stored. The oracles are GNU gzip 1.12 and CPython zlib 1.3. The same agent selected the files, wrote the harness, and wrote the attempt-2 candidate, so `blind` stays false. The measurement process refuses that directory. Both the stock zlib 1.4 `minigzip` and the attempt-2 candidate passed all 11 files on this host. An injected CRC `00000000` fails `judge_observed_crc`.

## Extended tier

Budget and floors were written in `docs/a19/EXTENDED_TIER_BUDGET.md` before the probe. Cap: projected seconds at most 4,200 and directory at most 4 GiB. The probe was inside the cap, so the full run started. It passed the declared floors. The 10,041-relation stop and attempt 2 stay failures. The standard-tier v3 pass stays a pass of the standard floors.

## REA

`rea-agents` 6.9.0. The 2026-11-15 attempt stays scored-pairs 0: `capture-process` returned signal 9 `idle_timeout` and did not show `count=3 sum=294`, and `debug-with-gdb run` reported that no executable was loaded.

On 2026-11-17 those two failures were run again and still failed the same way. A persistent GDB session then ran `file` and `run < <stdin file>` for four stdin values (`abc`, empty, `a`, `hello`). This tool's sandbox ran the same bytes. All four pairs were scored and both sides matched the contract stdout. `comparison_complete` is true for that task set. `ranking` is false. Model cost is unknown. `rizin` is still absent. `docs/a18/REA_RUNTIME_2026-11-17.md`.

## Local tests on this tree

On this slice, after the measurements above, `python3 -m pip install .` and `python3 -m pytest -q --tb=line` : 104 passed in 6.96s. `python3 tools/check_collection_floor.py` printed `collection floor matches 104 tests`. The earlier 93-test run stays a record of that tree.

On the attempt-4 slice, after that measurement, `python3 -m pip install .` and `python3 -m pytest -q --tb=line` : 112 passed in 7.72s. `python3 tools/check_collection_floor.py` printed `collection floor matches 112 tests`.

Hosted CI for `dce39956bc96275342517d9aa307be2ffc743435` succeeded on both runs. Each run had six jobs: Ubuntu, Windows, and macOS, on Python 3.11 and 3.15.

- Push: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/44025474427 success.
- Pull request: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/44025503417 success.

`docs/ci/dce3995.md`. This paragraph is newer than `dce3995`.

Commands from the previous slice, in order, on that host with CPython 3.12.3:

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

Hosted CI for `4b469df2dd581591f03bb0b60170a4a97efda435`:

- Pull request: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43696080740 success. Six jobs, including Windows 3.11 and 3.15.
- Push: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43696077652 failure. `macos-latest / py3.11` failed `tests/test_ledger_speed.py::test_support_batch_does_not_collapse` with `1.124669541000003 < (0.05146579200001611 * 12)`, about 22x. The other five push jobs passed. The test was not deleted. The 12x bound stays under the pre-fix ratio of about 18. A second batch is required only when the first window exceeds 12x. `docs/ci/4b469df.md`.

Hosted CI for `af0f4df42ec8adac70ef72f35f99b55353aec15a` succeeded on both runs. Each run had six jobs: Ubuntu, Windows, and macOS, on Python 3.11 and 3.15.

- Push: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43696321259 success.
- Pull request: https://github.com/jinxinche/jinxinche-raee-reverse-lite/actions/runs/43696324483 success.

`docs/ci/af0f4df.md`. This paragraph is newer than `af0f4df`.
