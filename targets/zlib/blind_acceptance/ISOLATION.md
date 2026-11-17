# Blind acceptance isolation

Seal time: `2026-11-17T06:13:09Z`. Candidates were already frozen at `8a06e96fffff1cfe6958010babaea5a9308d4961`. No candidate was run before the commit that adds this manifest.

## Authors

- Set and checker author: `bc-b2b647e7-62a7-5f3e-b41b-f15985b779c4`.
- Candidate author: `bc-641141af-3ffd-5b16-acb9-663777242042`, on the earlier commits that added `targets/zlib/candidate/crc32_pclmul.c` and `tools/measure_zlib_minigzip_attempt2.py` (`52d4a9e8b4918f75653b2912602a23d1cf510088`, `a912990a978ee37a595b82ae11ae6b0e4cb6ab81`, `dce39956bc96275342517d9aa307be2ffc743435`).

This set author did not write or edit the stock zlib tree, the closed LTO attempt, or minigzip attempt 2. `inputs_invented_for_this_candidate` is false. `tuned_on_this_set` is false.

## Why blind is true

The candidates existed, and were frozen, before this corpus was selected. The corpus is the whole published enwik8 file, so there was no per-file choice to fit a candidate. The checker was committed with the input hashes before either frozen binary was executed. GNU gzip and CPython zlib are the oracles. An injected CRC `00000000` fails the judge.

The set author can still read the candidate source in this checkout. That is not a second author. The candidate author could not tune on a set that was not selected until after `starting_ref`.

## What stays non-blind

`targets/zlib/published_acceptance/`, `targets/zlib/NON_BLIND.md`, and `targets/zlib/held_out/` are unchanged and stay non-blind. The same earlier agent selected the Canterbury files, wrote that harness, and wrote attempt 2.

## What the measurement tools cannot open

`raee_reverse.path_guard` refuses `targets/zlib/blind_acceptance` in the processes that install it. `tools/measure_zlib_crc32.py` and `tools/measure_zlib_minigzip_attempt2.py` install that guard and do not name this directory. The acceptance checker is a separate process. It was not used to edit a candidate.

Rebuilding uses `tools/reproduce_frozen_zlib_builds.py`, which calls the already recorded `./configure && make` recipe. The attempt-2 patch is applied only in a temporary tree. Repository sources and flags are not changed to pass this set.
