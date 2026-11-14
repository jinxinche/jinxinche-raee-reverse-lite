# zlib 1.4 compatible baseline

This project builds the frozen zlib 1.4 tarball and installs `minigzip` and a small `crc32_cli` harness. It is the compatible baseline, not an enhanced zlib.

The tarball is `targets/zlib/dist/zlib-1.4.tar.gz`, SHA-256 `02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584`, tag `v1.4`. The implementation is that source built with `./configure && make`. It was not fitted to the final-acceptance file.

Acceptance against the sealed final surfaces is **non-blind**. `accept.py` is the only program here that reads `targets/zlib/sealed_observations.json`, and it is run after this build recipe is fixed. `compression_level_9` is not part of the verdict.

## Install

From this directory, on Linux with `gcc` and `make`:

```bash
python3 build_and_check.py --prefix "$PWD/prefix"
"$PWD/prefix/bin/minigzip" < /dev/null | "$PWD/prefix/bin/minigzip" -d
```

`build_and_check.py` configures and builds inside the RAEE Reverse Lite sandbox runner, then checks dev inputs only: round trip, gzip magic `1f8b` with a zero mtime, and crc32(`abc`) = `352441c2`. Those checks do not read the final-acceptance file.

The installed binaries do not need the zlib source tree on `PATH` or as the working directory.

## Accept

```bash
python3 accept.py --prefix "$PWD/prefix"
```

This regenerates the sealed inputs from the published generator and compares the collected surfaces. A mismatch is a failure. It is not a reason to edit this baseline to chase the final file.
