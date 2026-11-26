# Published acceptance inputs

These files are the Canterbury corpus from `cantrbry.tar.gz`.

- Source: `https://corpus.canterbury.ac.nz/resources/cantrbry.tar.gz`
- Tarball SHA-256: `f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb`
- File names, lengths, and SHA-256 values are in `MANIFEST.json`. `SEAL.sha256` is the SHA-256 of that manifest with LF newlines.

The bytes were not invented for the minigzip candidate. Expected gzip bytes are not stored.

## Not blind

The same agent selected this corpus, wrote the checker harness, and wrote the minigzip attempt-2 candidate. GNU gzip and CPython zlib are the oracles. That is not isolation of authorship. `blind` is false. `targets/zlib/NON_BLIND.md` and `targets/zlib/held_out/` stay as they were.

`tools/measure_zlib_minigzip_attempt2.py` and `tools/measure_zlib_crc32.py` install a process guard that refuses this directory, `targets/zlib/held_out`, and `targets/zlib/sealed_observations.json`. The acceptance check is a separate process. It was not used to edit the candidate.
