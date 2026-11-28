# aklomp/base64 0.5.3 on this branch

This is a real program. It is not `samples/dev/checksum_cli.c` and it is not zlib. A result here is not a dev-sample result and not a zlib result.

The pin commit is `782cd114e8a4a19a801cca5652c187f5f0e33304`, before this build. Source URL `https://github.com/aklomp/base64/archive/refs/tags/v0.5.3.tar.gz`. Tarball SHA-256 `74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42`. The `LICENSE` file in the tarball is the 2-clause BSD license.

## Build

Command: `python3 tools/run_base64_target.py`.

`make -j4` ran through `run_sandboxed` with no `AVX*_CFLAGS`, no `SSE*_CFLAGS`, and no `OPENMP`. It exited 0. `lib/config.h` is:

```
#define HAVE_AVX512 0
#define HAVE_AVX2   0
#define HAVE_NEON32 0
#define HAVE_NEON64 0
#define HAVE_SSSE3  0
#define HAVE_SSE41  0
#define HAVE_SSE42  0
#define HAVE_AVX    0
```

`bin/base64` is ELF64, little-endian, machine 62 (x86-64), type 3 (PIE executable). SHA-256 `1849b1e96c54bc8398ee4a24dfe33765406e43c036339e299926b92d3d368776`. rlimits were applied. The network namespace was not applied (`unshare` returned operation not permitted).

## What the CLI did

The binary was copied into the work directory and invoked as `./base64`. Captured stdout and stderr are data. They were not executed.

| Case | Exit | stdout |
| --- | --- | --- |
| empty stdin | 0 | empty, no newline |
| `abc` | 0 | `YWJj\n` |
| `abc` with `-w 0` | 0 | `YWJj` |
| `hello` | 0 | `aGVsbG8=\n` |
| bytes `00 01 ff` | 0 | `AAH/\n` |
| file `input.bin` holding `abc` | 0 | `YWJj\n`, same stdout hash as stdin `abc` |
| `-d` of the `abc` encoding | 0 | `abc` |
| `-d` of `!!!!` | 1 | empty stdout, stderr `./base64: stdin: decoding error\n` |
| `-h` | 0 | usage text that starts `Usage: ./base64` |
| `-z` | 1 | stderr starts `./base64: unknown option 'z'\n` |

`abc` stdout hashes to `1b0a698c398da5c5865ed1ec4ba12c6c01a08f33a519fe8ef0fdbda20e19019e`. `abc` with `-w 0` hashes to `35d95694d3f160215db293c7899daa5907837838fb4b8119ed713e32446c1266`. The decode of `abc` hashes to `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`, which is the SHA-256 of the three bytes `abc`.

Round trip held for empty, `abc`, `hello`, and `00 01 ff`. The invalid decode did not round-trip. Its exit is 1. The sandbox calls that `execution_result` `failed`. `truncated` is false. The observation is complete. It is not an `accepted_pass`.

## Final set

Six lengths, 4, 7, 57, 58, 76, and 120, from `Random(20261126)`. Default encode (wrap 76). Each one exited 0, repeated the same stdout hash, and decoded back to the input. A second sandboxed encode matched exit, stdout hash, stderr hash, and the newline flag on all six. `final_rerun_match` is true. Label: **non-blind**. See `targets/base64/NON_BLIND.md`.

## Recovered behavior

- With no flags, short inputs are one base64 line plus a newline. Empty input produces no bytes at all.
- `-w 0` encodes `abc` without that newline.
- `-d` reverses the default encoding of the dev inputs above.
- A non-alphabet payload `!!!!` is rejected.
- A named file and stdin produce the same stdout for `abc`.

## Not compared

`--ignore-garbage`, `--no-strip-newlines`, wrap widths other than 76 and 0, and more than one filename were not run. Wall time and peak RSS were not collected. Ghidra is not installed. Static decompilation was not run. `ghidra.executed` is false and `ghidra.accepted_pass` is false. That is not a pass.

The contract is `raee_reverse.cli_contract`. It keeps those names `not_compared`.

## Compatible baseline

`python3 generated/base64-baseline/build_and_check.py --prefix /tmp/b64-base` built plain `make -j4` in the sandbox. `config_has_have_avx2_0` is true. All eight dev checks passed, including `YWJj\n`, `YWJj`, `aGVsbG8=\n`, `AAH/\n`, and the rejected `!!!!`. `dev_ok` is true. `accepted_pass` is false. `opened_seal` is false. The installed binary hash matched the sealed build, `1849b1e96c54bc8398ee4a24dfe33765406e43c036339e299926b92d3d368776`.

`python3 generated/base64-baseline/accept.py --prefix /tmp/b64-base` compared the six final lengths, including the round trip. `pass` is true. `acceptance` is `non-blind`. `accepted_pass` is false. `universal` is false. The uncollected names stayed `not_compared`.
