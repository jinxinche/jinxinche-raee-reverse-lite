# Lua 5.4.9 `luac -p` on this branch

This is a real program. It is not `samples/dev/checksum_cli.c`. A result here is not a dev-sample result, and a dev-sample result is not a result here.

The pin commit is `782cd114e8a4a19a801cca5652c187f5f0e33304`, before this build. Source URL `https://www.lua.org/ftp/lua-5.4.9.tar.gz`. Tarball SHA-256 `2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6`. License text in the tarball is the MIT license.

## Build

Command: `python3 tools/run_lua_target.py`.

`make linux` ran through `run_sandboxed` and exited 0. `src/luac` is ELF64, little-endian, machine 62 (x86-64), type 3 (PIE executable). SHA-256 `022af191fac69891b7abc599ab67ff9a2a13f93e067110b79fec78107e703d45`. rlimits were applied. The network namespace was not applied (`unshare` returned operation not permitted).

One earlier invocation passed `Path("./luac")`. `pathlib` stringifies that to `luac`, and `prlimit` reported `failed to execute luac: No such file or directory` with exit 127. That process was not `luac`. The sealed file is the rerun that executes `./luac`.

## What `luac -p` did

The binary was copied into the work directory and invoked as `./luac`, so the program name in messages is stable. Captured stdout and stderr are data. They were not executed.

| Case | Exit | stdout | stderr | `luac.out` |
| --- | --- | --- | --- | --- |
| empty `chunk.lua` | 0 | empty | empty | absent |
| `return 1\n` | 0 | empty | empty | absent |
| `print("abc")\n` | 0 | empty | empty | absent |
| `local =\n` | 1 | empty | `./luac: chunk.lua:1: <name> expected near '='\n` | absent |
| stdin `return 1\n` as `./luac -p -` | 0 | empty | empty | absent |
| `return 1\n` without `-p` | 0 | empty | empty | present, SHA-256 `2748d1f241deede220c0f7b96016e0ce5a7eaf2648d99652b0c191acd8b3ede5` |
| `./luac -v` | 0 | `Lua 5.4.9  Copyright (C) 1994-2026 Lua.org, PUC-Rio\n` | empty | absent |
| `./luac -p chunk.lua` with no file | 1 | empty | `./luac: cannot open chunk.lua: No such file or directory\n` | absent |
| `./luac -z` | 1 | empty | starts `./luac: unrecognized option '-z'\n` | absent |

Empty stdout and empty stderr hash to `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The syntax-error stderr hashes to `f96e214441de2dc8fb34642e9da5ed3edd408f426814925aa4a01a4b56a2452f`. The version stdout hashes to `b0f630b857b5d84db9a6455cc7bc7d0e9d881e9b00b4f3165c52cf7430446175`.

The sandbox labels a non-zero exit `execution_result` `failed`. For `local =\n` that non-zero exit is the observed behavior. `truncated` is false, so the observation is complete. It is not an `accepted_pass`.

Stdin `return 1\n` matched the file case on exit, stdout hash, and the absence of `luac.out`.

## Final set

Six chunks from seed `20261126`: four valid chunks of one to five locals, plus `local =\n` and `return =\n`. A second sandboxed run matched exit, stdout hash, stderr hash, and the output-file fields on all six. `final_rerun_match` is true. Label: **non-blind**. See `targets/lua/NON_BLIND.md`.

## Recovered behavior

- `./luac -p chunk.lua` accepts an empty file and `return 1\n`, writes nothing, and does not create `luac.out`.
- The same flag rejects `local =\n` with exit 1 and the stderr line above, and still does not create `luac.out`.
- Without `-p`, the same `return 1\n` file does create `luac.out`.
- `-p` does not run the chunk. Nothing in these observations executes `print`.
- `-v` prints the copyright line and exits 0.

## Not compared

`-l`, `-s`, `-o`, every other Lua program, bytecode compatibility with another Lua version, wall time, and peak RSS were not collected. Ghidra is not installed. Static decompilation was not run. `ghidra.executed` is false and `ghidra.accepted_pass` is false. That is not a pass.

The contract is `raee_reverse.cli_contract`. It keeps those names `not_compared`.

## Compatible baseline

`python3 generated/lua-baseline/build_and_check.py --prefix /tmp/lua-base` built `make linux` in the sandbox and passed the eight dev checks. `dev_ok` is true. `accepted_pass` is false. `opened_seal` is false. The installed `luac` hash matched the sealed build, `022af191fac69891b7abc599ab67ff9a2a13f93e067110b79fec78107e703d45`.

`python3 generated/lua-baseline/accept.py --prefix /tmp/lua-base` then compared the six final chunks. `pass` is true. `acceptance` is `non-blind`. `accepted_pass` is false. `universal` is false.
