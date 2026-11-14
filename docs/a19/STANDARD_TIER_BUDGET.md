# Standard-tier budget

Declared before any standard-tier execution. The earlier 200-relation run is not this tier.

## Work

- 1,000 claims, 10,000 observations, 50,000 relations in a fresh ledger under `/tmp/a19-standard`.
- Mixed reads and writes for at least 30 minutes after the load, including retraction, query, report, and cancel.
- Concurrency levels 1, 2, 4, 8, and 16 for short read bursts.
- 20 sandboxed executions of `/tmp/checksum_cli` with stdin `abc`, results saved in the ledger.
- Directory cap: stop if the ledger directory exceeds 2 GiB. Do not fill the rest of the disk.

## Pass

- Counts meet the floors above.
- `verify_integrity` succeeds at the end.
- A retracted necessary support does not leave `accepted_pass` true.
- A cancelled task is not `SUCCEEDED`.
- The mixed phase lasts at least 1800 seconds.
- All 20 target runs have an explicit `execution_result` and `accepted_pass` false at the observation layer.

## Stop without calling it a pass

If a timed probe of relation inserts shows the current ledger cannot finish 50,000 relations and the 30 minute phase in this session, record the probe and do not claim the standard tier.
