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

## Broad corpora

The section above is the enwik8 record. It is unchanged. This section is a later set. The checker and the input hashes were committed in `3b6e405f70129bf075cc7f654dfbfea74d8ceae5` before stock, attempt 2, or attempt 3 was run on these files. `source_commit` on each JSON file is that seal.

### Corpora

Silesia `mozilla`, `x-ray`, and `sao` are not in this set. The Silesia page states no license for the corpus or for those files. `x-ray` is described there as a hospital image of a child's hand. `mozilla` is described as a tar of an installed tree, not an official Mozilla release with a stated source offer. `sao` is described as a star catalog with no redistribution license on that page. Details: `targets/zlib/blind_broad/LICENSE.md`.

Two published corpora are sealed instead. The repository MIT license does not cover either zip.

- Executable: SQLite 3.54.1 official Linux x64 command-line tools, `sqlite-tools-linux-x64-3540100.zip`. Public domain, as dedicated at `https://sqlite.org/copyright.html`. Published SHA3-256 `555635de98534d87a67ee2e6e1b0d79f494b1b33b223477d3e7a8ea0c66e416f`. Release date 2026-10-16. Members: `sqlite3`, `sqldiff`, `sqlite3_analyzer`, `sqlite3_rsync`. All four are ELF x86-64 executables. None were rebuilt here.
- Random-like: every file in the `data/` directory of NIST STS 2.1.2, `sts-2_1_2.zip`. United States government work, public domain under 17 USC 105, as stated on the CSRC page. The page does not publish a digest. Two downloads of the URL were byte-identical. SHA-256 `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157`. Members: `BBS.dat`, `data.bad_rng`, `data.sha1` (binary) and `data.e`, `data.pi`, `data.sqrt2`, `data.sqrt3` (ASCII `0`/`1` expansions).

`inputs_invented_for_this_candidate` is false. `tuned_on_this_set` is false. Set author `bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d`. Attempt-2 candidate author `bc-641141af-3ffd-5b16-acb9-663777242042`. Attempt-3 candidate author `bc-cfef56ea-f25b-5590-a266-7684b5589b8e`. The enwik8 set author is a different agent.

### This host

One host for the JSON files below: Linux 6.12.113+ x86_64, gcc 13, GNU gzip 1.12, CPython 3.12.3, oracle zlib 1.3. `CFLAGS`, `LDFLAGS`, and `CC` were unset. Stock and attempt 2 were built by `tools/reproduce_frozen_zlib_builds.py`. Attempt 3 was built by `tools/reproduce_frozen_zlib_attempt3.py` from the frozen `./configure && make` recipe, with the patch applied only in a temporary tree. Attempt 3 did build on this x86_64 host.

The reproduced stock `minigzip` and `libz.a` hashes equal `targets/zlib/PIN.json`. The attempt-2 `minigzip` hash equals the hash in the enwik8 attempt-2 record. That is this compiler and the frozen recipe, not a flag change.

The same binaries were also run through the existing enwik8 checker. Stock and attempt 2 again recorded CRC `81838409` and gzip length 36,548,933. The committed enwik8 JSON files were not modified. The enwik8 checker still accepts only `stock` and `attempt2`. Attempt 3 was not given a new enwik8 label.

| Candidate | minigzip SHA-256 | inputs | CRC vs CPython | external gzip | CPython zlib | injected CRC | flipped byte | pass | blind |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| stock zlib 1.4 | `e5990e7d1b34bcbb8d7f9aff732887ba90d63c0e5d3e92f58a0156f5e7cec636` | 11 | match | match | match | fail, as required | rejected | true | true |
| attempt 2 | `6b0fb8208e1ccc4a6729c46592d5aaaf53a86dffe353d2c2543fb1742c64dee8` | 11 | match | match | match | fail, as required | rejected | true | true |
| attempt 3 | `ad20f09247ad065a7b571209a8495cf2fa58f3146666c102e69c174571fef1e3` | 11 | match | match | match | fail, as required | rejected | true | true |

The three reports record the same CRC and the same gzip length on each input. The gzip bytes were not stored and were not compared.

| Input | Kind | Length | CRC | Gzip length |
| --- | --- | --- | --- | --- |
| `sqlite3` | executable | 2037360 | `ff17be7e` | 1056293 |
| `sqldiff` | executable | 1596160 | `a41d4bc7` | 845946 |
| `sqlite3_analyzer` | executable | 3334360 | `1c107e0b` | 1607487 |
| `sqlite3_rsync` | executable | 1559168 | `a788ddf3` | 827578 |
| `BBS.dat` | random-like | 37500000 | `3f3e2732` | 37511458 |
| `data.bad_rng` | random-like | 1572864 | `cf68852f` | 1573362 |
| `data.e` | random-like | 1165666 | `7404fe79` | 210565 |
| `data.pi` | random-like | 1165666 | `b9d96c9c` | 210370 |
| `data.sha1` | random-like | 125000 | `bc71ef68` | 125058 |
| `data.sqrt2` | random-like | 1165667 | `87d25482` | 210201 |
| `data.sqrt3` | random-like | 1165667 | `008c1e73` | 210402 |

Records: `docs/evidence/blind_broad_stock.json`, `docs/evidence/blind_broad_attempt2.json`, and `docs/evidence/blind_broad_attempt3.json`.

### Other hosts

These JSON files are one host. They are not several hosts. `.github/workflows/blind-broad.yml` runs the same checker on `ubuntu-latest` and on `macos-latest`. Those runs are separate hosts. Their results are not in the JSON above. On a non-x86_64 runner, attempt 2 may fail to compile because the frozen patch passes `-msse4.2 -mpclmul`. That failure is not a pass. This x86_64 run did not hit it.

### Unverified

- Whether the three gzip streams are byte-for-byte identical. The recorded lengths match. The bytes were not stored and were not compared.
- Any host other than the Linux host named above.
- Wall time. This run does not measure the closed speed goals.
- The Canterbury files. They remain `blind` false.

### Not finished here

The local checks finished. The Actions runs on Ubuntu and macOS are not recorded in this commit. The closed LTO miss, the attempt-2 wall-time miss, and the attempt-3 wall-time miss stay missed.
