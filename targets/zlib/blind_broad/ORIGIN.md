# Broad blind inputs

Two published corpora. Expected gzip bytes are not stored. The repository MIT license does not cover either zip. The license text is in `LICENSE.md`.

## Executable corpus

SQLite 3.54.1 command-line tools for Linux x64.

- Zip: `https://sqlite.org/2026/sqlite-tools-linux-x64-3540100.zip`
- Listed on: `https://sqlite.org/download.html`
- Product row: `PRODUCT,3.54.1,2026/sqlite-tools-linux-x64-3540100.zip,4324601,555635de98534d87a67ee2e6e1b0d79f494b1b33b223477d3e7a8ea0c66e416f`
- Release date on `https://sqlite.org/chronology.html`: 2026-10-16
- Zip length: 4,324,601 bytes
- Published SHA3-256: `555635de98534d87a67ee2e6e1b0d79f494b1b33b223477d3e7a8ea0c66e416f`
- Zip SHA-256: `a21062b333c7d66d7d8c42054c0fab1c1899729185289ad14bd4f25f9f576d14`

The published SHA3-256 matched the downloaded zip before this manifest was sealed. Member hashes are of the bytes inside that zip. Every executable member is an input. There is no other member.

| Member | Length | SHA-256 |
| --- | --- | --- |
| `sqlite3` | 2037360 | `c9daa875c28379f0d61a833d47928c6e43b352d98638cd824ec405f23c99d870` |
| `sqldiff` | 1596160 | `62b3014603bbf427eeaba2767f32ffc4c88ea261d5960dfff6683c26bf50d56b` |
| `sqlite3_analyzer` | 3334360 | `e2ffb7e4471e17dfa2f0b1829350b30a36a46cdafb9ecb870891781df6b1fbd3` |
| `sqlite3_rsync` | 1559168 | `5203304e7ce33b872eea14ad3888d557d86f6860cf3643a6d03fa987e8d980fa` |

## Random-like corpus

The `data/` directory of NIST STS 2.1.2.

- Zip: `https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip`
- Page: `https://csrc.nist.gov/Projects/Random-Bit-Generation/Documentation-and-Software`
- Zip length: 43,915,127 bytes
- Zip SHA-256: `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157`
- Publisher digest: none on that page. Two downloads were byte-identical.

Every file under `sts-2.1.2/sts-2.1.2/data/` is an input. The C sources and templates in the zip are not inputs.

| Member | Length | SHA-256 | Bytes |
| --- | --- | --- | --- |
| `BBS.dat` | 37500000 | `8b808e72e5b9e50893f5714a948d3a87c3a014fc8b8e0be3f64e3da07ad8ed6c` | binary |
| `data.bad_rng` | 1572864 | `4a596370fcb4263c99f4fddcbd5c766c4abf5cfaab645bef1d3611d86f1c3e60` | binary |
| `data.e` | 1165666 | `b4b49e2987dacdbd5fe75a8ad767f4139e7be7d8f0ff9ddfb23e6081a5feed2d` | ASCII `0`/`1` |
| `data.pi` | 1165666 | `8efe68d864d53540de7a7a3c54743cb0f47ffcd28b2950992519068474498823` | ASCII `0`/`1` |
| `data.sha1` | 125000 | `dcc306053a40b5f0c94508425660620b932a1803aadc7207a1b669eb4e3bd6a3` | binary |
| `data.sqrt2` | 1165667 | `66e6fd40d1e7b14613801cdb8af67ee6b4fde988f348e0a09e7be84257ee3ed3` | ASCII `0`/`1` |
| `data.sqrt3` | 1165667 | `6b1fc9f59f701b4c75d013cb3854bcc545f971da057d8140a8d7600bd34850e0` | ASCII `0`/`1` |

## Not these inputs

This is not the Canterbury tarball `cantrbry.tar.gz` (`f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb`). It is not `enwik8.zip` (`547994d9980ebed1288380d652999f38a14fe291a6247c157c3d33d4932534bc`). It does not contain the Silesia files `mozilla`, `x-ray`, or `sao`.

`MANIFEST.json` is the seal record. `SEAL.sha256` is the SHA-256 of that manifest after CRLF is turned into LF.
