# zlib 1.4 on this branch

Built from the vendored tarball `targets/zlib/dist/zlib-1.4.tar.gz`, SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`, tag `v1.4`. `./configure` and `make -j4` ran through `run_sandboxed`. Both exited 0. The network namespace was not applied (`unshare` returned operation not permitted).

Frozen build hashes are in `targets/zlib/PIN.json`. On this machine `minigzip` was `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636`. A different compiler can produce a different binary hash. The sealed gzip bytes are what this build emitted.

## Sets

| Set | Role |
| --- | --- |
| dev | `empty`, `abc`, `hello`. Used for the ledger claim and the Ghidra story. |
| tune | `tune-alpha`, `tune-repeat`, `tune-range`. The level `-9` experiment used `tune-alpha` only. |
| final | Eight lengths from seed `20261114`. Surfaces were sealed, then a second sandboxed run was compared with `compare_surfaces`. All eight matched. Label: **non-blind**. See `targets/zlib/NON_BLIND.md`. |

## Executed observations

- stdin `abc`: exit 0, round trip, crc32 `352441c2`, empty stderr. Ledger `accepted_pass` is true for that scope only (`not_universal`, one source family).
- Ghidra 12.2 / Temurin 25 decompiled `crc32` (it calls `crc32_z`) and `main`. `ghidra.accepted_pass` is false.
- Default versus `-9` on `tune-alpha`: stdout hashes differ. Surviving hypothesis: `level-9-differs`. The contract verdict still lists `compression_level_9` as `not_compared`.
- A truncated `abc` gzip failed to decompress. Deletion shrinking reduced 22 bytes to 4. `global_minimum` is false.

Command: `python3 tools/run_zlib_target.py`.
