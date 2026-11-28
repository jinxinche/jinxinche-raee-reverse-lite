# Licenses of the broad blind corpora

The files in this directory are not covered by the MIT license at the repository root.

## SQLite 3.54.1 Linux x64 command-line tools

`sqlite-tools-linux-x64-3540100.zip` is the official precompiled tools archive for SQLite 3.54.1, published at `https://sqlite.org/2026/sqlite-tools-linux-x64-3540100.zip` and listed on `https://sqlite.org/download.html`.

Hwaci's copyright page, `https://sqlite.org/copyright.html`, says:

> All of the code and documentation in SQLite has been dedicated to the public domain by the authors. All code authors, and representatives of the companies they work for, have signed affidavits dedicating their contributions to the public domain and originals of those signed affidavits are stored in a firesafe at the main offices of Hwaci. All contributors are citizens of countries that allow creative works to be dedicated to the public domain. Anyone is free to copy, modify, publish, use, compile, sell, or distribute the original SQLite code, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

The members `sqlite3`, `sqldiff`, `sqlite3_analyzer`, and `sqlite3_rsync` are the four executables in that zip. They were not rebuilt here. `file` identifies each as an ELF 64-bit x86-64 executable, dynamically linked. The public-domain dedication above is the license relied on for those official binaries. The dynamic linker is not bundled in the zip.

The download page publishes SHA3-256 `555635de98534d87a67ee2e6e1b0d79f494b1b33b223477d3e7a8ea0c66e416f` for this zip. The bytes in this tree match that digest. The chronology page dates the 3.54.1 release 2026-10-16, which is before the frozen candidates.

## NIST Statistical Test Suite 2.1.2 sample data

`sts-2_1_2.zip` is the archive linked as the NIST Statistical Test Suite from `https://csrc.nist.gov/Projects/Random-Bit-Generation/Documentation-and-Software`. The download URL is `https://csrc.nist.gov/CSRC/media/Projects/Random-Bit-Generation/documents/sts-2_1_2.zip`.

That page states:

> This software was developed at the National Institute of Standards and Technology by employees of the Federal Government in the course of their official duties. Pursuant to title 17 Section 105 of the United States Code this software is not subject to copyright protection and is in the public domain. The NIST Statistical Test Suite is an experimental system. NIST assumes no responsibility whatsoever for its use by other parties, and makes no guarantees, expressed or implied, about its quality, reliability, or any other characteristic. We would appreciate acknowledgment if the software is used.

The inputs are the seven files in `sts-2.1.2/sts-2.1.2/data/`. The C source, headers, and templates in the same zip are not inputs. The CSRC page does not publish a digest of the zip. Two downloads of that URL were byte-identical. SHA-256 of those bytes is `0238d2f1d26e120e3cc748ed2d4c674cdc636de37fc4027c76cc2a394fff9157`.

`data.pi`, `data.e`, `data.sqrt2`, and `data.sqrt3` are ASCII `0` and `1` expansions, with spaces and newlines. `BBS.dat`, `data.bad_rng`, and `data.sha1` are binary samples from the same data directory. The suite's generator list includes Blum-Blum-Shub (`bbs`) and SHA-1 (`SHA1`). This note does not add a claim about whether `data.bad_rng` fails a statistical test.

## Silesia files that were not used

The Silesia corpus page, `https://sun.aei.polsl.pl/~sdeor/index.php?page=silesia`, describes `mozilla`, `x-ray`, and `sao` and does not state a license for the corpus or for those files.

- `mozilla` is described as a tar of an installed Mozilla 1.0 directory on Tru64 UNIX, not as an official Mozilla source or binary release. The page does not identify license notices or a source offer for that tar. MPL, GPL, or LGPL terms that may apply to Mozilla's own releases are not a clear license for this packaging.
- `x-ray` is described as a hospital X-ray of a child's hand. The page gives no license. It was not copied.
- `sao` is described as the SAO star catalog, taken from "Astronomical Catalogs and Catalog Formats." The page gives no redistribution license.

Those three files are not in this tree.
