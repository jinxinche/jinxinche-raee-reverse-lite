# Frozen improvement goal

Written before any enhanced candidate. The compatible baseline has already passed the sealed-surface check. This file is the goal. It is not a result.

## Primary metric

Median wall time to decompress one 4 MiB buffer, lower better.

The buffer is `bytes(i % 251 for i in range(4 * 1024 * 1024))`. It is not a final-acceptance input.

## Thresholds

- Meaningful improvement: candidate median ≤ 90% of the compatible-baseline median.
- Allowed degradation: candidate median compress time of the same buffer ≤ 105% of the baseline median.
- Correctness first: decompress(compress(buffer)) equals the buffer, and the dev checks (round trip, gzip magic with zero mtime, crc32(`abc`) = `352441c2`) still hold.
- If correctness fails, the candidate fails even if it is faster.

## Measurement

- One warmup, then 21 measured runs, for decompress and for compress separately.
- Each run is one sandboxed invocation. The clock is `time.perf_counter` around that invocation, so process start is included.
- Median of the 21 runs. No other summary replaces the median.
- Same machine, one binary at a time. This is one sample, not a claim of a stable improvement.
- The baseline binary is the install produced by `generated/zlib-baseline/build_and_check.py`.
- The only candidate that may be built against this goal is zlib 1.4 configured with `CFLAGS="-O3 -flto"` and `LDFLAGS="-flto"`.

## Failure rule

If that candidate misses the 10% decompress bar, exceeds the 5% compress cap, or fails correctness, the delivery is: compatible baseline done, enhancement not met. The numbers stay. The metric is not replaced by peak RSS or by any other menu item.
