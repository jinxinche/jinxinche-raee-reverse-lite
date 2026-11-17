# Frozen minigzip attempt 2

Written before the attempt-2 candidate was built or measured. This file is the goal. It is not a result. It does not change `docs/phase4/GOAL.md` or `docs/evidence/zlib_enhancement.json`.

The closed goal stays missed. Its candidate was zlib 1.4 with `CFLAGS="-O3 -flto"` and `LDFLAGS="-flto"`. The recorded decompress median ratio is 0.9956544893408726 against a required 0.90. The recorded compress median ratio is 1.0022963782068877 against a cap of 1.05. Those numbers are not revised here.

`docs/phase4/GOAL_CRC32.md` is a different metric. Its one-host crc32 ratio is not a substitute for this minigzip wall-time goal. This goal does not replace the target with xxHash, lz4, or another program.

## Target

zlib 1.4, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`. The program under the clock is `minigzip`.

## Primary metric

Median wall time to decompress one 4 MiB buffer, lower better.

The buffer is `bytes(i % 251 for i in range(4 * 1024 * 1024))`. It is the same buffer as the closed goal. It is not a final-acceptance input.

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

Both trees use zlib's default `./configure && make`. No `CFLAGS` override. No `LDFLAGS` override. `CFLAGS="-O3 -flto"` is not this candidate. The closed goal already missed with those flags.

The only extra compiler flags are `-msse4.2 -mpclmul` on the translation unit `crc32_pclmul.c`. They are not applied to the rest of the library. Configure runs before the source edits, because configure writes `Makefile`. Make runs after the edits. That order is part of this goal. It is not changed after a measurement.

## Candidate edits

The candidate is a source change, not a flag change:

- In `test/minigzip.c`, `BUFLEN` changes from 16384 to 262144.
- In the stdin/stdout path of `main`, `setvbuf` fully buffers stdin and stdout at 262144 bytes.
- `crc32.c` gains the same early return hook already used by `tools/measure_zlib_crc32.py`, calling `crc32_z_pclmul_try` from `targets/zlib/candidate/crc32_pclmul.c`.

One thread. The candidate must not create threads.

## Measurement

- One warmup, then 21 measured runs, for decompress and for compress separately.
- Each run is one sandboxed invocation. The clock is `time.perf_counter` around that invocation, so process start is included. The sandbox is `raee_reverse.sandbox.run_sandboxed`. The same function times the baseline and the candidate.
- Median of the 21 runs. No other summary replaces the median.
- Same machine, one pair of binaries. This is one sample. `stable_improvement` is false for a single-host, single-sample result even if the ratio is at or under 0.90.
- The machine-readable copy is `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.json`.
- Command: `python3 tools/measure_zlib_minigzip_attempt2.py /tmp/zlib-minigzip-attempt2 /tmp/zlib-minigzip-attempt2.json`
- The script refuses a decompress bar other than 0.90, a compress cap other than 1.05, a `BUFLEN` other than 262144, or a recipe that adds `-O3` or `-flto`.

## Failure rule

If the candidate misses the 10% decompress bar, exceeds the 5% compress cap, or fails correctness, this attempt is closed as missed. The numbers stay. The closed goal is not reopened and is not relabeled as passed.
