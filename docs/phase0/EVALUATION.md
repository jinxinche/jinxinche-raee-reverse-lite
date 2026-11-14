# Evaluation rules

## Four-way status

Every phase report uses these four labels and no blended "done":

1. **Implemented** — code or documents are in the tree.
2. **Executed** — a command or test was run and its output was kept.
3. **Unverified hypothesis** — a design claim that this run did not measure.
4. **Not done** — blocked by environment, scope, or time. Absence is not a pass.

## Splits

| Set | What it is in this run | Blind? |
| --- | --- | --- |
| Dev | `tests/` and `samples/dev/checksum_cli.c` | No. The same agent wrote the tests and the code. |
| Tune | Not created. No model was called and no parameter was fit. | n/a |
| Final acceptance | The zlib 1.4 procedure in `TARGETS.md`. Inputs are not sealed. The target was not built. | Not run. A later run by this same agent would still be non-blind unless someone else seals the inputs. |

Rules that stay in force:

- A test id removed from `tests/COLLECTED_IDS.txt` fails CI. The floor is an exact set, not a minimum that can be padded.
- `accepted_pass` requires a valid applicable claim, at least one independent source family, explicit input/behavior/environment scope, and no counterevidence or retracted necessary premise.
- Exit code 0 of `rrl` means the command finished, except `rrl gate`, which exits 0 only for `accepted_pass` and 2 otherwise.
- Exit code 0 of a target is an observation about that process. It does not accept a claim by itself.
- Uncertain, truncated, stale, missing, and retracted states are not passes.
- Same-source copies share a `source_family`. A retraction of one record removes the whole family from support. Other families can still support the claim. Records are not deleted.
- Name similarity is rejected (`E_SIMILARITY_NOT_COVERAGE`).
- Cache hits require content, dependency, tool version, parameters, config, and a complete environment. Paths and mtimes are ignored. An incomplete environment is stored and not reused.
- Attribution helpers are arithmetic on a caller-supplied value function. Missing coalitions stay missing. Results set `causal_claim` false.
- Static import audit sets `closure_proof` false even when no omission is detected.

## What would count as a later pass

A zlib improvement counts only if the sealed correctness set passes, the pre-registered primary metric clears its threshold, and the protected metric stays inside its regression cap, on a named host, with the sample size written down. One measurement is not a stable improvement. A dev-sample `accepted_pass` is not that result.
