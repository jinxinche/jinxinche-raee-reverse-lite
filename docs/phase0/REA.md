# REA baseline

REA was identified. It was not installed, not started, and not compared.

## What was checked

- GitHub API `repos/morluto/rea` on 2026-11-14: description "Reverse engineer anything with agents, from app behavior down to native binaries." License MIT. `stargazers_count` 458493 at the time of the call. The star count was not audited and is not a quality result.
- Latest release: tag `rea-agents-6.9.0`, published 2026-11-12T08:59:13Z. `package.json` at that tag has `"version": "6.9.0"`, bin `rea`, and engines `node: ^22.23.4 || ^24.22.1 || >=26.12.1`.
- This VM's Node is v22.23.4, which matches the lower engine bound. That only means a later run could try to install it. This run did not.
- `jinxinche` repository list (21 repos visible to this account) has no repository named REA. `jinxinche/elf-proof` is a medical time-series README, not a reverse-engineering tool.
- A clone of `jinxinche/RAEE` at `86eefae793fa1c67b69716690b01cf0dece8dc03` has no `REA` match in the tree that was searched.

Public docs describe REA as a local CLI and MCP server that calls Hopper, Ghidra, IDA, or other providers and returns evidence objects. That description is from the project README and CLI doc. It is not a measurement of REA on our sample.

## Impact

Work unit A18 (comparison, ablation, statistics) cannot succeed. No accuracy, cost, or runtime number versus REA is claimed. Phase 6 remains not done.
