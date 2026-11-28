# Frozen base64 encode goal

Written before any enhanced base64 candidate. This file does not change `docs/phase4/GOAL.md` or the other zlib goals. Those stay as they are. It does not change `docs/phase4/GOAL_LUA.md`.

The compatible baseline is plain `make -j4`. Its `lib/config.h` has every `HAVE_*` codec macro set to 0. This file is the goal. It is not a result.

## Why this clock

Encoding a few bytes is close to the cost of starting a sandboxed process. This goal clocks `base64_encode` inside one process.

## Target

aklomp/base64 `v0.5.3`, tarball SHA-256 `74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42`. The timed call is `base64_encode` with `flags` 0. The CLI remains a compatibility check. Its wall time is not this metric. The target is not replaced by another encoder.

## Metric

Median time of one `base64_encode` call, lower better.

The buffer is `bytes(i % 251 for i in range(8 * 1024 * 1024))`. It is not a sealed final input.

## Acceptance

- Meaningful improvement: candidate median ≤ 90% of the baseline median.
- Correctness first: the candidate's encoded bytes are identical to the baseline's encoded bytes for that buffer. The CLI still encodes stdin `abc` to `YWJj\n`, encodes `abc` with `-w 0` to `YWJj`, encodes `hello` to `aGVsbG8=\n`, encodes empty stdin to empty, encodes bytes `00 01 ff` to `AAH/\n`, decodes `YWJj\n` to `abc`, and rejects `-d` of `!!!!` with exit 1.
- If correctness fails, the candidate fails even if the median is lower.
- One thread. `OPENMP` is not set. The candidate must not create threads.
- `flags` passed to `base64_encode` stays 0. A forced-codec flag is not this goal.
- The only candidate is the x86 codec set quoted by the tarball README, and nothing else: `AVX2_CFLAGS=-mavx2 SSSE3_CFLAGS=-mssse3 SSE41_CFLAGS=-msse4.1 SSE42_CFLAGS=-msse4.2 AVX_CFLAGS=-mavx make -j4`. No `AVX512_CFLAGS`. No source edit. The baseline is `make -j4` with those variables unset.

## Cost

Identical encoded bytes mean the output size does not change. Binary size is reported and is not a second bar. One sample is not a stable improvement.

## Measurement

- One warmup, then 21 measured calls. The median is the 11th sample after sorting. No other summary replaces it.
- The clock is `CLOCK_MONOTONIC` around `base64_encode` only. Process start is outside the clock.
- The harness is the same source for both trees. It is not the candidate.
- One machine, one pair of builds. This is one sample.
- Command: `python3 tools/measure_base64_encode.py /tmp/base64-encode-work /tmp/base64-encode-result.json`
- The script refuses a bar other than 0.90. The machine-readable copy is `docs/phase4/GOAL_BASE64.json`.

## Failure rule

If the candidate misses the 10% bar or fails correctness, the delivery for this goal is: not met. The numbers stay. The bar is not replaced. AVX512 is not added after the measurement. The Lua goal is not used as a replacement.
