# Lua 5.4.9 compatible baseline

This directory builds the pinned Lua 5.4.9 tarball and checks `luac`. It is the compatible baseline, not an enhanced `luac`.

The tarball is `targets/lua/dist/lua-5.4.9.tar.gz`, SHA-256 `2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6`. The build is `make linux` inside the sandbox runner. `build_and_check.py` does not read `targets/lua/sealed_observations.json`.

Dev checks: empty file, `return 1`, `print("abc")`, the syntax error `local =`, stdin, `-v`, a missing file, and a dump without `-p`. The dump check requires a `luac.out` that starts with the Lua bytecode signature `\x1bLua`. It does not require the host-specific hash from the sealed file.

```bash
python3 build_and_check.py --prefix "$PWD/prefix"
python3 accept.py --prefix "$PWD/prefix"
```

`accept.py` is the program that reads the sealed final surfaces. Agreement there is non-blind. `accepted_pass` in that report stays false. The verdict is not universal.
