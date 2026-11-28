"""Compare a Ghidra function export with a backup-engine catalog.

Disagreements are kept. Normalization only strips symbol prefixes that both
families use for the same symbol. It does not drop a name that is unique to
one side. `identical` is true only when the normalized name sets and the
address sets agree, and the program entries agree when both were observed.
"""

from __future__ import annotations

_PREFIXES = ("sym.imp.", "sym.", "imp.", "reloc.")


def parse_ghidra_export(text: str) -> list[dict]:
    functions = []
    for line in text.splitlines():
        if not line.startswith("function\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        address = parse_address(parts[2])
        if address is None or not parts[1]:
            continue
        functions.append({"name": parts[1], "entry": address})
    return functions


def parse_address(text: str) -> int | None:
    token = text.strip()
    if ":" in token:
        token = token.split(":")[-1]
    if not token:
        return None
    try:
        return int(token, 16)
    except ValueError:
        return None


def normalize_name(name: str) -> str:
    for prefix in _PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def program_entry_from_name(functions: list[dict], name: str) -> int | None:
    addresses = sorted({int(item["entry"]) for item in functions if item["name"] == name})
    if len(addresses) == 1:
        return addresses[0]
    return None


def compare_catalogs(
    ghidra: list[dict],
    backup: list[dict],
    *,
    ghidra_entry: int | None = None,
    backup_entry: int | None = None,
) -> dict:
    summary = _summarize(ghidra, backup, ghidra_entry=ghidra_entry, backup_entry=backup_entry)
    summary["address_base"] = _address_base(summary, ghidra, backup, ghidra_entry, backup_entry)
    return summary


def _summarize(
    ghidra: list[dict],
    backup: list[dict],
    *,
    ghidra_entry: int | None,
    backup_entry: int | None,
) -> dict:
    grouped_g = _group(ghidra)
    grouped_b = _group(backup)
    only_ghidra = sorted(set(grouped_g) - set(grouped_b))
    only_backup = sorted(set(grouped_b) - set(grouped_g))
    entry_disagreements = []
    entry_matches = 0
    for name in sorted(set(grouped_g) & set(grouped_b)):
        if grouped_g[name] != grouped_b[name]:
            entry_disagreements.append(
                {
                    "name": name,
                    "ghidra": sorted(grouped_g[name]),
                    "backup": sorted(grouped_b[name]),
                }
            )
        else:
            entry_matches += 1
    program_entry_disagreement = None
    if ghidra_entry is not None and backup_entry is not None and int(ghidra_entry) != int(backup_entry):
        program_entry_disagreement = {"ghidra": int(ghidra_entry), "backup": int(backup_entry), "missing": False}
    elif (ghidra_entry is None) != (backup_entry is None):
        program_entry_disagreement = {"ghidra": ghidra_entry, "backup": backup_entry, "missing": True}
    identical = not only_ghidra and not only_backup and not entry_disagreements and program_entry_disagreement is None
    return {
        "normalization": "strip prefixes sym.imp., sym., imp., reloc. in that order; compare sets of entry addresses",
        "only_ghidra": only_ghidra,
        "only_backup": only_backup,
        "entry_disagreements": entry_disagreements,
        "entry_matches": entry_matches,
        "program_entry_disagreement": program_entry_disagreement,
        "identical": identical,
        "counts": {
            "ghidra_functions": len(ghidra),
            "backup_functions": len(backup),
            "normalized_ghidra": len(grouped_g),
            "normalized_backup": len(grouped_b),
            "only_ghidra": len(only_ghidra),
            "only_backup": len(only_backup),
            "entry_disagreements": len(entry_disagreements),
            "entry_matches": entry_matches,
        },
    }


def _address_base(summary: dict, ghidra: list[dict], backup: list[dict], ghidra_entry: int | None, backup_entry: int | None):
    singles = [
        row["ghidra"][0] - row["backup"][0]
        for row in summary["entry_disagreements"]
        if len(row["ghidra"]) == 1 and len(row["backup"]) == 1
    ]
    if len(singles) < 2 or len(set(singles)) != 1:
        return None
    delta = singles[0]
    shifted = [{"name": item["name"], "entry": int(item["entry"]) - delta} for item in ghidra]
    shifted_entry = None if ghidra_entry is None else int(ghidra_entry) - delta
    after = _summarize(shifted, backup, ghidra_entry=shifted_entry, backup_entry=backup_entry)
    return {
        "ghidra_minus_backup": delta,
        "single_address_pairs": len(singles),
        "note": "raw entry_disagreements stay in this object; this block only records whether one constant separates the single-address pairs",
        "after": {
            "only_ghidra": after["only_ghidra"],
            "only_backup": after["only_backup"],
            "entry_disagreements": after["entry_disagreements"],
            "entry_matches": after["entry_matches"],
            "program_entry_disagreement": after["program_entry_disagreement"],
            "identical": after["identical"],
            "counts": after["counts"],
        },
    }


def _group(functions: list[dict]) -> dict[str, set[int]]:
    grouped: dict[str, set[int]] = {}
    for item in functions:
        grouped.setdefault(normalize_name(str(item["name"])), set()).add(int(item["entry"]))
    return grouped
