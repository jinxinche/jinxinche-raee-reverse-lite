# Extended-tier budget

Declared before the probe and before any extended-tier execution. Phase 0 had marked this tier as not required. This file does not change that history, and it does not change the standard-tier records.

These stay as they are:

- `docs/a19/standard_tier.json`: stopped at 10,041 relations and 21,000 records. `standard_tier_pass` is false.
- `docs/a19/attempt2.json`: 2,000 supports, full tier not started. `standard_tier_pass` is false.
- `docs/a19/standard_tier_v3.json`: the later standard-tier run passed its own floors.

The machine-readable copy of this budget is `docs/a19/EXTENDED_TIER_BUDGET.json`. The probe and the runner read that file. They do not lower the floors below.

## Scale

- 10,000 claims
- 100,000 observations
- 250,000 relations, of which 100,000 are `supports` and 150,000 are `derived_from`
- Mixed reads and writes for at least 1,800 seconds, interleaving a query, a report, a new write, a retraction, and a cancel
- Concurrency bursts at 1, 2, 4, 8, and 16
- 20 sandboxed executions of the checksum sample, with stdout saved
- Latency P50, P95, and P99 for load inserts and for mixed-phase operations, each with its sample size

## Pass

A run is the extended tier only when a fresh ledger reaches all of these by execution:

- the counts above
- `verify_integrity` succeeds
- retracting a necessary support clears `accepted_pass`
- a cancelled task is `CANCELLED` and is not `SUCCEEDED`
- the mixed phase lasts at least 1,800 seconds
- the concurrency bursts ran
- all 20 target runs have an explicit `execution_result`, saved stdout `count=3 sum=294\n`, and `accepted_pass` false
- both latency percentile groups are present and each sample size is at least 1
- the ledger directory stays at or under 4 GiB

A partial load is not a pass. A probe is not a pass.

## Probe, then start only inside the cap

- Probe directory: `/tmp/a19-extended-probe`. Do not reuse a standard-tier directory.
- Probe shape: 100 claims, 1,000 observations, 2,000 `supports`, 500 `derived_from`.
- Stop the probe at 120 seconds or 512 MiB. An unfinished probe does not start the full tier.
- Project claims, observations, supports, and `derived_from` from the measured rates. The support rate is the last 100 supports. Multiply that load by 1.5. Add 1,800 seconds for the mixed phase and 180 seconds for setup, the 20 target runs, and integrity.
- Project the directory as probe bytes times full-record-count over probe-record-count, times 2.
- Start the full tier only if the projected seconds are at most 4,200 and the projected directory is at most 4 GiB.
- Full-tier directory: `/tmp/a19-extended`, cap 4 GiB.
- If the load phase exceeds the projected load seconds, stop and do not enter the mixed phase. That stop is not a pass.
