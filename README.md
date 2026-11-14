# RAEE Reverse Lite

Local evidence ledger for a small reverse-engineering workflow. Version 0.1.0 records requirements, artifacts, observations, claims, retractions, and task state. It does not reimplement a target program, and it has not been compared with REA.

The method reference is [jinxinche/RAEE](https://github.com/jinxinche/RAEE) (read-only). This repository does not modify that one.

## Install

```bash
python -m pip install .
python -m raee_reverse --version
```

Python range: 3.11 up to, and not including, 3.16. This VM executed the tests on CPython 3.12.3. The core CI matrix is Linux, Windows, and macOS on 3.11 and 3.15; a hosted run is a property of GitHub Actions for a specific commit, not of this README.

There are no runtime dependencies. `pytest` is a test extra (`pip install ".[dev]"`).

## Minimal CLI

`ok: true` means the command finished. It is not a verification pass. `rrl gate` exits 0 only when that claim's `accepted_pass` is true, and exits 2 otherwise.

```bash
python -m raee_reverse --root /tmp/rrl-demo init
python -m raee_reverse --root /tmp/rrl-demo claim add \
  --statement "stdin abc prints count=3 sum=294" \
  --scope-json '{"inputs":["stdin:abc"],"behaviors":["prints-sum"],"environments":["linux-x86_64"],"require_complete_output":true,"complete_output":true}'
python -m raee_reverse --root /tmp/rrl-demo gate CLAIM_ID
```

`tests/test_sandbox_cli.py::test_cli_gate_and_retraction` runs init, a failing gate, a linked observation, a passing gate, a retraction, and a failing gate again.

## What was executed

- Phase 0 notes: `docs/phase0/`.
- Unit tests: `python -m pytest`.
- Synthetic ELF plus headless Ghidra 12.2: `docs/phase2/DEV_SAMPLE.md`.
- zlib 1.4 sandbox build, sealed dev/tune/final surfaces, and Ghidra on `minigzip`: `docs/phase2/ZLIB.md`. Acceptance is non-blind.
- Compatible baseline: `generated/zlib-baseline/`. It matched the sealed surfaces. The reproduction copy is `repro/zlib-baseline/`.
- Offline HTML: `python -m raee_reverse --root DIR report --out report.html`.
- MCP stdio: `python -m raee_reverse.mcp_server --root DIR`.

## What is not in this tree

- A compatible or improved clone of zlib, an REA comparison, and the standard stress tier.
- An enhanced zlib. The pre-registered LTO candidate missed the 10% decompress bar (`docs/evidence/zlib_enhancement.json`).
- An REA comparison, and the standard stress tier. A smaller declared ledger budget is in `docs/a19/`.
- `d38e889` is the green 12-job matrix. `12735f05` remains a recorded failure: `docs/ci/12735f05.md`.

Check that graph JSON is valid and A14 still blocked. Also verify json dump didn't break trailing issues.

Look at A13 - I set blocked_reason None then popped it. Good.

Run a quick python json load.

Also the chmod test on Windows: after my change, if owner can read, status is no_omission. The PermissionError path is always tested via monkeypatch. Good.

macOS killpg: we catch PermissionError and proc.kill(). Timeout test should get timeout outcome. File size: wrapper sets rlimits. Need to be sure RLIMIT_FSIZE works when applied via python -c exec. The test asserts rlimits_applied True AND file size. If setrlimit fails silently inside wrapper, file could be large and test fails again. That's a real failure we'd see on CI. On macOS RLIMIT_FSIZE should work.

One issue: the wrapper is `sys.executable -c code` and the code calls os.execv(argv[0], argv). argv is the original command. For the file size test, argv is [python, -c, script]. execv replaces the wrapper with python running the write script, inheriting rlimits. Good.

prlimit path on Linux unchanged. Tests passed locally.

Windows: rlimits_applied False, test takes the non-posix branch. Good.

I'll also double-check graph JSON is valid and A19 still blocked.

Commit, push, update PR.

Then I should wait for CI? The user wants results bound to the new SHA. I should push and poll for a while. CI took about 1-2 minutes last time for ubuntu, mac a bit longer. I can push and poll with AwaitShell or repeated get_ci_status. The subscribe instruction from last turn said end the turn to receive events. This turn the user wants the conclusion. I'll push, poll a few minutes. If not done, report pending and subscribe.

Let me also verify graph file and that tarball is staged. Don't commit __pycache__.

Also look at sealed json - does it include stdout_hex of final inputs? Yes. That's the expected output in the repo. Non-blind is labeled. Good.

Commit message should explain CI fix and zlib work.

Two commits would be cleaner:
1. CI fix
2. zlib + A09 + A16

User said fix in a new commit then continue. Two commits then one push is fine. The CI runs on the final SHA which includes both. The failure record is for 12735f05. The new SHA includes the fix AND zlib. That's OK if I say the fix is in the new commit along with zlib. If CI fails for a zlib-related test, we diagnose again.

The evidence test doesn't rebuild zlib so CI shouldn't need the tarball to compile. The tarball is in the repo but tests only check hashes in JSON. Good.

Windows chmod test logic: monkeypatch then undo. On Windows read_bytes after chmod 0 succeeds, second audit is no_omission. First audit with monkeypatch is uncertain. Good.

Let me validate graph and then commit in two commits? One commit is simpler for "results bound to the new SHA" as one SHA. The user said "a new commit" for the fix. I'll make two commits:
1. Fix Windows/macOS test failures
2. zlib seal, contract, MCP, HTML

Then push both. CI runs on the tip. I'll mention both SHAs.

Need to split the index carefully with git add.

Commit 1 files:
- src/raee_reverse/sandbox.py
- src/raee_reverse/scheduler.py
- tests/test_cache_audit_attribution.py
- docs/ci/12735f05.md
- tests/COLLECTED_IDS.txt might include new tests so it belongs with commit 2. If I commit the floor early, CI of commit 1 would fail the floor if I only commit the chmod test change without new tests... Commit 1's floor must match the tests in that commit. If I change the unreadable test but not add tests, the floor ids stay 46 if the test name is unchanged. COLLECTED_IDS currently has 52 after --write. I should regenerate floor only at the end and include it in the second commit. First commit shouldn't include the 52-id floor or CI of an intermediate commit isn't what we push... We push both, CI only on the tip if we push once. Intermediate commit isn't tested by Actions if we push both together (Actions tests the pushed SHA, the tip). Good.

One commit is OK too. I'll do one commit that says it fixes the CI failures and records zlib, so one SHA to watch. The user said "a new commit" singular is fine.

Let me json-check graph and look at A14 blocked_reason still present.

Task states: `docs/tasks/graph.json`. One agent wrote them. `SUCCEEDED` on a scheduler task is not `accepted_pass`.
