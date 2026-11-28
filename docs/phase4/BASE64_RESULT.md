# Base64 encode goal result

The goal in `docs/phase4/GOAL_BASE64.md` was committed in `39ee2082521a5ef6944330e4f3a63cb43e9fbcfb` before this measurement. That file was not edited after the numbers below. The closed zlib goals stay missed. The Lua parse goal stays missed.

## Implemented

- Frozen goal: `docs/phase4/GOAL_BASE64.md` and `docs/phase4/GOAL_BASE64.json`.
- `tools/measure_base64_encode.py` builds two aklomp/base64 0.5.3 trees. The baseline is `make -j4` with no codec flags. The candidate is the README x86 line, run as `bash -c` inside `run_sandboxed` because that runner does not pass `AVX2_CFLAGS` and the other codec variables through its environment. No `AVX512_CFLAGS`, no `OPENMP`, and no source edit. `base64_encode` is called with `flags` 0. The harness `targets/base64/harness/encode_bench.c` is the same for both trees and is compiled with `-O2`.

## Executed

Command: `python3 tools/measure_base64_encode.py /tmp/base64-encode-work /tmp/base64-encode-result.json`

The JSON copy is `docs/evidence/base64_encode_goal.json`.

Host: Linux 6.12.113+ x86_64, gcc 13, CPython 3.12.3, Intel Xeon, 4 CPUs. `/proc/cpuinfo` lists `ssse3`, `sse4_1`, `sse4_2`, `avx`, `avx2`, `avx512vl`, and `avx512vbmi`. AVX512 was not enabled in the candidate. One host. One pair of clean builds. Baseline `config.h` has the codec macros at 0. Candidate `config.h` has AVX2, SSSE3, SSE4.1, SSE4.2, and AVX set to 1, and AVX512 and both NEON macros set to 0. rlimits were applied. The network namespace was not applied.

Correctness passed. Both builds encoded the 8 MiB buffer to the same bytes, SHA-256 `865eba5947f15d5c42b0bf140c3af446d36ff98ccdba616ca1ec602f15e56a73`. The CLI checks matched for both binaries: `abc` to `YWJj\n`, `-w 0` to `YWJj`, `hello` to `aGVsbG8=\n`, empty to empty, `00 01 ff` to `AAH/\n`, `-d` of `YWJj\n` to `abc`, and `-d` of `!!!!` exit 1.

| Median of 21 runs after one warmup | Nanoseconds |
| --- | --- |
| Baseline plain `make -j4` | 4238053 |
| Candidate README x86 codecs | 2764818 |
| Ratio, candidate / baseline | 0.652379288319424 |

The bar is 0.90. The ratio is below it. `enhancement_met` is true for this one sample. `stable_improvement` is false. `attempt_status` is `closed_met`. One sample is not a stable improvement.

Cost, reported and not a second bar: `bin/base64` grew from 35568 bytes to 84720 bytes. `libbase64.o` grew from 23560 bytes to 77736 bytes. The encoded output did not change size.

This result does not change the missed Lua ratio 0.9475223614074023.

## Not done

- No second host.
- No AVX512 candidate and no OpenMP candidate. Those were outside the frozen goal and were not added after this ratio.
- Ghidra was not installed and was not run.
- The sealed final surfaces were not opened by the measurement process.
