# Frozen crc32 goal

Written before the candidate in `targets/zlib/candidate/crc32_pclmul.c` was measured. This file does not change `docs/phase4/GOAL.md`. That goal stays closed and missed. Its result stays in `docs/evidence/zlib_enhancement.json` (decompress median ratio about 0.99565 against a required 0.90, compress about 1.00230 against a cap of 1.05, candidate `CFLAGS="-O3 -flto"`).

## Why this is a different goal

The closed measurement clocked a sandboxed `minigzip` process around one 4 MiB buffer. Process start was large next to the inflate time, and the extra LTO flags did not move the median by 10%. This goal clocks `crc32()` inside one process. The buffer, the clock, and the candidate are not the closed ones.

## Target

zlib 1.4, tarball SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`. The isolatable function is `crc32`. `minigzip` stays a compatibility check. Its wall time is not this metric. The target is not replaced by xxHash or lz4.

## Metric

Median wall time of one `crc32()` call on a 16 MiB buffer, lower better.

The buffer is `bytes((i * 17 + 3) & 0xff for i in range(16 * 1024 * 1024))`. It is not a final-acceptance input and it is not the closed goal's 4 MiB buffer.

## Acceptance

- Meaningful improvement: candidate median ≤ 90% of the baseline median.
- Correctness first: the candidate CRC equals the baseline CRC on that buffer, `crc32` of the ASCII bytes `123456789` is `cbf43926`, and `minigzip` stdout for empty, `abc`, and `hello` is byte-identical to the baseline `minigzip` built from the same tarball with the same configure flags.
- If correctness fails, the candidate fails even if the median is lower.
- One thread. The candidate must not create threads. A result that spends extra cores is not eligible for this goal.
- The candidate is the PCLMULQDQ path in `targets/zlib/candidate/crc32_pclmul.c`, built with zlib's default `./configure && make` plus that object. It is not `CFLAGS="-O3 -flto"`.

## Measurement

- One warmup, then 21 measured calls. The median is the 11th sample after sorting. No other summary replaces it.
- The clock is `CLOCK_MONOTONIC` around `crc32()` only. Process start is outside the clock.
- Baseline and candidate are built from the same tarball. The only intended difference is the PCLMULQDQ path for buffers of at least 64 bytes. Shorter inputs stay on the stock function.
- One machine, one pair of binaries. This is one sample, not a claim of a stable improvement.
- Command: `python3 tools/measure_zlib_crc32.py /tmp/zlib-crc32-work /tmp/zlib-crc32-result.json`
- The script refuses a bar other than 0.90. The machine-readable copy is `docs/phase4/GOAL_CRC32.json`.

## Failure rule

If the candidate misses the 10% bar or fails correctness, the delivery for this goal is: not met. The numbers stay. The closed goal is not reopened and is not relabeled as passed.
