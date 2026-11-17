# Minigzip attempt 3 result

The goal in `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.md` was committed before this measurement. That file was not edited after the numbers below. The closed goal in `docs/phase4/GOAL.md` and `docs/evidence/zlib_enhancement.json` stays missed. Attempt 2 in `docs/phase4/ATTEMPT2_RESULT.md` stays missed.

## Implemented

- Frozen goal: `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.md` and `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.json`, commit `1130d45dfdd04c46784b14e6974294c437c91eba`, before the candidate build.
- `tools/measure_zlib_minigzip_attempt3.py` builds two zlib 1.4 trees with `./configure && make` and no `CFLAGS` or `LDFLAGS` override. The candidate edits only `inffast.c`, after configure and before make. On the direct-from-output match in `inflate_fast`, a distance of at least 16 is copied 16 bytes at a time with `_mm_loadu_si128` and `_mm_storeu_si128`. Shorter distances and the remainder use zlib 1.4's three-byte loop. Window copies, `BUFLEN` 16384, `crc32.c`, and `minigzip.c` stay stock. One thread.
- The same command records a `/bin/true` floor and an empty `minigzip -d` floor. Those samples do not decide `enhancement_met`.

## Executed

Command: `python3 tools/measure_zlib_minigzip_attempt3.py /tmp/zlib-minigzip-attempt3 /tmp/zlib-minigzip-attempt3.json`

The JSON copy is `docs/evidence/zlib_minigzip_attempt3.json`.

Host: Linux 6.12.113+ x86_64, gcc 13, CPython 3.12.3, Intel Xeon, 4 CPUs. One host. One pair of clean rebuilds. Both Makefiles had `CFLAGS=-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN`, which is zlib's configure default, not an override passed by this attempt. One warmup, then 21 runs. Clock is `time.perf_counter` around `run_sandboxed`.

Correctness passed: round trip of the 4 MiB buffer, candidate gzip of that buffer byte-identical to the baseline gzip, candidate decompress of the baseline gzip equal to the buffer, byte-identical `minigzip` stdout for empty, `abc`, and `hello`, the same gzip bytes and round trip for zeros, periods 3/15/16/17, repeated `abc`, and 8000 fixed-seed bytes, gzip magic `1f8b` with zero mtime on `abc`, and `crc32(abc)` = `352441c2`.

| Median | Baseline seconds | Candidate seconds | Ratio |
| --- | --- | --- | --- |
| Decompress, 21 runs after one warmup | 0.011944525999979305 | 0.01191764000003559 | 0.9977490944434495 |
| Compress, 21 runs after one warmup | 0.024580331000038314 | 0.024523283000007723 | 0.9976791199422619 |

The decompress bar is 0.90. The ratio is above it, so the bar was missed. The compress cap is 1.05. That cap was met. `enhancement_met` is false. `stable_improvement` is false. `attempt_status` is `closed_missed`. `docs/phase0/EVALUATION.md` says one measurement is not a stable improvement.

Floor samples from the same command, same clock, 21 runs after one warmup. They do not decide the bar:

| Sample | Median seconds |
| --- | --- |
| `/bin/true`, empty stdin | 0.011671332999981132 |
| Baseline `minigzip -d` of the gzip of empty | 0.011932761000025494 |

`0.90 * 0.011944525999979305` is 0.010750073399981375. The `/bin/true` median is above that product. `/bin/true` divided by the 4 MiB baseline decompress median is 0.9771281840737216. Empty decompress divided by that baseline is 0.9990150299849628.

Before the candidate existed, the same sandbox on stock minigzip gave an inner duration near one 0.01 second poll sleep: 4 MiB decompress inner median 0.010113042000000405 over 7 runs, empty decompress inner median 0.010106871999994382 over 7 runs, and `/bin/true` inner median 0.010109 seconds when printed to 6 decimals over 9 runs. `run_sandboxed` sleeps 0.01 seconds when the child is still alive at the first poll. Those shorter samples are not the decision medians.

This miss does not replace the closed LTO miss (decompress ratio 0.9956544893408726) or the attempt-2 miss (decompress ratio 1.003810222421081).

## Unverified

- Whether the 16-byte copy reduces inflate CPU time. This attempt did not clock `inflate_fast` by itself. The wall-time ratio above is the decision, and it missed 0.90.
- Whether a clock that does not include process start and the sandbox poll, or a second host, would clear 0.90. That was not measured. A one-host wall-time miss is not evidence that every clock misses, and it is not a pass.
- `stable_improvement` on more than one host.

## Not done

- No second host and no retune of the copy width, the bars, or the payload.
- Held-out, Canterbury, and `docs/a18/routing_comparison.json` were not modified. This attempt did not run those checkers and did not invent a blind-set result. A separate agent owns the post-hoc blind set for the already-frozen stock and attempt-2 candidates.
- No five-policy routing comparison and no savings, price, or model result.
- Nothing was merged.
