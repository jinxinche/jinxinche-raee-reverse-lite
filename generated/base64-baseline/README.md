# aklomp/base64 0.5.3 compatible baseline

This directory builds the pinned tarball and checks `bin/base64`. It is the compatible baseline, not an enhanced encoder.

The tarball is `targets/base64/dist/base64-0.5.3.tar.gz`, SHA-256 `74f83a5396660dfe5a09f0339982c03c44ef018e459a8bfcde8b31ca7444aa42`. The build is `make -j4` with no `AVX*_CFLAGS`, no `SSE*_CFLAGS`, and no `OPENMP`. `build_and_check.py` does not read `targets/base64/sealed_observations.json`.

Dev checks are the observed bytes: empty stays empty, `abc` encodes to `YWJj\n`, `-w 0` encodes `abc` to `YWJj`, `hello` encodes to `aGVsbG8=\n`, `00 01 ff` encodes to `AAH/\n`, a file holding `abc` matches stdin, `-d` of `YWJj\n` is `abc`, and `-d` of `!!!!` exits 1.

```bash
python3 build_and_check.py --prefix "$PWD/prefix"
python3 accept.py --prefix "$PWD/prefix"
```

`accept.py` is the program that reads the sealed final surfaces. Agreement there is non-blind. `accepted_pass` in that report stays false. The verdict is not universal. `roundtrip_equals_input` is not on the encode-only final rows, so the verdict leaves it `not_compared` for those rows.
