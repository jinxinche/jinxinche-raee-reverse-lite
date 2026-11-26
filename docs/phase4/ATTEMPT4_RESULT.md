# Minigzip attempt 4 result

The goal in `docs/phase4/GOAL_MINIGZIP_ATTEMPT4.md` was committed before this measurement. That file was not edited after the numbers below. Changing the metric does not turn any earlier miss into a pass. The closed goal in `docs/phase4/GOAL.md` and `docs/evidence/zlib_enhancement.json` stays missed. Attempt 2 in `docs/phase4/ATTEMPT2_RESULT.md` stays missed. Attempt 3 in `docs/phase4/ATTEMPT3_RESULT.md` stays missed.

## Implemented

- Frozen goal: `docs/phase4/GOAL_MINIGZIP_ATTEMPT4.md` and `docs/phase4/GOAL_MINIGZIP_ATTEMPT4.json`, commit `283754e7660083ec8c1721f1760b77c99413da3f`, before the candidate build.
- The metric is the median in-process time of one gzip inflate of the same 4 MiB buffer, lower better. The clock is `CLOCK_MONOTONIC` around `inflateInit2`, `inflate` with `Z_NO_FLUSH` until `Z_STREAM_END`, and `inflateEnd`. The compress cap uses the same boundaries around `deflateInit2`, `deflate` with `Z_FINISH`, and `deflateEnd`. Process start is outside the clock. This is not the sandboxed `minigzip` wall-time metric.
- `tools/measure_zlib_minigzip_attempt4.py` builds two zlib 1.4 trees with `./configure && make` and no `CFLAGS` or `LDFLAGS` override. The candidate edits only `inffast.c`, after configure and before make. The edit is the attempt-3 direct-match copy: distance at least 16 is copied 16 bytes at a time with `_mm_loadu_si128` and `_mm_storeu_si128`. Shorter distances and the remainder use zlib 1.4's three-byte loop. Window copies, `BUFLEN` 16384, `crc32.c`, and `minigzip.c` stay stock. One thread. The copy width was not changed after this measurement.

## Executed

Command: `python3 tools/measure_zlib_minigzip_attempt4.py /tmp/zlib-minigzip-attempt4 /tmp/zlib-minigzip-attempt4.json`

The JSON copy is `docs/evidence/zlib_minigzip_attempt4.json`.

Host: Linux 6.12.113+ x86_64, gcc 13, CPython 3.12.3, Intel Xeon, 4 CPUs. `uname` was `Linux 6.12.113+ #1 SMP PREEMPT_DYNAMIC Wed Nov 25 22:23:42 UTC 2026 x86_64`. One host. One pair of clean rebuilds. Both Makefiles had `CFLAGS=-O3 -fPIC -D_LARGEFILE64_SOURCE=1 -DHAVE_HIDDEN`, which is zlib's configure default, not an override passed by this attempt. One warmup, then 21 runs. The harness is `targets/zlib/harness/inflate_deflate_bench.c`, compiled with `gcc -O2 -I. -o inflate_deflate_bench inflate_deflate_bench.c libz.a` and linked to that tree's `libz.a`.

Correctness passed: harness inflate of the gzip equals the 4 MiB buffer for both trees, harness gzip bytes are identical, `minigzip` round trip of the buffer equals the buffer, candidate `minigzip` of the baseline gzip equals the buffer, byte-identical `minigzip` stdout for empty, `abc`, and `hello`, the same gzip bytes and round trip for zeros, periods 3/15/16/17, repeated `abc`, and 8000 fixed-seed bytes, gzip magic `1f8b` with zero mtime on `abc`, and `crc32(abc)` = `352441c2`.

| Median | Baseline seconds | Candidate seconds | Ratio |
| --- | --- | --- | --- |
| In-process decompress, 21 runs after one warmup | 0.000911048 | 0.001033826 | 1.1347656764517347 |
| In-process compress, 21 runs after one warmup | 0.010163022 | 0.010221828 | 1.005786271052055 |

The decompress bar is 0.90. The ratio is above it, so the bar was missed. The candidate median is higher than the baseline median on this sample. The compress cap is 1.05. That cap was met. `enhancement_met` is false. `stable_improvement` is false. `attempt_status` is `closed_missed`. `docs/phase0/EVALUATION.md` says one measurement is not a stable improvement.

Sandboxed `/bin/true` is not a sample for this metric and did not decide `enhancement_met`.

This miss does not replace the closed LTO miss (decompress ratio 0.9956544893408726), the attempt-2 miss (decompress ratio 1.003810222421081), or the attempt-3 miss (decompress ratio 0.9977490944434495). Those three stay missed.

## Unverified

- Whether another host would produce the same in-process ratio.
- `stable_improvement` on more than one host.
- A different copy width. This attempt did not try one. The frozen width stays 16.

## Not done

- No second host and no retune of the copy width, the bars, the payload, or the clock.
- Held-out, Canterbury, and `docs/a18/routing_comparison.json` were not modified. This attempt did not run those checkers and did not invent a blind-set result.
- No five-policy routing comparison and no savings, price, or model result.
- Nothing was merged.
