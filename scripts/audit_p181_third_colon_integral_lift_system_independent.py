#!/usr/bin/env python3
"""Independent byte-level and modular audit of the integral lift system."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
PROMOTED_CSR = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
AUDITED_RHS = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-rhs-v1/target_rhs_mod181.u8"
SOLUTION = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-integral-lift-system-independent-audit.json"
P = 181


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_modular_csr(path: Path) -> tuple[list[int], list[int], bytes]:
    payload = path.read_bytes()
    require(payload[:8] == b"HC4AC181", f"modular CSR magic drift: {path}")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85_651, 35_881, 1_354_540), "modular CSR dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = payload[cursor:cursor + nonzeros]
    cursor += nonzeros
    require(cursor == len(payload), "modular CSR trailing bytes")
    return offsets, indices, values


def read_integral(path: Path) -> tuple[list[int], list[int], list[int], list[int]]:
    payload = path.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral system magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85_651, 35_881, 1_354_540), "integral dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]
    cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]
    cursor += 8 * rows
    require(cursor == len(payload), "integral system trailing bytes")
    return offsets, indices, values, rhs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    artifact = arguments.artifact_dir if arguments.artifact_dir.is_absolute() else CAMPAIGN / arguments.artifact_dir
    require(not OUTPUT.exists(), "integral audit output already exists")
    receipt_path = artifact / "integral-system.json"
    integral_path = artifact / "A_Z_b_Z_fixed_gauge.i64csr"
    modular_path = artifact / "A_Z_mod181_fixed_gauge.csr"
    scalars_path = artifact / "integral_to_promoted_row_scalars_mod181.u8"
    producer = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_SOURCE_CLEAN_P181_INTEGRAL_LIFT_SYSTEM", "producer PASS drift")
    for path in (integral_path, modular_path, scalars_path):
        record = producer["outputs"][path.name]
        require(file_hash(path) == record["sha256"] and path.stat().st_size == record["bytes"], f"producer output drift: {path.name}")

    offsets, indices, values, integer_rhs = read_integral(integral_path)
    mod_offsets, mod_indices, mod_values = read_modular_csr(modular_path)
    promoted_offsets, promoted_indices, promoted_values = read_modular_csr(PROMOTED_CSR)
    require(offsets == mod_offsets == promoted_offsets, "row offset stream mismatch")
    require(indices == mod_indices == promoted_indices, "column stream mismatch")
    require(bytes(value % P for value in values) == mod_values, "integral-to-modular coefficient reduction mismatch")
    scalars = scalars_path.read_bytes()
    audited_rhs = AUDITED_RHS.read_bytes()
    solution = SOLUTION.read_bytes()
    require(len(scalars) == len(audited_rhs) == len(integer_rhs) == 85_651, "row vector length drift")
    require(len(solution) == 35_881, "solution length drift")

    coefficient_alignment_mismatches = 0
    rhs_alignment_mismatches = 0
    solution_mismatches = 0
    ordered_row_mismatches = 0
    for row in range(85_651):
        start, stop = offsets[row], offsets[row + 1]
        if any(indices[position - 1] >= indices[position] for position in range(start + 1, stop)):
            ordered_row_mismatches += 1
        scalar = scalars[row]
        if scalar == 0:
            coefficient_alignment_mismatches += 1
        for position in range(start, stop):
            if mod_values[position] != scalar * promoted_values[position] % P:
                coefficient_alignment_mismatches += 1
        if integer_rhs[row] % P != scalar * audited_rhs[row] % P:
            rhs_alignment_mismatches += 1
        total = sum(mod_values[position] * solution[indices[position]] for position in range(start, stop)) % P
        if total != integer_rhs[row] % P:
            solution_mismatches += 1
    require(ordered_row_mismatches == 0, "integral CSR rows not strictly ordered")
    require(coefficient_alignment_mismatches == 0, "coefficient alignment mismatch")
    require(rhs_alignment_mismatches == 0, "RHS alignment mismatch")
    require(solution_mismatches == 0, "modular solution mismatch")
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-integral-lift-system-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_INTEGRAL_LIFT_SYSTEM_REPLAY",
        "bound_hashes": {
            "producer": file_hash(receipt_path),
            "integral_system": file_hash(integral_path),
            "modular_csr": file_hash(modular_path),
            "row_scalars": file_hash(scalars_path),
            "promoted_csr": file_hash(PROMOTED_CSR),
            "audited_rhs": file_hash(AUDITED_RHS),
            "audited_solution": file_hash(SOLUTION),
        },
        "checks": {
            "rows": 85_651,
            "columns": 35_881,
            "nonzeros": 1_354_540,
            "integral_modular_reduction_exact": True,
            "ordered_row_mismatches": ordered_row_mismatches,
            "coefficient_alignment_mismatches": coefficient_alignment_mismatches,
            "rhs_alignment_mismatches": rhs_alignment_mismatches,
            "solution_mismatches": solution_mismatches,
            "maximum_coefficient_bit_length": max(abs(value).bit_length() for value in values),
            "maximum_rhs_bit_length": max(abs(value).bit_length() for value in integer_rhs),
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "producer_not_imported_or_executed": True,
            "quarantined_dixon_container_not_read": True,
            "no_elimination_or_solve": True,
            "no_mod181_squared": True,
        },
        "claim_boundary": (
            "This PASS independently checks the emitted exact byte structure and every modular row alignment. "
            "It supplies no higher p-adic digit, rational identity, colon, saturation, secant closure, "
            "nullcone containment, or HC4 theorem."
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
