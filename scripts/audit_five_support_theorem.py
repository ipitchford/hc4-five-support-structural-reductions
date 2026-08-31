#!/usr/bin/env python3
"""Audit, and optionally replay, the consolidated five-support theorem."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "receipts"
SOURCE = ROOT / "source" / "royvanrijn-jacobian-research"
PINNED_COMMIT = "3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9"

ROWS = {
    (6, 1, 1, 1, 1): (
        "scripts/certify_endpoint_radical_61111.py",
        "receipts/endpoint-radical-61111.json",
    ),
    (5, 2, 1, 1, 1): (
        "scripts/certify_endpoint_radical_52111.py",
        "receipts/endpoint-radical-52111.json",
    ),
    (4, 3, 1, 1, 1): (
        "scripts/certify_endpoint_cover_43111.py",
        "receipts/endpoint-cover-43111.json",
    ),
    (4, 2, 2, 1, 1): (
        "scripts/certify_endpoint_cover_42211.py",
        "receipts/endpoint-cover-42211.json",
    ),
    (3, 3, 2, 1, 1): (
        "scripts/certify_endpoint_radical_33211.py",
        "receipts/endpoint-radical-33211.json",
    ),
    (3, 2, 2, 2, 1): (
        "scripts/certify_endpoint_cover_32221.py",
        "receipts/endpoint-cover-32221.json",
    ),
    (2, 2, 2, 2, 2): (
        "scripts/certify_endpoint_cover_22222.py",
        "receipts/endpoint-cover-22222.json",
    ),
}

SOURCE_HASHES = {
    "HC4_DOUBLE_CONIC_NORMAL_LAYERS.md": (
        "2203c36bcb787a3d9620fa7110f6f3a48bd5e7769cc156100837aef6914d4ce1"
    ),
    "HC4_DOUBLE_CONIC_INVARIANT_SATURATION_GATE.md": (
        "519cecddf95ff1d8106d2680f88f687d5db1a39306a361dfcc728200711e9928"
    ),
    "HC4_DOUBLE_CONIC_BALANCED_FOUR_ROOT_CLOSURE.md": (
        "0e6cac3d8ae4f4bf8e049c7d43686297ff44c6017eb0aa6ba13ed2475d0fb26d"
    ),
    "scripts/verify_hc4_double_conic_normal_layers.py": (
        "48b78faeb4bd2a2700084d3314be7f3745dbd953368c4777f02b4d92cbcc0a07"
    ),
    "scripts/verify_hc4_double_conic_invariant_saturation_gate.py": (
        "03a9e5b6b0e867b54cbf3daac872d768e730f7b9290ce09ec108011f9e0e94f3"
    ),
    "scripts/verify_hc4_double_conic_balanced_four_root_closure.py": (
        "822b56fd73e75631ea5d337499315c977f5bae938bae638596e64ee9bd16ed7e"
    ),
}


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not a JSON object")
    return value


def run_command(command: list[str]) -> dict[str, object]:
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    record = {
        "command": command,
        "return_code": process.returncode,
        "wall_seconds": time.perf_counter() - started,
        "stdout_tail": process.stdout[-1000:],
        "stderr_tail": process.stderr[-1000:],
    }
    if process.returncode != 0:
        raise AssertionError(f"replay command failed: {record}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-replay", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()

    replay_runs: list[dict[str, object]] = []
    if arguments.full_replay:
        replay_runs.append(
            run_command(
                [
                    sys.executable,
                    "scripts/reconstruct_normal_layers.py",
                    "--training-samples",
                    "3",
                    "--holdout-samples",
                    "2",
                    "--seed",
                    "20260829",
                    "--output",
                    "receipts/independent-normal-layers.json",
                ]
            )
        )
        for _, (script, receipt) in ROWS.items():
            replay_runs.append(
                run_command([sys.executable, script, "--output", receipt])
            )
        replay_runs.append(
            run_command(
                [
                    sys.executable,
                    "scripts/audit_cassini_staircase_generating_function.py",
                    "--output",
                    "receipts/cassini-generating-function-audit.json",
                ]
            )
        )

    checks: dict[str, bool] = {}
    source_commit = subprocess.run(
        ["git", "-C", str(SOURCE), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    checks["source_commit_pinned"] = source_commit == PINNED_COMMIT
    source_hashes = {name: sha256(SOURCE / name) for name in SOURCE_HASHES}
    checks["source_hashes_match"] = source_hashes == SOURCE_HASHES

    normal_receipt = load_json(RECEIPTS / "independent-normal-layers.json")
    checks["normal_layers_pass"] = (
        normal_receipt.get("status") == "PASS"
        and normal_receipt.get("reference_coefficient_table_imported") is not True
        and normal_receipt.get("holdout_samples") == 2
    )
    # The import flag is nested under method in schema v1.
    method = normal_receipt.get("method")
    if isinstance(method, dict):
        checks["normal_layers_pass"] = checks["normal_layers_pass"] and (
            method.get("reference_coefficient_table_imported") is False
        )

    row_records: list[dict[str, object]] = []
    seen_partitions: set[tuple[int, ...]] = set()
    for expected_partition, (script, receipt_name) in ROWS.items():
        receipt_path = ROOT / receipt_name
        receipt = load_json(receipt_path)
        partition = tuple(int(item) for item in receipt.get("partition", []))
        seen_partitions.add(partition)
        row_records.append(
            {
                "partition": list(partition),
                "script": script,
                "script_sha256": sha256(ROOT / script),
                "receipt": receipt_name,
                "receipt_sha256": sha256(receipt_path),
                "status": receipt.get("status"),
                "equation_count": receipt.get("equation_count"),
                "wall_seconds": receipt.get("wall_seconds"),
                "conclusion": receipt.get("conclusion"),
            }
        )
        checks[f"row_{''.join(map(str, expected_partition))}_pass"] = (
            partition == expected_partition
            and receipt.get("status") == "PASS"
            and receipt.get("equation_count") == 52
        )
    checks["seven_partitions_exactly_covered"] = seen_partitions == set(ROWS)

    cassini = load_json(RECEIPTS / "cassini-generating-function-audit.json")
    checks["cassini_second_derivation_pass"] = cassini.get("status") == "PASS"
    checks["theorem_document_present"] = (ROOT / "FIVE_SUPPORT_THEOREM.md").is_file()
    checks["claim_ledger_present"] = (ROOT / "CLAIM_LEDGER.json").is_file()
    checks["boundary_lemma_present"] = (ROOT / "FIVE_SUPPORT_BOUNDARY_LEMMA.md").is_file()

    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise AssertionError(f"consolidated audit failed: {failed}")

    row_serial_seconds = sum(
        float(record["wall_seconds"])
        for record in row_records
        if isinstance(record.get("wall_seconds"), (int, float))
    )
    result = {
        "schema": "hc4-five-support-consolidated-audit-v1",
        "status": "PASS",
        "full_replay_performed": arguments.full_replay,
        "checks": checks,
        "source": {
            "commit": source_commit,
            "hashes": source_hashes,
        },
        "normal_layers_receipt_sha256": sha256(
            RECEIPTS / "independent-normal-layers.json"
        ),
        "cassini_receipt_sha256": sha256(
            RECEIPTS / "cassini-generating-function-audit.json"
        ),
        "rows": row_records,
        "metrics": {
            "row_serial_equivalent_seconds": row_serial_seconds,
            "audit_wall_seconds": time.perf_counter() - started,
            "full_replay_runs": replay_runs,
        },
        "claim_boundary": {
            "independent_exact": (
                "no clean nonzero residual-line solution whose nonzero binary-decic "
                "restriction has exactly five distinct projective roots"
            ),
            "pinned_source_dependency": (
                "the at-most-five-support corollary uses HC4NHM15 and HC4NHM18 "
                "for the support-at-most-four half"
            ),
            "open": (
                "restrictions with at least six support points, the full double-conic "
                "packet, and HC4"
            ),
        },
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output or RECEIPTS / "five-support-theorem-audit.json"
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
