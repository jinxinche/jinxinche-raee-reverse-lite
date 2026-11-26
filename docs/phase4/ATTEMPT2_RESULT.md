# Minigzip attempt 2 result

The goal in `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md` was committed before this measurement. That file was not edited after the numbers below. The closed goal in `docs/phase4/GOAL.md` and `docs/evidence/zlib_enhancement.json` stays missed.

## Command

`python3 tools/measure_zlib_minigzip_attempt2.py /tmp/zlib-minigzip-attempt2 /tmp/zlib-minigzip-attempt2.json`

The JSON copy is `docs/evidence/zlib_minigzip_attempt2.json`.

## Environment

Linux 6.12.113+ x86_64, gcc 13, CPython 3.12.3, Intel Xeon, 4 CPUs. One host. One pair of clean rebuilds. `./configure && make` for both trees. No `CFLAGS` or `LDFLAGS` override. The candidate adds `BUFLEN` 262144, `setvbuf` of 262144 on the stdin/stdout path, and the existing PCLMULQDQ `crc32` hook with `-msse4.2 -mpclmul` only on `crc32_pclmul.c`.

## Result

Correctness passed: round trip of the 4 MiB buffer, byte-identical `minigzip` stdout for empty, `abc`, and `hello`, gzip magic `1f8b` with zero mtime on `abc`, and `crc32(abc)` = `352441c2`.

| Median | Baseline seconds | Candidate seconds | Ratio |
| --- | --- | --- | --- |
| Decompress, 21 runs after one warmup | 0.011994312999831891 | 0.012040014000149313 | 1.003810222421081 |
| Compress, 21 runs after one warmup | 0.024667178000072454 | 0.02535202100011702 | 1.0277633298808058 |

The decompress bar is 0.90. The ratio is above it, so the bar was missed. The compress cap is 1.05. That cap was met. `enhancement_met` is false. `stable_improvement` is false. `attempt_status` is `closed_missed`.

This miss does not replace the closed LTO miss (decompress ratio 0.9956544893408726).
