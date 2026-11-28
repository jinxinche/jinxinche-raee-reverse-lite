# Broad blind acceptance isolation

Candidates were already frozen at `d538cb64feb965d3d849759ec0ffdb4086dff1af` before this manifest. No candidate is run in the commit that adds this manifest. A later commit may record runs. That later commit is not this seal.

## Authors

- Set and checker author: `bc-2508fd5e-68a5-584e-8806-b3b3fa0c959d`.
- Attempt 2 and the stock minigzip measurement: `bc-641141af-3ffd-5b16-acb9-663777242042`, frozen at `8a06e96fffff1cfe6958010babaea5a9308d4961`.
- Attempt 3: `bc-cfef56ea-f25b-5590-a266-7684b5589b8e`, on `1130d45dfdd04c46784b14e6974294c437c91eba` and `c1680fcad53b9a76bdcc40f640f1962392244dd9`.
- Enwik8 set author, a different agent: `bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4`.

This set author did not write or edit the stock zlib tree, minigzip attempt 2, or minigzip attempt 3. `inputs_invented_for_this_candidate` is false. `tuned_on_this_set` is false.

## Why blind is true

The candidates existed, and were on `main`, before these corpora were selected. The inputs are whole published files: every executable in the SQLite 3.54.1 Linux x64 tools zip, and every file in the NIST STS 2.1.2 `data/` directory. Members were not dropped after a compression trial. The checker was committed with the input hashes before any frozen binary was executed on these files. GNU gzip and CPython zlib are the oracles. An injected CRC `00000000` fails the judge. One flipped byte in each gzip stream must be rejected.

SQLite 3.54.1 was released on 2026-10-16. The frozen tip `8a06e96fffff1cfe6958010babaea5a9308d4961` is 2026-11-17. NIST STS 2.1.2 is the suite linked from the CSRC page, whose listed updates run through 2014.

## What stays unchanged

`targets/zlib/blind_acceptance/`, the enwik8 evidence JSON, `targets/zlib/published_acceptance/`, `targets/zlib/NON_BLIND.md`, and `targets/zlib/held_out/` stay as they were. The Canterbury set remains `blind` false. The enwik8 records remain the earlier seal.

## What the measurement tools cannot open

`raee_reverse.path_guard` refuses `targets/zlib/blind_acceptance` and `targets/zlib/blind_broad` in the processes that install it. `tools/measure_zlib_crc32.py`, `tools/measure_zlib_minigzip_attempt2.py`, and `tools/measure_zlib_minigzip_attempt3.py` install that guard and do not name `blind_broad`. The acceptance checker is a separate process. It was not used to edit a candidate.

Rebuilding stock and attempt 2 uses `tools/reproduce_frozen_zlib_builds.py` unchanged. Attempt 3 uses `tools/reproduce_frozen_zlib_attempt3.py`, which calls the already recorded `./configure && make` recipe and applies the attempt-3 patch only in a temporary tree. Repository sources and flags are not changed to pass this set.
