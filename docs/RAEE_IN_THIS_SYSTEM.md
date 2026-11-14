# How the evidence model is used

A record has five independent fields: provenance (`observed`, `imported`, `model_generated`), execution result (`not_executed`, `passed`, `failed`, `uncertain`), applicability (`valid`, `stale`, `retracted`, `incomplete_scope`), usage (`support`, `oppose`, `qualify`, `background`), and a verification scope. None of them is a confidence percentage.

`accepted_pass` is derived. It is true only when the current projection is an applicable, supported claim with at least one independent source family and an explicit scope, and when counterevidence and missing necessary premises are absent. The dev-sample claim that passed is limited to stdin `abc` on Linux x86-64. The evidence file sets `not_universal` true.

Raw `records`, `relations`, and `events` are append-only SQLite tables with triggers that abort updates and deletes. Current conclusions are projections. Retraction inserts a retraction record, marks applicability `retracted`, and recomputes the support set. It does not delete the old observation. A stale evaluation payload can still say that an earlier conclusion was a pass; its projection is `stale`, and the claim's current `accepted_pass` is whatever the recomputation says.

Same-source duplicates share `source_family` and count once. Retracting one member of that family removes the family from support. A different family can keep the claim accepted.

The scheduler states are `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `BLOCKED`, and `CANCELLED`. `SUCCEEDED` there means the handler returned. It does not set `accepted_pass`. Infrastructure failures retry until `max_attempts`. Deterministic failures do not. A killed process that never published a result is recovered to `QUEUED` or `FAILED`, not to success.
