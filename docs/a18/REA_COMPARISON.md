# REA 6.9.0 comparison

REA was installed and run. The comparison is one static task, one sample, not a stable ranking.

## Install

- Package: `rea-agents@6.9.0` (npm pack reported that version, shasum `d48047b60abccc7a9acdaf9097955ddea8f0df04`).
- Command: `npm install rea-agents@6.9.0` in `/tmp/rea-6.9.0` (not the repository). Exit 0. `rea --version` printed `6.9.0`.
- Node `v22.23.4`, which matches the package engine `^22.23.4`.
- No model API key was set. No Hopper, IDA, JADX, or Kuna install was added.

## Shared task and budget

Target: `/tmp/checksum_cli`, SHA-256 `89f0c6003fe2846b6d3b88d71f031340457c4977dc070130c7d8b518a561d9ae` (the same bytes as `docs/evidence/phase2_dev_sample.json`).

Task: with Ghidra only, recover the `checksum` function's signature and modulus. Budget: one provider (`ghidra`), 180 second wall cap per command, no model call, no extra engine installed.

`rea doctor --provider ghidra --target /tmp/checksum_cli --format json` exited 0. Ghidra checks were `ok: true` (Ghidra 12.2, JDK 25.0.5, headless binary present). `environment_healthy` was false because Hopper, IDA, JADX, and Kuna are not installed. Those were outside the shared provider budget, so they were not installed to make REA look more ready.

## Executed commands

| Tool | Command | Wall seconds | Result |
| --- | --- | --- | --- |
| REA 6.9.0 | `rea analyze /tmp/checksum_cli --provider ghidra --format json` | 11.307 (`command_ms` 9958) | exit 0. Overview of the ELF. The normalized inventory did not include the `checksum` pseudocode. |
| REA 6.9.0 | `rea function /tmp/checksum_cli checksum --provider ghidra --format json` | 11.055 (`command_ms` 9646) | exit 0. Pseudocode shows `sum = (data[index] + sum) % 0xfff1` and signature `uint32_t checksum(uchar *data, size_t length, uint32_t *count)`. `confidence` is `observed`. Ten limitation strings were returned. |
| This tool | `analyze_elf` with `ExportNamed.java`, functions `checksum,main`, timeout 180 | 6.959 | exit 0. Export contains `decompiled=true checksum` and `0xfff1`. `accepted_pass` is false. |

Sample size is one run of each command on one binary. The wall times include process start and are not a distribution. A faster single run is not a stable performance claim.

Runtime behavior (`stdin abc` prints `count=3 sum=294`) was collected earlier by this tool's sandbox and was not part of these REA commands. REA was not asked to execute the ELF, so this comparison does not score runtime evidence.

## What is not claimed

No accuracy percentage, no token cost, and no win/loss across a task suite. Both static runs recovered the same modulus on this one function.
