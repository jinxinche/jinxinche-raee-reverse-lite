"""Bounded static import audit.

A scan that reports no omission is not a proof of dependency closure.
Dynamic imports, unreadable files, and syntax errors are uncertain.
An import that is not declared is an incomplete scope, not a pass.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def audit_python_tree(root: Path, declared_third_party: set[str] | None = None) -> dict:
    root = Path(root)
    declared = {name.replace("-", "_").lower() for name in (declared_third_party or set())}
    local = _local_names(root)
    stdlib = set(sys.stdlib_module_names)
    third_party: set[str] = set()
    dynamic: list[dict] = []
    unreadable: list[str] = []
    syntax_errors: list[dict] = []
    scanned = 0
    if not root.is_dir():
        return _result(
            "uncertain",
            third_party=set(),
            missing=set(),
            dynamic=[],
            unreadable=[str(root)],
            syntax_errors=[],
            scanned=0,
            notes=["audit root is not a directory"],
        )
    for path in sorted(root.rglob("*.py")):
        if any(part in {".venv", "venv", "__pycache__", ".git"} for part in path.parts):
            continue
        if path.is_symlink():
            unreadable.append(str(path))
            continue
        scanned += 1
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            unreadable.append(str(path))
            continue
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append({"path": str(path), "message": str(exc)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _consider(alias.name, local, stdlib, third_party)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if node.module:
                    _consider(node.module, local, stdlib, third_party)
            elif isinstance(node, ast.Call):
                if _is_dynamic_import(node):
                    dynamic.append({"path": str(path), "line": getattr(node, "lineno", None)})
    missing = {name for name in third_party if name.lower() not in declared}
    notes = [
        "a static import scan is not a proof of dependency closure",
        "distribution names are compared only after replacing '-' with '_'",
    ]
    if missing:
        status = "incomplete_scope"
    elif dynamic or unreadable or syntax_errors:
        status = "uncertain"
    else:
        status = "no_omission_detected"
    return _result(
        status,
        third_party=third_party,
        missing=missing,
        dynamic=dynamic,
        unreadable=unreadable,
        syntax_errors=syntax_errors,
        scanned=scanned,
        notes=notes,
    )


def _local_names(root: Path) -> set[str]:
    names: set[str] = set()
    try:
        children = list(root.iterdir())
    except OSError:
        return names
    for child in children:
        if child.name.startswith("."):
            continue
        if child.is_dir() and (child / "__init__.py").exists():
            names.add(child.name)
        elif child.suffix == ".py":
            names.add(child.stem)
    return names


def _consider(module: str, local: set[str], stdlib: set[str], third_party: set[str]) -> None:
    top = module.split(".", 1)[0]
    if top in local or top in stdlib:
        return
    third_party.add(top)


def _is_dynamic_import(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "__import__":
        return True
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        return True
    return False


def _result(
    status: str,
    *,
    third_party: set[str],
    missing: set[str],
    dynamic: list[dict],
    unreadable: list[str],
    syntax_errors: list[dict],
    scanned: int,
    notes: list[str],
) -> dict:
    return {
        "status": status,
        "closure_proof": False,
        "accepted_pass": False,
        "third_party_imports": sorted(third_party),
        "missing_declarations": sorted(missing),
        "dynamic_imports": dynamic,
        "unreadable": unreadable,
        "syntax_errors": syntax_errors,
        "files_scanned": scanned,
        "limitations": notes,
    }
