# Frozen minigzip attempt 4

Written before the attempt-4 candidate was built or measured. This file is the goal. It is not a result. It does not change `docs/phase4/GOAL.md`, `docs/evidence/zlib_enhancement.json`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.json`, `docs/evidence/zlib_minigzip_attempt2.json`, `docs/phase4/ATTEMPT2_RESULT.md`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.md`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.json`, `docs/evidence/zlib_minigzip_attempt3.json`, or `docs/phase4/ATTEMPT3_RESULT.md`.

Changing the metric does not turn any earlier miss into a pass. The closed LTO goal stays missed. Attempt 2 stays missed. Attempt 3 stays missed. Their recorded ratios stay the recorded ratios. A later pass or miss on the clock below is not a new label for those three wall-time results.

The closed LTO goal's candidate was zlib 1.4 with `CFLAGS="-O3 -flto"` and `LDFLAGS="-flto"`. The recorded decompress median ratio is 0.9956544893408726 against a required 0.90. The recorded compress median ratio is 1.0022963782068877 against a cap of 1.05.

Attempt 2's candidate was `BUFLEN` 262144, `setvbuf` of 262144 on the stdin/stdout path, and the existing PCLMULQDQ `crc32` hook. The recorded decompress median ratio is 1.003810222421081 against a required 0.90. The recorded compress median ratio is 1.0277633298808058 against a cap of 1.05.

Attempt 3's candidate was a 16-byte SSE2 copy on the direct-from-output match in `inflate_fast`. The recorded decompress median ratio is 0.9977490944434495 against a required 0.90. The recorded compress median ratio is 0.9976791199422619 against a cap of 1.05. Sandboxed `/bin/true` on that run had median 0.011671332999981132 seconds. The 4 MiB baseline decompress median was 0.011944525999979305 seconds. `/bin/true` divided by that baseline is 0.9771281840737216. The 0.90 bar on that wall clock is 0.010750073399981375 seconds, and `/bin/true` is slower than that product. Process start on the 4 MiB sandboxed wall clock is large enough that the 0.90 bar cannot be met.

`docs/phase4/GOAL_CRC32.md` is a different metric. Its one-host crc32 ratio is not a substitute for this goal, and it is not a substitute for the wall-time goals. This goal does not replace the target with xxHash, lz4, or another program.

## Target

zlib 1.4, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`. The calls under the clock are `inflate` and `deflate` in one process, linked to the `libz.a` that the tree just built. `minigzip` stays a correctness check. Its wall time is not this metric.

## Primary metric

Median in-process time to inflate one gzip of one 4 MiB buffer, lower better.

The buffer is `bytes(i % 251 for i in range(4 * 1024 * 1024))`. It is the same buffer as the closed goal and as attempts 2 and 3. It is not a final-acceptance input.

This is not the sandboxed `minigzip` wall-time metric used by `docs/phase4/GOAL.md`, attempt 2, and attempt 3. Process start is outside this clock.

The candidate median must be at most 90% of the baseline median. That bar is not weaker than the closed goal.

## Compress cap

Median in-process time to gzip that same buffer must be at most 105% of the baseline median. That cap is not weaker than the closed goal.

## Clock

The harness is `targets/zlib/harness/inflate_deflate_bench.c`. It is compiled with `gcc -O2 -I. -o inflate_deflate_bench <harness> libz.a` in each built tree and linked only to that tree's `libz.a`. No other compiler or linker flag is added. The same command builds the baseline harness and the candidate harness.

- The clock is `clock_gettime(CLOCK_MONOTONIC)` inside that process.
- One compress sample starts immediately before `deflateInit2` and stops immediately after `deflateEnd` returns. The `deflate` calls use `Z_FINISH` until `Z_STREAM_END`.
- One decompress sample starts immediately before `inflateInit2` and stops immediately after `inflateEnd` returns. The `inflate` calls use `Z_NO_FLUSH` until `Z_STREAM_END`.
- Both use the gzip wrapper: `windowBits` 15+16, level `Z_DEFAULT_COMPRESSION`, `memLevel` 8, `Z_DEFAULT_STRATEGY`.
- The inflate output buffer is the full 4 MiB. The deflate output buffer is at least `deflateBound` of that length. The bytes are not fed through `minigzip`'s 16384-byte loop.
- Filling the buffer, comparing bytes, hashing, and writing the reference gzip are outside the clock.
- One warmup sample, then 21 measured samples, for compress and for decompress separately. The first printed sample of each series is the warmup and is excluded.
- Median of the 21 measured samples. No other summary replaces the median.
- One thread. The harness must not create threads.

