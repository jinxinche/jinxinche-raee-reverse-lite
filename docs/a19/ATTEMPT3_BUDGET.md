# Third standard-tier attempt

Declared before the probe in this file. Pass thresholds are the floors in `docs/a19/STANDARD_TIER_BUDGET.md`. They are not lowered.

These records stay failures and are not rewritten:

- `docs/a19/standard_tier.json`: stopped at 10,041 relations and 21,000 records. `standard_tier_pass` is false.
- `docs/a19/attempt2.json`: 2,000 supports, full tier not started. `standard_tier_pass` is false.

## Pass, unchanged

A run is the standard tier only when a fresh ledger reaches all of these by execution:

- 1,000 claims, 10,000 observations, 50,000 relations
- `verify_integrity` succeeds
- retracting a necessary support clears `accepted_pass`
- a cancelled task is not `SUCCEEDED`
- mixed reads and writes last at least 1,800 seconds
- concurrency bursts at 1, 2, 4, 8, and 16
- 20 sandboxed target runs, each with an explicit `execution_result` and `accepted_pass` false
- directory at or under 2 GiB

## Resource budget for deciding whether to start

- Probe directory: `/tmp/a19-attempt3-probe`. Do not reuse `/tmp/a19-standard`.
- Probe shape: 100 claims, 500 observations, 2,000 `supports`, then 500 `derived_from`.
- Stop the probe at 90 seconds or 256 MiB.
- Project 10,000 supports at the last-100 support rate, 40,000 `derived_from` at the measured derived_from rate, then add 1,800 seconds for the mixed phase and 120 seconds for setup and the 20 target runs.
- Start the full tier only if that projection is at most 2,700 seconds.
- Full-tier directory: `/tmp/a19-standard-v3`, cap 2 GiB.
- If the projection is above 2,700 seconds, do not start. Do not write 30-minute or 20-target results.
