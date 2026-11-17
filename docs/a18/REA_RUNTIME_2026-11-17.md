# REA runtime comparison, 2026-11-17

This is not a product ranking. `docs/a18/REA_COMPARISON.md` stays a static sample of one. `docs/a18/rea_runtime_2026-11-15.json` stays the earlier incomplete attempt.

## Environment

- `rea-agents` 6.9.0 at `/tmp/rea-6.9.0/node_modules/.bin/rea`. `rea --version` printed `6.9.0`.
- GDB `GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1`.
- `rizin` was not on `PATH`. The apt index on this host has no `rizin` package. Radare2 was not used as a substitute.
- No model endpoint and no model API key. `model_calls` is 0. Model cost is unknown, not zero.
- Target: `/tmp/checksum_cli`, built from `samples/dev/checksum_cli.c` with `gcc -O2`.

Command: `python3 tools/run_rea_runtime.py /tmp/rea-runtime-2026 /tmp/rea-runtime-2026.json /tmp/checksum_cli`

The JSON copy is `docs/a18/rea_runtime_2026-11-17.json`.

## Failures that remain

| Attempt | Result |
| --- | --- |
| `rea capture-process` on `/tmp/checksum_cli` with terminal input `abc` | Exit 0. Signal 9, reason `idle_timeout`, about 2.578 seconds. The rendered terminal did not contain `count=3 sum=294`. The scenario schema accepts `input`, `resize`, and `signal` only. It has no EOF event. |
| `rea debug-with-gdb run` | Exit 0, about 1.375 seconds. GDB reported `No executable file specified`. One command cannot both load the ELF and redirect stdin. |

Those two attempts are not scored pairs.

## Scored pairs

The persistent GDB session is the workflow the one-shot command names. For each task the session ran `file /tmp/checksum_cli` and then `run < <stdin file>`. This tool ran the same stdin bytes through `run_sandboxed`. The contract is the program's stdout, not REA's output.

Sample size of scored pairs: 4. Declared tasks: 4. `comparison_complete` is true for this task set. `ranking` is false.

| Task | Stdin | Contract stdout | REA correct | This tool correct | REA seconds | This tool seconds |
| --- | --- | --- | --- | --- | --- | --- |
| abc | `abc` | `count=3 sum=294\n` | true | true | 0.2116 | 0.0128 |
| empty | empty | `count=0 sum=0\n` | true | true | 0.1730 | 0.0123 |
| a | `a` | `count=1 sum=97\n` | true | true | 0.1692 | 0.0120 |
| hello | `hello` | `count=5 sum=532\n` | true | true | 0.1633 | 0.0123 |

Both sides were correct on all four tasks. Correct-completion rate on this sample is 1.0 for each side. That is one host and four tasks. It is not a ranking and it does not make the 2026-11-15 scored-pair count of 0 into a pass. No savings percentage.
