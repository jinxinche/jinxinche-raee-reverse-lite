# Frozen Lua parse goal

Written before any enhanced `luac` candidate. This file does not change `docs/phase4/GOAL.md`, `docs/phase4/GOAL_CRC32.md`, `docs/phase4/GOAL_MINIGZIP_ATTEMPT2.md`, or `docs/phase4/GOAL_MINIGZIP_ATTEMPT3.md`. Those goals stay as they are. It also does not change the base64 goal.

The compatible baseline has already matched the sealed `luac -p` surfaces. This file is the goal. It is not a result.

## Why this clock

`luac -p` on a small chunk returns in about the same wall time as a sandboxed `/bin/true`. A clock around `run_sandboxed` would mostly time process start. This goal clocks `luaL_loadbuffer` inside one process.

## Target

Lua 5.4.9, tarball SHA-256 `2335b6c582a52654f94612bf10d2f4672805d05329aa6568b1d8cd9e5c6fb8e6`. The program is `luac`. The timed call is `luaL_loadbuffer` on one chunk. The target is not replaced by Lua 5.5.1 or by jq.

## Metric

Median time of one `luaL_loadbuffer` call, lower better.

The chunk is the six bytes `x = 1\n` repeated 200,000 times (1,200,000 bytes). It is not a sealed final input.

## Acceptance

- Meaningful improvement: candidate median ≤ 90% of the baseline median.
- Correctness first: the timed call returns 0 on that chunk. `luaL_loadbuffer` of `local =\n` does not return 0. `./luac -p` on an empty file, on `return 1\n`, and on `print("abc")\n` still exits 0 with empty stdout and empty stderr and does not create `luac.out`. `./luac -p` on `local =\n` still exits 1 and writes `./luac: chunk.lua:1: <name> expected near '='\n` to stderr.
- If correctness fails, the candidate fails even if the median is lower.
- One thread. The candidate must not create threads.
- The only candidate is `make linux MYCFLAGS=-O3` from the pinned tarball. No source edit. No `-flto`. No other `MYCFLAGS`. The baseline is `make linux` with `MYCFLAGS` unset. Both use the sandbox runner.

## Measurement

- One warmup, then 21 measured calls. The median is the 11th sample after sorting. No other summary replaces it.
- The clock is `CLOCK_MONOTONIC` around `luaL_loadbuffer` only. Process start is outside the clock.
- The harness is the same source for both trees. It is not the candidate.
- One machine, one pair of builds. This is one sample, not a claim of a stable improvement.
- Command: `python3 tools/measure_lua_parse.py /tmp/lua-parse-work /tmp/lua-parse-result.json`
- The script refuses a bar other than 0.90. The machine-readable copy is `docs/phase4/GOAL_LUA.json`.

## Failure rule

If the candidate misses the 10% bar or fails correctness, the delivery for this goal is: not met. The numbers stay. The bar is not replaced. Lua 5.5.1 is not substituted. The base64 goal is not used as a replacement.
