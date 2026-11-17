# Blind enwik8 acceptance

The checker and the input hashes were committed in `f3a79dce276c4919936ef06be8eba56ad91f7c5c` before either frozen binary was run. This file records the runs that happened after that commit. It does not replace the non-blind Canterbury result, and it does not reopen a closed minigzip goal.

## Implemented

- Corpus: enwik8, the published 100,000,000-byte Wikipedia prefix in `targets/zlib/blind_acceptance/enwik8.zip`.
- Origin: `http://mattmahoney.net/dc/enwik8.zip`, documented at `http://mattmahoney.net/dc/textdata.html`.
- License: GNU Free Documentation License 1.2, no invariant sections, front-cover texts, or back-cover texts. The repository MIT license does not cover the zip. See `targets/zlib/blind_acceptance/LICENSE.md`.
- Published identity: MD5 `a1fa5ffddb56f4953e226637dabbb36a`, SHA-1 `57b8363b814821dc9d47aa4d41f58733519076b2`, length 100,000,000. Member SHA-256 `2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8`. Zip SHA-256 `547994d9980ebed1288380d652999f38a14fe291a6247c157c3d33d4932534bc`.
- Oracles: GNU gzip and CPython zlib. Expected gzip bytes are not stored.
- Negative controls: injected CRC `00000000`, and one flipped byte in the gzip stream.
- Builds: `tools/reproduce_frozen_zlib_builds.py` calls the already recorded `./configure && make` recipe. The attempt-2 patch is applied only in a temporary tree.

## Executed

Host: Linux 6.12.113+ x86_64, gcc 13, GNU gzip 1.12, CPython 3.12.3, oracle zlib 1.3. The candidates are zlib 1.4. `source_commit` on both runs is the seal commit above. `CFLAGS`, `LDFLAGS`, and `CC` were unset.

| Candidate | minigzip SHA-256 | enwik8 CRC | gzip bytes | external gzip | CPython zlib | injected CRC | flipped byte | pass | blind |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stock zlib 1.4 | `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636` | `81838409` | 36548933 | match | match | fail, as required | rejected | true | true |
| attempt 2 | `6b0fb8208e1ccc4a6729c46592d5aaaf53a86dffe353d2c2543fb1742c64dee8` | `81838409` | 36548933 | match | match | fail, as required | rejected | true | true |

The reproduced stock `minigzip` and `libz.a` hashes equal the hashes already recorded in `targets/zlib/PIN.json`. That is the same recipe and this compiler, not a flag change. Sample size is 1.

`inputs_invented_for_this_candidate` is false. `tuned_on_this_set` is false. Set author `bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4`. Candidate author `bc-641141af-3ffd-5b16-acb9-663777242042`.

Records: `docs/evidence/blind_acceptance_stock.json` and `docs/evidence/blind_acceptance_attempt2.json`.

## Unverified

- Any input other than enwik8. One file is not a claim about the Canterbury files or about every input.
- Any host other than this one.
- Whether the two gzip streams are byte-for-byte identical. Both lengths were 36,548,933 and both round-tripped. The bytes were not stored and were not compared.
- Wall time. This run does not measure the closed speed goals.
- A five-policy routing comparison. Those records were not changed, and no price or savings figure was produced.

## Not finished here

Nothing in this check was left unrun. The Canterbury set remains `blind` false. `targets/zlib/NON_BLIND.md` is unchanged. The closed LTO miss and the closed attempt-2 wall-time miss stay missed.
