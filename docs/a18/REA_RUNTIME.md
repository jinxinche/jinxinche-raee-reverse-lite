# REA runtime attempt, 2026-11-15

This is not a ranking. The static sample in `docs/a18/REA_COMPARISON.md` stays a sample of one and is not promoted.

## What was installed and run

- `rea-agents` 6.9.0 from the earlier install path `/tmp/rea-6.9.0`. `rea --version` printed `6.9.0`.
- GDB `GNU gdb (Ubuntu 15.1-1ubuntu1~24.04.1) 15.1` was installed so `debug-with-gdb` could be attempted. `rizin` was not on `PATH`.
- No model endpoint and no model API key. Model cost is unknown, not zero. `model_calls` recorded here is 0 because these two commands do not take a model.

## Commands

`python3 tools/run_rea_runtime.py /tmp/rea-runtime /tmp/rea-runtime.json /tmp/checksum_cli`

The JSON copy is `docs/a18/rea_runtime_2026-11-15.json`.

| Attempt | Result |
| --- | --- |
| `rea capture-process` on `/tmp/checksum_cli` with terminal input `abc` | Exit 0. The capture ended with signal 9, reason `idle_timeout`, after about 2.376 seconds. The rendered terminal contained `abc` and did not contain `count=3 sum=294`. |
| `rea debug-with-gdb run` with an inferior TTY | Exit 0. GDB reported `No executable file specified`. One command cannot both load the ELF and redirect stdin; `run` with redirection is rejected by REA. |

`checksum_cli` reads stdin until EOF. REA's process capture is a PTY. The PTY did not deliver EOF before the idle timeout killed the process, so the program never printed. That is an attempted runtime observation, not a scored pair.

## What is not claimed

`comparison_complete` is false. `executed` is false for the comparison. Sample size of scored pairs is 0. Correct-completion rate, coverage, time to a correct result, and resource cost were not collected. No savings percentage. The original RAEE research is not evidence that this tool wins.
