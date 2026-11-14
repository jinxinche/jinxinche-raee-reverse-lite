# Phase 0 environment facts

Checked on the agent VM on 2026-11-14. Commands below were run. Figures marked **assumed** were not measured.

| Fact | Status | Observation |
| --- | --- | --- |
| OS | observed | Ubuntu 24.04.5 LTS, kernel `6.12.113+`, `x86_64` (`uname -a`, `/etc/os-release`) |
| CPU | observed | 4 online CPUs, `Intel(R) Xeon(R) Processor` under KVM (`lscpu`, `nproc`) |
| RAM | observed | `free -h` reported 15 GiB total. `/proc/vmstat` balloon was about 10 GiB (`balloon_inflate - balloon_deflate`). Process RSS summed to about 0.7 GiB at that moment. Usable memory is higher than `MemAvailable` alone because of the balloon. |
| Disk | observed | `/` had 247 GB free of 254 GB (`df -h`) |
| Python on the VM | observed | CPython 3.12.3 at `/usr/bin/python3`. 3.11 and 3.15 are **not** installed here. |
| Latest stable CPython | observed from python.org | 3.15.2, released 2026-10-25. 3.10.22 was the last 3.10 release (series ended 2026-10-01). 3.16.0a1 exists and is not a stable release. |
| Distro Java | observed | `/usr/bin/java` is OpenJDK 21.0.13 (2026-10-24) |
| JDK used for Ghidra | observed | Eclipse Temurin 25.0.5+8, downloaded from Adoptium and extracted at `/tmp/jdk25/jdk-25.0.5+8`. It is not a distro package and is not committed. |
| Ghidra | observed | Not on `PATH`. Release `Ghidra_12.2_build` (`ghidra_12.2_PUBLIC_20261016.zip`, GitHub asset) was downloaded and extracted under `/tmp/ghidra-dl`. With `JAVA_HOME` pointed at JDK 21, `analyzeHeadless` printed `unsupported java version` and `Unable to prompt user for JDK path, no TTY detected`. With Temurin 25, `analyzeHeadless -help` printed usage. A later headless import of `samples/dev/checksum_cli` completed; see `docs/evidence/phase2_dev_sample.json`. |
| Model API | observed | No `API_KEY`, `OPENAI`, `ANTHROPIC`, or `AZURE_OPENAI` variables were set. No model call was made. |
| Node | observed | `v22.23.4` and npm 10.9.9 are installed. REA was not installed and was not run. |
| Sandbox tools | observed | `gcc` 13.3.0, `prlimit`, and `unshare` exist. `bwrap` does not. `unshare -n true` did not provide a network namespace to the dev-sample runs (`network_namespace: false` in the evidence file). |
| Agent concurrency | observed | One agent. The scheduler test started two dev-task processes in one batch. That is not 20 agents. |

`docs/phase0/environment.observed.json` is the output of `python3 tools/collect_environment.py` after Temurin had been prepended to `PATH`. Its `java_resolved_by_path` field is therefore Temurin 25, not the distro JDK. `java_usr_bin` is the distro binary.

Nothing in this file was inferred from a plan.