## Correctness

Correctness is required. A faster library that fails any of these checks fails the goal:

- In the harness, inflate of the gzip equals the buffer for the baseline and for the candidate, and the candidate gzip bytes equal the baseline gzip bytes.
- `minigzip` round trip of the same buffer equals the buffer for the baseline and for the candidate.
- The candidate gzip of `abc`, from `minigzip`, starts with magic `1f8b` and has a zero mtime.
- `crc32` of the ASCII bytes `abc` is `352441c2` on the candidate library.
- Candidate `minigzip` stdout for empty, `abc`, and `hello` is byte-identical to the baseline `minigzip` built from the same tarball with the same configure invocation.

## Build recipe

Both trees use zlib's default `./configure && make`. No `CFLAGS` override. No `LDFLAGS` override. zlib's configure script may itself put `-O3` into the generated Makefile. That default is not this candidate. `CFLAGS="-O3 -flto"` is not this candidate. The closed goal already missed with those flags.

Configure runs before the source edit, because configure writes `Makefile`. Make runs after the edit. That order is part of this goal. It is not changed after a measurement.

## Candidate edit

The candidate is the attempt-3 source change in `inffast.c` and nothing else. It is not retuned on this buffer. The copy width, the overlap rule, the payload, the bars, and the run count stay the numbers in this file.

- `test/minigzip.c` keeps `#define BUFLEN 16384`. No `setvbuf` call is added.
- `crc32.c` is not edited. `crc32_pclmul.c` is not added. `-msse4.2` and `-mpclmul` are not added.
- In `inflate_fast`, only the direct-from-output match branch changes. The window-copy loops stay the stock byte copies.
- On that direct branch, when the match distance is at least 16, each iteration loads and stores 16 bytes with the x86-64 baseline SSE2 intrinsics `_mm_loadu_si128` and `_mm_storeu_si128`. A 16-byte chunk does not overlap when the distance is at least 16.
- When the distance is below 16, and for any remainder under 16 bytes, the copy is the stock three-byte loop from zlib 1.4 `inffast.c`.
- One thread. The candidate must not create threads.
- The measurement host must be x86-64. On any other machine the attempt closes as missed rather than swapping the copy.

## Measurement

- Same machine, one pair of binaries. This is one sample. `stable_improvement` is false for a single-host, single-sample result even if the ratio is at or under 0.90. `docs/phase0/EVALUATION.md` says one measurement is not a stable improvement.
- The machine-readable copy is `docs/phase4/GOAL_MINIGZIP_ATTEMPT4.json`.
- Command: `python3 tools/measure_zlib_minigzip_attempt4.py /tmp/zlib-minigzip-attempt4 /tmp/zlib-minigzip-attempt4.json`
- The script refuses a decompress bar other than 0.90, a compress cap other than 1.05, a payload other than this 4 MiB buffer, a warmup other than 1, a run count other than 21, a `BUFLEN` other than 16384, a `setvbuf` edit, a crc32 hook, a copy width other than 16, a recipe that adds `-O3` or `-flto`, or a decision clock that is sandboxed `minigzip` wall time.
- Sandboxed `/bin/true` is not a sample for this metric and does not decide `enhancement_met`.

## Failure rule

If the candidate misses the 10% decompress bar, exceeds the 5% compress cap, or fails correctness, this attempt is closed as missed. The numbers stay. The closed goal, attempt 2, and attempt 3 are not reopened and are not relabeled as passed. Meeting this in-process bar would still leave those three wall-time attempts missed.
