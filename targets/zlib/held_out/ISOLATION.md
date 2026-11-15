# Held-out acceptance is not blind

The dev, tune, and final surfaces in `targets/zlib/sealed_observations.json` stay non-blind. `targets/zlib/NON_BLIND.md` is unchanged.

This directory is a separate held-out set. It is still not blind. One agent wrote the input bytes, this note, the checker in `src/raee_reverse/held_out.py`, and the crc32 candidate. That agent can read every file here. A single-agent run cannot honestly be called blind, so this set is not called blind.

## What is isolated

- Input bytes live here. Expected gzip bytes are not stored.
- `MANIFEST.json` records the SHA-256 and length of each input. `SEAL.sha256` is the SHA-256 of that manifest file.
- `tools/measure_zlib_crc32.py` installs `raee_reverse.path_guard` before it builds or times anything. The guard raises if that process opens `targets/zlib/held_out` or `targets/zlib/sealed_observations.json`.
- The candidate is one fixed PCLMULQDQ path. There is no loop that reads expected answers and retries.

## What the checker uses

- The published ISO-HDLC CRC-32 of the ASCII bytes `123456789`, which is `cbf43926`. That constant is not an output this agent measured and then stored as the expected gzip.
- CPython's `zlib.crc32` on the same bytes. On this machine that is zlib 1.3, not the zlib 1.4 under test. A disagreement between that value and `cbf43926` is a failed check, not a pass.
- GNU gzip, when it is on `PATH`, decompresses the candidate `minigzip` bytes. Those bytes are not an agent-written expected file.
- An injected CRC of `00000000` for `123456789` must fail the checker. The unit test `tests/test_held_out.py` does that.

Self-built round trips are not the only check. They are also not a blind trial.
