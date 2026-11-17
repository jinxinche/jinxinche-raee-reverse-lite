# zlib 1.4 crc32 candidate

This is the candidate for `docs/phase4/GOAL_CRC32.md`. It is not the closed LTO goal in `docs/phase4/GOAL.md`, and that goal remains missed.

The source added to a zlib 1.4 tree is `targets/zlib/candidate/crc32_pclmul.c`. `tools/measure_zlib_crc32.py` extracts the pinned tarball, inserts the call at the start of `crc32_z`, and builds with `./configure && make`. It does not pass `CFLAGS="-O3 -flto"`.

The speed clock is around `crc32()` on one 16 MiB buffer inside `targets/zlib/harness/crc32_bench.c`. `minigzip` stdout for empty, `abc`, and `hello` must match the baseline build. The result of the measurement is `docs/evidence/zlib_crc32_goal.json` when that file exists. If the ratio is above 0.90, the goal is not met.
