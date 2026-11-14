# Targets

The dev sample and the real target are different. The dev sample was executed. The real target was not built, not run, and not optimised.

## Frozen real target

**zlib 1.4, `minigzip`, with `crc32` as the isolatable function.**

| Item | Frozen value |
| --- | --- |
| Repository | `https://github.com/madler/zlib` |
| Tag | `v1.4` (published 2026-11-05, GitHub release) |
| License | zlib license, read from `zlib.h` at that tag (`version 1.4, November 4th, 2026`, copyright 1995–2026 Jean-loup Gailly and Mark Adler). GitHub's SPDX field for the repo is `NOASSERTION`; the header text is the license that was read. |
| Build | `./configure && make`, documented in the tag's `README`. Not run in this phase. |
| I/O | `test/minigzip.c` compresses and decompresses stdin/stdout. `crc32` is a named library function. |
| Why this one | Single permissive license, small C library, deterministic bytes in and out, one function that can be named without guessing. |

Closed alternates, recorded so they are not swapped in later:

| Candidate | Why it is not the target |
| --- | --- |
| Cyan4973/xxHash `v0.8.4` (2026-09-19) | Library files are BSD-2-Clause. The `xxhsum` CLI is GPLv2 (`cli/COPYING`, stated in the tag README). The license split makes the CLI a worse v1 target than zlib. |
| lz4/lz4 `v1.11.1` (2026-11-10) | `lib/` is BSD-2-Clause. The CLI and tests are GPL-2.0-or-later (repository `LICENSE` at that tag). Same reason. |

No fourth candidate may be added. The choice is zlib 1.4, not "whichever of these is easier at optimisation time".

### Acceptance rule for zlib, not yet executed

Before any enhanced candidate exists, pick exactly one primary metric from this closed menu and freeze the threshold in the same change that records the choice:

1. Median wall time of decompress on a sealed input set, at least 10% lower than the frozen zlib 1.4 binary, with compress-time regression at most 5%, after correctness passes.
2. Peak RSS of decompress, at least 15% lower, after correctness passes.

Correctness is gzip-compatible round trip (RFC 1952) and matching `crc32` on the sealed inputs. The sealed input bytes, their hashes, and the baseline binary hash do not exist yet. They must be written down before an enhanced candidate is generated. They were not created in this run, so there is no final-acceptance result.

Must-keep versus intentional change versus unknown behavior lists are not written yet, because the target has not been built.

## Dev sample (executed, synthetic)

`samples/dev/checksum_cli.c` is ours. It is not a user project and it is not zlib.

- `printf abc | ./checksum_cli` prints `count=3 sum=294` and exits 0. Re-checked by `tests/test_phase2_evidence.py` on Linux x86-64 when `gcc` exists.
- `--fail` prints the same line and exits 3.
- Headless Ghidra 12.2 decompiled `checksum` and `main`. The decompiler printed the modulus as `0xfff1` (decimal 65521). That is a static observation. It is not the runtime claim.
- The ledger accepted the stdin-`abc` claim for this host only (`not_universal: true`, one independent support). Evidence: `docs/evidence/phase2_dev_sample.json`.

## Isolation

Target processes run with `raee_reverse.sandbox`:

- a fresh directory as `cwd` and `HOME`
- environment reduced to a short allow-list, with names containing tokens, keys, or secrets removed
- `prlimit` CPU, file-size, nofile, and nproc limits when `prlimit` exists
- stdout/stderr capped; truncation sets `execution_result` to `uncertain`
- timeout and resource-limit stops are `uncertain`, not passes
- captured bytes are stored, not executed

On this VM the network namespace probe failed, so the dev-sample runs record `network_namespace: false` and a limitation. That is not "network isolated".
