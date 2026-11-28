"""Write docs/optional/CHECKS.md from the three recorded JSON files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "optional" / "CHECKS.md"


def _load(name: str) -> dict:
    return json.loads((ROOT / "docs" / "evidence" / name).read_text(encoding="utf-8"))


def _flag(value: bool) -> str:
    return "true" if value else "false"


def main() -> int:
    network = _load("network_isolation.json")
    parity = _load("engine_parity_zlib.json")
    gzip = _load("compiler_gzip_bytes.json")
    mechanism = network["network_probe"].get("mechanism")
    lines = [
        "# Optional checks",
        "",
        "These three checks were run on this tree. Earlier phase evidence files were not edited. `unshare -n` remains the probe recorded in Phase 0. This run's connect probe is separate and is the only basis for `network_isolated`.",
        "",
        "## Network isolation",
        "",
        f"Host: {network['host']['system']} {network['host']['machine']}, Python {network['host']['python']}.",
        f"`network_isolated` is {_flag(network['network_isolated'])}. `network_namespace` is {_flag(network['network_namespace'])}. `accepted_pass` is false.",
        f"Baseline connect: {network['network_probe']['baseline_connect']}. Probe reason: {network['network_probe']['reason']}.",
        f"`unshare -n` available: {_flag(bool(network['network_probe']['unshare_n']['available']))}.",
    ]
    if network["network_probe"]["unshare_n"].get("detail"):
        lines.append(f"`unshare -n` detail: {network['network_probe']['unshare_n']['detail'].strip()}")
    for attempt in network["network_probe"]["attempts"]:
        lines.append(
            f"Attempt `{attempt['mechanism']}`: {attempt['result']}. namespace={_flag(bool(attempt['network_namespace']))}."
        )
    lines.append("Sandboxed target stdout:")
    lines.append("")
    lines.append("```")
    lines.append(network["stdout"].rstrip())
    lines.append("```")
    lines.append("")
    lines.append(f"Record: `docs/evidence/network_isolation.json`. Mechanism field: `{mechanism}`.")
    lines.append("")
    lines.append("## Backup static engine")
    lines.append("")
    locate = parity["backup"]["locate"]
    lines.append(
        f"r2pipe version: {locate.get('r2pipe_version')}. radare2 on PATH: {_flag(bool(locate.get('radare2_on_path')))}. rizin on PATH: {_flag(bool(locate.get('rizin_on_path')))}."
    )
    lines.append(f"Selected binary: `{locate.get('binary')}`. angr selected: false. angr installed: {_flag(bool(parity['backup'].get('angr_installed')))}.")
    lines.append("rizin apt-cache policy:")
    lines.append("")
    lines.append("```")
    lines.append(str(parity["backup"].get("rizin_apt_policy") or "").rstrip())
    lines.append("```")
    lines.append("")
    lines.append(
        f"Ghidra was executed in this run: {_flag(bool(parity['ghidra']['executed_this_run']))}. Source: `{parity['ghidra']['source']}`. Export sha256: `{parity['ghidra']['export_sha256']}`."
    )
    lines.append(
        f"Pinned minigzip sha256: `{parity['ghidra']['binary_sha256']}`. Rebuilt minigzip sha256: `{parity['backup'].get('binary_sha256')}`. `same_binary` is {_flag(bool(parity['same_binary']))}."
    )
    lines.append(f"`parity_executed` is {_flag(bool(parity['parity_executed']))}. `identical` is {parity['identical']}. `accepted_pass` is false.")
    if parity.get("disagreements"):
        counts = parity["disagreements"]["counts"]
        lines.append(
            "Every normalized disagreement is listed in `docs/evidence/engine_parity_zlib.json`. "
            f"Counts: only_ghidra={counts['only_ghidra']}, only_backup={counts['only_backup']}, "
            f"entry_disagreements={counts['entry_disagreements']}, entry_matches={counts['entry_matches']}."
        )
        lines.append("Names only in the Ghidra export: " + ", ".join(parity["disagreements"]["only_ghidra"]))
        lines.append("Names only in the backup list: " + ", ".join(parity["disagreements"]["only_backup"]))
        lines.append(f"Program entry disagreement: `{json.dumps(parity['disagreements']['program_entry_disagreement'])}`.")
        base = parity["disagreements"].get("address_base")
        if base:
            after = base["after"]
            lines.append(
                f"The {base['single_address_pairs']} single-address entry disagreements differ by ghidra_minus_backup={base['ghidra_minus_backup']}. "
                f"After subtracting that constant, identical is {after['identical']}, entry_matches={after['entry_matches']}, "
                f"remaining entry_disagreements={after['counts']['entry_disagreements']}."
            )
        lines.append(
            f"Backup program entry matches the ELF header: {parity.get('backup_entry_matches_elf')}. "
            f"Analysis commands: {parity['backup']['analysis'].get('analysis_commands')}."
        )
    else:
        lines.append("No function-list comparison was stored. The limitations in the JSON say why.")
    schema_path = ROOT / "docs" / "evidence" / "radare2_607_main.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        lines.append("")
        lines.append("## Radare2 6.0.7 function names")
        lines.append("")
        lines.append(
            f"Upstream `{schema['version_line']}` analyzed the pinned minigzip with `{schema['analysis_command']}`. "
            f"`main_recovered` is {_flag(bool(schema['main_recovered']))}. "
            f"Names that contain main: {', '.join(schema['names_containing_main'])}. "
            f"Functions named main: {', '.join(schema['main_names'])}."
        )
        lines.append(
            f"`offset` is in the first aflj entry: {_flag(bool(schema['offset_in_first_entry']))}. "
            f"`addr` is in the first aflj entry: {_flag(bool(schema['addr_in_first_entry']))}. "
            f"The addr type is `{schema['first_addr_type']}`."
        )
        lines.append(schema["ci_failure_cause"])
        lines.append(
            f"The Ubuntu 26.04 package `{schema['ubuntu_2604_package']}` was executed here: {_flag(bool(schema['ubuntu_package_executed_here']))}. "
            f"{schema['ubuntu_package_not_executed_because']}."
        )
        lines.append("`accepted_pass` is false. Record: `docs/evidence/radare2_607_main.json`.")
    lines.append("")
    lines.append("## Compiler gzip bytes")
    lines.append("")
    lines.append(f"gcc: {gzip.get('gcc_version')}. clang: {gzip.get('clang_version')}.")
    lines.append(f"Requested CFLAGS for both trees: `{gzip.get('requested_cflags')}`.")
    lines.append(f"`same_flags` is {gzip.get('same_flags')}. `identical` is {gzip.get('identical')}. `accepted_pass` is false.")
    if gzip.get("builds"):
        for name in ("gcc", "clang"):
            build = gzip["builds"][name]
            lines.append(
                f"{name} configure_exit={build['configure_exit']} make_exit={build['make_exit']} "
                f"minigzip sha256 `{build.get('binary_sha256')}` makefile CFLAGS `{build.get('makefile_cflags')}`."
            )
            if build.get("compile_line"):
                lines.append(f"{name} compile line: `{build['compile_line']}`")
            if build.get("makefile_cflags") != gzip.get("requested_cflags"):
                lines.append(
                    f"{name} Makefile CFLAGS is not the make override. Configure appended flags that were already in the environment. The compile line is the command that ran."
                )
    if gzip.get("comparison"):
        lines.append("Per-input gzip sha256:")
        lines.append("")
        for row in gzip["comparison"]["inputs"]:
            lines.append(
                f"- {row['name']}: equal={_flag(bool(row['equal']))} gcc `{row['stdout_sha256']}` clang `{row['other_sha256']}` "
                f"first_mismatch_offset={row['first_mismatch_offset']}"
            )
    lines.append("")
    lines.append("Record: `docs/evidence/compiler_gzip_bytes.json`.")
    lines.append("")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
