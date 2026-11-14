# Reproduction pack for the zlib 1.4 compatible baseline

Run `build_and_check.py` from a checkout that still contains `targets/zlib/dist/zlib-1.4.tar.gz`.
Dev checks do not read the sealed final-acceptance file.
`accept.py` does read it. That comparison is non-blind and is not included as expected bytes in this directory.
This pack is not an enhanced zlib and not an REA comparison.
