"""Build zlib 1.4 in the sandbox, seal input sets, and record one Ghidra run.

Final-acceptance outputs are written by this process. The same agent can read
them, so the acceptance label is non-blind. This script does not read the
final expected file while choosing the dev or tune inputs: those bytes are
fixed in DEV_INPUTS and TUNE_INPUTS below.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from raee_reverse.canonical import digest_bytes  # noqa: E402
from raee_reverse.compare import UNCOLLECTED_SURFACES, compare_surfaces  # noqa: E402
from raee_reverse.experiments import select_experiment  # noqa: E402
from raee_reverse.ghidra_adapter import analyze_elf  # noqa: E402
from raee_reverse.sandbox import run_sandboxed  # noqa: E402
from raee_reverse.shrink import shrink_bytes  # noqa: E402
from raee_reverse.store import Store  # noqa: E402

TARBALL = ROOT / "targets" / "zlib" / "dist" / "zlib-1.4.tar.gz"
TARBALL_SHA256 = "02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584"
HARNESS = ROOT / "targets" / "zlib" / "harness" / "crc32_cli.c"
SCRIPT = ROOT / "samples" / "dev" / "ghidra" / "ExportNamed.java"
OUT_DIR = ROOT / "targets" / "zlib"
EVIDENCE = ROOT / "docs" / "evidence" / "zlib_phase2.json"
GHIDRA = Path(os.environ.get("GHIDRA_INSTALL_DIR", "/tmp/ghidra-dl/ghidra_12.2_PUBLIC"))
JAVA = Path(os.environ.get("JAVA_HOME", "/tmp/jdk25/jdk-25.0.5+8"))

DEV_INPUTS = {
    "empty": b"",
    "abc": b"abc",
    "hello": b"hello",
}
TUNE_INPUTS = {
    "tune-alpha": b"tune-alpha",
    "tune-repeat": b"tune-beta" * 10,
    "tune-range": bytes(range(64)),
}


def _extract_checked(archive: tarfile.TarFile, dest: Path) -> None:
    root = dest.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise SystemExit(f"tarball path escapes the work directory: {member.name}")
        archive.extract(member, root)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run(binary: str, data: bytes, work: Path, args: list[str] | None = None) -> dict:
    return run_sandboxed(
        [binary, *(args or [])],
        work_dir=work,
        stdin=data,
        timeout=20,
        cpu_seconds=10,
        fsize_bytes=5_000_000,
        max_output_bytes=2_000_000,
    )


def _observe(minigzip: str, crc_bin: str, data: bytes, work: Path) -> dict:
    compressed = _run(minigzip, data, work / "comp")
    if compressed["truncated"] or compressed["returncode"] != 0:
        roundtrip = False
        decompress_exit = None
    else:
        decompressed = _run(minigzip, compressed["stdout"], work / "dec", ["-d"])
        roundtrip = (
            not decompressed["truncated"]
            and decompressed["returncode"] == 0
            and decompressed["stdout"] == data
        )
        decompress_exit = decompressed["returncode"]
    crc = _run(crc_bin, data, work / "crc")
    crc_text = crc["stdout"].decode("ascii", "replace").strip()
    return {
        "stdout_sha256": _sha(compressed["stdout"]),
        "stderr_sha256": _sha(compressed["stderr"]),
        "exit_code": compressed["returncode"],
        "roundtrip_equals_input": roundtrip,
        "crc32_hex": crc_text if crc["returncode"] == 0 and not crc["truncated"] else None,
        "decompress_exit_code": decompress_exit,
        "stdout_hex": compressed["stdout"].hex(),
        "execution_result": compressed["execution_result"],
        "truncated": compressed["truncated"],
        "rlimits_applied": compressed["rlimits_applied"],
        "network_namespace": compressed["network_namespace"],
        "limitations": compressed["limitations"],
    }


def _public(observation: dict) -> dict:
    copied = dict(observation)
    copied.pop("stdout_hex", None)
    return copied


def main() -> int:
    blob = TARBALL.read_bytes()
    if digest_bytes(blob) != TARBALL_SHA256:
        raise SystemExit("tarball sha256 does not match the frozen pin")
    OUT_DIR.joinpath("sets").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rrl-zlib-") as temporary:
        root = Path(temporary)
        with tarfile.open(TARBALL, "r:gz") as archive:
            _extract_checked(archive, root)
        source = root / "zlib-1.4"
        configure = run_sandboxed(
            ["./configure"], work_dir=source, timeout=90, cpu_seconds=60, fsize_bytes=80_000_000
        )
        make = run_sandboxed(
            ["make", "-j4"], work_dir=source, timeout=180, cpu_seconds=120, fsize_bytes=80_000_000
        )
        if configure["returncode"] != 0 or make["returncode"] != 0:
            raise SystemExit(f"build failed configure={configure['returncode']} make={make['returncode']}")
        minigzip = source / "minigzip"
        libz = source / "libz.a"
        crc_bin = root / "crc32_cli"
        built = subprocess.run(
            ["gcc", "-O2", "-o", str(crc_bin), str(HARNESS), f"-I{source}", str(libz)],
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode != 0:
            raise SystemExit(built.stderr)
        pin = {
            "project": "zlib",
            "tag": "v1.4",
            "tarball_sha256": TARBALL_SHA256,
            "license": "zlib license, from zlib.h in this tarball",
            "minigzip_sha256": digest_bytes(minigzip.read_bytes()),
            "libz_a_sha256": digest_bytes(libz.read_bytes()),
            "build": {
                "configure_exit": configure["returncode"],
                "make_exit": make["returncode"],
                "sandbox": True,
                "rlimits_applied": bool(make["rlimits_applied"]),
                "network_namespace": bool(make["network_namespace"]),
            },
            "acceptance": "non-blind",
            "acceptance_reason": "the same agent generated the sealed outputs and can read them",
        }
        sets = {}
        for split, mapping in (("dev", DEV_INPUTS), ("tune", TUNE_INPUTS)):
            sets[split] = {}
            for name, data in mapping.items():
                observed = _observe(str(minigzip), str(crc_bin), data, root / split / name)
                sets[split][name] = {
                    "input_sha256": _sha(data),
                    "input_length": len(data),
                    "observed": _public(observed),
                    "stdout_hex": observed["stdout_hex"],
                }
        final_inputs = {}
        generator = random.Random(20261114)
        for index, length in enumerate((1, 2, 7, 16, 32, 100, 256, 1000)):
            final_inputs[f"final-{index}-len{length}"] = bytes(generator.randrange(256) for _ in range(length))
        sets["final"] = {}
        for name, data in final_inputs.items():
            observed = _observe(str(minigzip), str(crc_bin), data, root / "final" / name)
            sets["final"][name] = {
                "input_sha256": _sha(data),
                "input_length": len(data),
                "observed": _public(observed),
                "stdout_hex": observed["stdout_hex"],
            }
        # Level experiment uses a tune input only. Predictions were fixed before this call.
        tune_payload = TUNE_INPUTS["tune-alpha"]
        selection = select_experiment(
            [
                {"name": "levels-identical"},
                {"name": "level-9-differs"},
            ],
            [
                {
                    "name": "run-default-and-level-9",
                    "cost": 2,
                    "predictions": {
                        "levels-identical": "stdout_sha_equal",
                        "level-9-differs": "stdout_sha_differ",
                    },
                }
            ],
        )
        default_run = _run(str(minigzip), tune_payload, root / "level-default")
        level9 = _run(str(minigzip), tune_payload, root / "level-9", ["-9"])
        level_result = {
            "selection": selection,
            "default_sha256": _sha(default_run["stdout"]),
            "level9_sha256": _sha(level9["stdout"]),
            "stdout_equal": default_run["stdout"] == level9["stdout"],
            "surviving_hypothesis": (
                "levels-identical" if default_run["stdout"] == level9["stdout"] else "level-9-differs"
            ),
            "input": "tune-alpha",
            "used_final_acceptance_set": False,
        }
        # Shrink one failing decompress of a truncated dev gzip. Not a global minimum.
        abc_gzip = bytes.fromhex(sets["dev"]["abc"]["stdout_hex"])
        truncated = abc_gzip[:-1]

        def decompress_fails(candidate: bytes) -> bool:
            result = _run(str(minigzip), candidate, root / "shrink", ["-d"])
            return result["returncode"] != 0

        reduced = shrink_bytes(truncated, decompress_fails)
        shrink_record = {
            "seed_length": len(truncated),
            "reduced_length": len(reduced["reduced"]),
            "reduced_sha256": _sha(reduced["reduced"]),
            "steps": reduced["steps"],
            "predicate_held": reduced["predicate_held"],
            "global_minimum": False,
        }
        ghidra_out = root / "ghidra.txt"
        ghidra = analyze_elf(
            minigzip,
            ghidra_home=GHIDRA if (GHIDRA / "support" / "analyzeHeadless").is_file() else None,
            java_home=JAVA if (JAVA / "bin" / "java").is_file() else None,
            project_dir=root / "ghidra-project",
            script_path=SCRIPT,
            output_path=ghidra_out,
            timeout=300,
            extra_env={"RRL_GHIDRA_FUNCTIONS": "main,crc32"},
        )
        export_text = ghidra.get("export_text") or ""
        ghidra_record = {
            "executed": ghidra.get("outcome") == "completed" and bool(export_text),
            "execution_result": ghidra.get("execution_result"),
            "accepted_pass": False,
            "simulated": False,
            "returncode": ghidra.get("returncode"),
            "saw_crc32": "function\tcrc32\t" in export_text,
            "saw_main": "function\tmain\t" in export_text,
            "decompiled_crc32": "decompiled=true\tcrc32" in export_text,
            "decompiled_main": "decompiled=true\tmain" in export_text,
            "export_sha256": digest_bytes(export_text.encode()) if export_text else None,
            "export_text": export_text,
            "limitations": ghidra.get("limitations", []),
            "stderr_tail": (ghidra.get("stderr_tail") or "")[-1500:],
        }
        # Ledger: one dev claim, supported by the fresh abc observation only.
        store = Store(root / "ledger")
        try:
            artifact = store.add_record(
                kind="artifact",
                payload={
                    "content_digest": store.put_blob(minigzip.read_bytes()),
                    "size": minigzip.stat().st_size,
                    "path_hint": "minigzip",
                    "zlib_tag": "v1.4",
                    "tarball_sha256": TARBALL_SHA256,
                },
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope={
                    "inputs": ["tarball:" + TARBALL_SHA256],
                    "behaviors": ["built minigzip"],
                    "environments": ["linux-x86_64"],
                    "complete_output": True,
                },
            )
            abc = sets["dev"]["abc"]["observed"]
            scope = {
                "inputs": ["stdin:" + sets["dev"]["abc"]["input_sha256"]],
                "behaviors": [
                    "stdout_sha256 matches sealed dev/abc",
                    "exit 0",
                    "roundtrip",
                    "crc32 " + str(abc["crc32_hex"]),
                ],
                "environments": ["linux-x86_64", "zlib-1.4"],
                "require_complete_output": True,
                "complete_output": True,
            }
            observation = store.add_record(
                kind="observation",
                payload={
                    "summary": "sandboxed minigzip stdin abc",
                    "truncated": False,
                    "surfaces": {key: abc[key] for key in ("stdout_sha256", "stderr_sha256", "exit_code", "roundtrip_equals_input", "crc32_hex")},
                    "run": {"command": ["minigzip"], "exit_code": abc["exit_code"], "observed_status": "passed"},
                },
                provenance="observed",
                execution_result="passed",
                applicability="valid",
                usage="support",
                verification_scope=scope,
                source_family="zlib-1.4-minigzip-abc",
            )
            store.add_relation(
                "derived_from",
                observation,
                artifact,
                {"statement": "the observation is from this minigzip binary", "method": "explicit"},
            )
            claim = store.add_record(
                kind="claim",
                payload={
                    "statement": "zlib 1.4 minigzip on stdin abc emits the sealed gzip bytes, exits 0, round-trips, and the harness crc32 matches the sealed value, on linux-x86_64.",
                    "required_scope": scope,
                },
                provenance="observed",
                execution_result="not_executed",
                applicability="valid",
                usage="background",
                verification_scope=scope,
            )
            store.add_relation(
                "supports",
                observation,
                claim,
                {"statement": "the sandboxed run recorded those surfaces for stdin abc", "method": "explicit"},
            )
            decision = store.decision(claim)
            final_verdicts = []
            for name, data in final_inputs.items():
                again = _public(_observe(str(minigzip), str(crc_bin), data, root / "final-again" / name))
                verdict = compare_surfaces(again, sets["final"][name]["observed"])
                final_verdicts.append(
                    {
                        "name": name,
                        "verdict": verdict["compatible_on_collected_surfaces"],
                        "mismatches": verdict["mismatches"],
                        "universal": False,
                    }
                )
            store.verify_integrity()
            ledger = {
                "artifact": artifact,
                "observation": observation,
                "claim": claim,
                "accepted_pass": decision["accepted_pass"],
                "not_universal": decision["not_universal"],
                "independent_support_count": decision["independent_support_count"],
                "final_self_check_all_match": all(item["verdict"] for item in final_verdicts),
                "final_count": len(final_verdicts),
                "non_blind": True,
            }
        finally:
            store.close()
        pin["minigzip_sha256"] = digest_bytes(minigzip.read_bytes())
        pin["libz_a_sha256"] = digest_bytes(libz.read_bytes())
    # Persist pins and sealed observations. Raw final inputs are not required
    # to reproduce the verdict; their hashes and the observed surfaces are.
    (OUT_DIR / "PIN.json").write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    sealed = {"non_blind": True, "sets": sets}
    (OUT_DIR / "sealed_observations.json").write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "NON_BLIND.md").write_text(
        "\n".join(
            [
                "# Acceptance label: non-blind",
                "",
                "The same agent chose the final-acceptance inputs, ran zlib 1.4, and wrote the expected surfaces.",
                "Those expected surfaces were not used to edit minigzip. They also were not hidden from this agent.",
                "A later comparison against this file is a non-blind check.",
                "",
                f"Final input count: {len(sets['final'])}.",
                "Input bytes are identified by SHA-256 in sealed_observations.json.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    evidence = {
        "kind": "zlib-1.4-phase2",
        "synthetic": False,
        "acceptance": "non-blind",
        "pin": pin,
        "dev_abc": sets["dev"]["abc"]["observed"],
        "level_experiment": level_result,
        "shrink": shrink_record,
        "ghidra": ghidra_record,
        "ledger": ledger,
        "uncollected_surfaces": list(UNCOLLECTED_SURFACES),
        "level_9_note": "level -9 was compared with the default on tune-alpha only; the contract verdict still marks compression_level_9 as not_compared",
        "limitations": [
            "acceptance is non-blind",
            "ghidra decompilation is not the runtime claim",
            "the shrink result is not a global minimum",
            "level -9 was measured on tune-alpha only",
        ],
    }
    # compression_level_9 was collected for tune-alpha, so it is not in the uncollected list.
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "minigzip_sha256": pin["minigzip_sha256"],
        "accepted_pass": ledger["accepted_pass"],
        "final_self_check_all_match": ledger["final_self_check_all_match"],
        "ghidra_executed": ghidra_record["executed"],
        "saw_crc32": ghidra_record["saw_crc32"],
        "decompiled_crc32": ghidra_record["decompiled_crc32"],
        "level": level_result["surviving_hypothesis"],
        "shrink_len": shrink_record["reduced_length"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
