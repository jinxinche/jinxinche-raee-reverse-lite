# Frozen minigzip attempt 3

Written before the attempt-3 candidate was built or measured. This file is the goal. It is not a result. It does not change `docs/phase4/GOAL.md`, `docs/evidence/zlib_enhancement.json`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.json`, `docs/evidence/zlib_minigzip_attempt2.json`, or `docs/phase4/ATTEMPT2_RESULT.md`.

The closed LTO goal stays missed. Its candidate was zlib 1.4 with `CFLAGS="-O3 -flto"` and `LDFLAGS="-flto"`. The recorded decompress median ratio is 0.9956544893408726 against a required 0.90. The recorded compress median ratio is 1.0022963782068877 against a cap of 1.05.

Attempt 2 stays missed. Its candidate was `BUFLEN` 262144, `setvbuf` of 262144 on the stdin/stdout path, and the existing PCLMULQDQ `crc32` hook. The recorded decompress median ratio is 1.003810222421081 against a required 0.90. The recorded compress median ratio is 1.0277633298808058 against a cap of 1.05.

`docs/phase4/GOAL_CRC32.md` is a different metric. Its one-host crc32 ratio is not a substitute for this minigzip wall-time goal. This goal does not replace the target with xxHash, lz4, or another program.

## Target

zlib 1.4, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`. The program under the clock is `minigzip`.

## Primary metric

Median wall time to decompress one 4 MiB buffer, lower better.

The buffer is `bytes(i % 251 for i in range(4 * 1024 * 1024))`. It is the same buffer as the closed goal and as attempt 2. It is not a final-acceptance input.

The candidate median must be at most 90% of the baseline median. That bar is not weaker than the closed goal.

## Compress cap

Median wall time to compress that same buffer must be at most 105% of the baseline median. That cap is not weaker than the closed goal.

## Correctness

Correctness is required. A faster binary that fails any of these checks fails the goal:

- `decompress(compress(buffer))` equals the buffer for the baseline and for the candidate.
- The candidate gzip of `abc` starts with magic `1f8b` and has a zero mtime.
- `crc32` of the ASCII bytes `abc` is `352441c2` on the candidate library.
- Candidate `minigzip` stdout for empty, `abc`, and `hello` is byte-identical to the baseline `minigzip` built from the same tarball with the same configure invocation.

## Build recipe

Both trees use zlib's default `./configure && make`. No `CFLAGS` override. No `LDFLAGS` override. zlib's configure script may itself put `-O3` into the generated Makefile. That default is not this candidate. `CFLAGS="-O3 -flto"` is not this candidate. The closed goal already missed with those flags.

Configure runs before the source edit, because configure writes `Makefile`. Make runs after the edit. That order is part of this goal. It is not changed after a measurement.

## Candidate edit

The candidate is one source change in `inffast.c`. It is not a flag change, not a `minigzip` buffer change, and not the crc32 hook.

- `test/minigzip.c` keeps `#define BUFLEN 16384`. No `setvbuf` call is added.
- `crc32.c` is not edited. `crc32_pclmul.c` is not added. `-msse4.2` and `-mpclmul` are not added.
- In `inflate_fast`, only the direct-from-output match branch changes. The window-copy loops stay the stock byte copies.
- On that direct branch, when the match distance is at least 16, each iteration loads and stores 16 bytes with the x86-64 baseline SSE2 intrinsics `_mm_loadu_si128` and `_mm_storeu_si128`. A 16-byte chunk does not overlap when the distance is at least 16.
- When the distance is below 16, and for any remainder under 16 bytes, the copy is the stock three-byte loop from zlib 1.4 `inffast.c`.
- One thread. The candidate must not create threads.
- The measurement host must be x86-64. On any other machine the attempt closes as missed rather than swapping the copy.

## Measurement

- One warmup, then 21 measured runs, for decompress and for compress separately.
- Each run is one sandboxed invocation. The clock is `time.perf_counter` around that invocation, so process start is included. The sandbox is `raee_reverse.sandbox.run_sandboxed`. The same function times the baseline and the candidate.
- Median of the 21 runs. No other summary replaces the median.
- Same machine, one pair of binaries. This is one sample. `stable_improvement` is false for a single-host, single-sample result even if the ratio is at or under 0.90. `docs/phase0/EVALUATION.md` says one measurement is not a stable improvement.
- The machine-readable copy is `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.json`.
- Command: `python3 tools/measure_zlib_minigzip_attempt3.py /tmp/zlib-minigzip-attempt3 /tmp/zlib-minigzip-attempt3.json`
- The script refuses a decompress bar other than 0.90, a compress cap other than 1.05, a `BUFLEN` other than 16384, a `setvbuf` edit, a crc32 hook, a copy width other than 16, or a recipe that adds `-O3` or `-flto`.

The same command also records two floor samples with the same clock, warmup, and run count: sandboxed `/bin/true` with empty stdin, and sandboxed baseline `minigzip -d` of the gzip of empty. Those samples do not decide `enhancement_met`, `decompress_bar_met`, or `compress_cap_met`. They exist so a later reader can see the sandbox floor next to the 4 MiB medians. They are not a replacement metric.

## Failure rule

If the candidate misses the 10% decompress bar, exceeds the 5% compress cap, or fails correctness, this attempt is closed as missed. The numbers stay. The closed goal and attempt 2 are not reopened and are not relabeled as passed.
