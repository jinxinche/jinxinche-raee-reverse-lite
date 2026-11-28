# Additional real targets

Frozen before either program was built or run. This file does not change `docs/phase0/TARGETS.md`. zlib 1.4 stays the first real target. These two are later targets. They are not a replacement. A miss on one is not a reason to delete it and pin another.

The dev sample in `samples/dev/checksum_cli.c` is synthetic. It is not one of these targets. A result on that sample is not a result on Lua or on base64.

## Chosen

| Name | Why this one |
| --- | --- |
| Lua 5.4.9, `luac -p` | MIT, read from `doc/readme.html` in the official tarball (copyright 1994–2026 Lua.org, PUC-Rio). Released 10 Aug 2026. The same file says `make` builds `luac`. `luac -p` checks the syntax of a file. That is a language front end, not a compressor. |
| aklomp/base64 `v0.5.3` | BSD-2-Clause, read from `LICENSE` in the tag tarball. GitHub published the tag on 2026-11-04. The README says `make` builds `bin/base64` and that this program works similarly to the `base64` utility. That is an encoder, not a compressor. |

The README and `LICENSE` of the base64 tarball, and `doc/readme.html` of the Lua tarball, were read to check the license and that each tree builds a CLI. Neither program was compiled. Neither program was executed.

Pins:

| Target | URL | SHA-256 |
| --- | --- | --- |
| `targets/lua/dist/lua-5.4.9.tar.gz` | `https://www.lua.org/ftp/lua-5.4.9.tar.gz` | `2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6` |
| `targets/base64/dist/base64-0.5.3.tar.gz` | `https://github.com/aklomp/base64/archive/refs/tags/v0.5.3.tar.gz` | `74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42` |

No binary hash is recorded yet. Neither tree has been built.

## Not chosen

Recorded so they are not swapped in after a measurement:

| Candidate | Why it is not a target of this pass |
| --- | --- |
| jq 1.x | MIT, and it was on the candidate list. It is a programming language. A few filters would not be the program. It is not pinned. |
| Lua 5.5.1 | Also MIT. Official tarball `https://www.lua.org/ftp/lua-5.5.1.tar.gz`, SHA-256 `1c4b4068d67061f2a2231ad2b5422e77acea1487ea9890f6320af614f4373dce`, released 24 Jul 2026. It was not built and not run. The pin is 5.4.9. |
| GNU coreutils `base64`, xxHash `xxhsum`, lz4 CLI | The CLI license is GPL. That is outside the license rule. |

## Not done

Observation, recovered behavior, an executable contract, a compatible build, an enhancement goal, a candidate, and a measurement. None of those exist yet. Absence is not a pass.
