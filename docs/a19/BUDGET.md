# A19 budget for this run

Declared before the run. This is not the standard stress tier.

## This run

- Insert 200 claim-sized ledger records and 200 support relations.
- Then run `verify_integrity`.
- Pass threshold: integrity holds, and the wall time of that insert-and-check is under 10 seconds.
- Memory threshold: the process RSS after the run is under 256 MiB.
- One process. No Ghidra. No target execution mixed in.

## Not this run

The standard tier is 1,000 conclusions, 10,000 evidence rows, 50,000 relations, concurrency 1/2/4/8/16, and at least 30 minutes. It is not attempted here. A pass of the budget above is not a standard-tier pass.

The extended tier stays out of v1, as frozen in Phase 0.
