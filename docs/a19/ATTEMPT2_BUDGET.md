# Second standard-tier attempt

Declared before the probe in this file. Pass thresholds are the floors in `docs/a19/STANDARD_TIER_BUDGET.md`. They are not lowered. `docs/a19/standard_tier.json` stays a failure: `standard_tier_executed` false, `standard_tier_pass` false, stop at 10,041 relations and 21,000 records.

## Pass, unchanged

A later run is the standard tier only when a fresh ledger reaches all of these by execution:

- 1,000 claims, 10,000 observations, 50,000 relations
- `verify_integrity` succeeds
- retracting a necessary support clears `accepted_pass`
- a cancelled task is not `SUCCEEDED`
- mixed reads and writes last at least 1,800 seconds
- 20 sandboxed `/tmp/checksum_cli` runs, each with an explicit `execution_result` and `accepted_pass` false
- directory at or under 2 GiB

## Resource budget for deciding whether to start

- Probe directory: `/tmp/a19-attempt2`. Do not treat `/tmp/a19-standard` as a pass.
- Probe shape: 100 claims, 500 observations, then `supports` relations.
- Stop the probe at 90 seconds of relation inserts or 256 MiB, whichever comes first.
- Start the full tier only if the last 100 supports, scaled linearly by relation count from that rate through 50,000 relations, plus 1,800 seconds, fits in 2,700 seconds.
- If that projection is above 2,700 seconds, do not start the full tier. Do not write 30-minute or 20-target results.
