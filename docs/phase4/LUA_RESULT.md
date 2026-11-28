# Lua parse goal result

The goal in `docs/phase4/GOAL_LUA.md` was committed in `39ee2082521a5ef6944330e4f3a63cb43e9fbcfb` before this measurement. That file was not edited after the numbers below. The closed zlib goals stay missed. The base64 goal is a different metric.

## Implemented

- Frozen goal: `docs/phase4/GOAL_LUA.md` and `docs/phase4/GOAL_LUA.json`.
- `tools/measure_lua_parse.py` builds two Lua 5.4.9 trees with `make linux`. The candidate adds only `MYCFLAGS=-O3`. No source edit and no `-flto`. The harness `targets/lua/harness/loadbuffer_bench.c` is the same for both trees and is compiled with `-O2`. It clocks `luaL_loadbuffer` with `CLOCK_MONOTONIC`.

## Executed

Command: `python3 tools/measure_lua_parse.py /tmp/lua-parse-work /tmp/lua-parse-result.json`

The JSON copy is `docs/evidence/lua_parse_goal.json`.

Host: Linux 6.12.113+ x86_64, gcc 13, CPython 3.12.3, Intel Xeon, 4 CPUs. One host. One pair of clean builds. `make echo` on the baseline did not contain `-O3`. `make echo` on the candidate contained `-O3` and did not contain `-flto`. rlimits were applied. The network namespace was not applied.

Correctness passed. The timed call returned 0 on 200,000 copies of `x = 1\n` (1,200,000 bytes) for both builds. `luaL_loadbuffer` of `local =\n` returned non-zero for both. `./luac -p` on empty, `return 1\n`, and `print("abc")\n` exited 0 with empty stdout and empty stderr and did not create `luac.out`. `./luac -p` on `local =\n` exited 1 with `./luac: chunk.lua:1: <name> expected near '='\n`.

| Median of 21 runs after one warmup | Nanoseconds |
| --- | --- |
| Baseline `make linux` | 15521049 |
| Candidate `MYCFLAGS=-O3` | 14706541 |
| Ratio, candidate / baseline | 0.9475223614074023 |

The bar is 0.90. The ratio is above it, so the bar was missed. `enhancement_met` is false. `stable_improvement` is false. `attempt_status` is `closed_missed`.

Cost, reported and not a second bar: `luac` grew from 225888 bytes to 277776 bytes. `liblua.a` grew from 525710 bytes to 623286 bytes.

This is one sample. It is not a stable improvement. The goal was not reopened and Lua 5.5.1 was not substituted.

## Not done

- No second host.
- No second candidate. `-flto`, a parser edit, and a different payload were not tried after this miss.
- Ghidra was not installed and was not run. That remains not done, not a pass.
- The sealed final surfaces were not opened by the measurement process.
