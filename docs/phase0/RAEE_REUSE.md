# What was read from jinxinche/RAEE

Clone: `/tmp/raee-ref`, commit `86eefae793fa1c67b69716690b01cf0dece8dc03` (2026-11-09). Package version in `pyproject.toml`: `0.10.0rc2`. Python `>=3.10`. License MIT. The checkout was not edited, branched, or pushed.

RAEE-Lite is a local evidence ledger for AI coding agents: requirements, check receipts, staleness after source fingerprint changes, and reports. Its README separates five roles: Intent, Change, Verification, Environment, Boundary. The research citation is the oncology preprint (DOI 10.21203/rs.3.rs-10194336/v1). The README says that preprint does not validate the coding tool. This project uses the same separation and does not claim the preprint validates reverse engineering.

## Ideas carried over, reimplemented

| RAEE piece | Use here |
| --- | --- |
| Five roles in `README.md` | Dimensions and record kinds, not one confidence score. |
| `evidence_binding.intent_digest` | Canonical JSON SHA-256. Name similarity is not coverage. |
| `evidence_binding.valid_execution` | A passed observation needs a consistent exit code and `observed_status`. Exit 0 alone is not enough. |
| `safe_process.capture_bounded` | Bounded capture, process-group kill on timeout, explicit truncation. Our sandbox also strips credentials and uses `prlimit`. It is still not a VM. RAEE's module says the same about itself. |
| `dependency_audit.py` and its docs | A static import scan that cannot finish cleanly is uncertain. A clean scan is not a closure proof. |
| Stale evidence after content change | `note_content_change` compares hashes. Paths and mtimes are not cache keys. |

## Not reused

Attestation, DSSE, CI provenance, agent-log import, Docker replay, and the `.raee` JSON ledger. Those belong to the coding-agent product. Copying them would not analyze an ELF.

No RAEE source file is vendored. The MIT notice for this repository covers this code. RAEE's copyright stays in that repository.
