#!/usr/bin/env -S sage -python
"""Build a fresh exact integral system aligned with the audited p181 identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import sys
import time
from array import array
from pathlib import Path

from preprocess_fixed_p181_dixon_integer_system import (
    build_rational_block,
    primitive_integer_row,
)


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
PROMOTED_CSR = CAMPAIGN / (
    "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/"
    "A_C_mod181_target_free.csr"
)
PROMOTED_CSR_SHA256 = "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
GAUGE_SHA256 = "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2"
AUDITED_RHS = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-rhs-v1/target_rhs_mod181.u8"
AUDITED_RHS_SHA256 = "72d15610c6630a4d1929029476cb9b01d8494bc502b9b68457674795dcd1c76f"
MODULAR_SOLUTION = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
MODULAR_SOLUTION_SHA256 = "5c37ce8fda3829baeef36f58002589e289bdd552939f61216b3ce257af456e58"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_promoted_csr() -> tuple[list[int], list[int], bytes]:
    payload = PROMOTED_CSR.read_bytes()
    require(file_hash(PROMOTED_CSR) == PROMOTED_CSR_SHA256, "promoted CSR drift")
    require(payload[:8] == b"HC4AC181", "promoted CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85_651, 35_881, 1_354_540), "promoted CSR dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = payload[cursor:cursor + nonzeros]
    cursor += nonzeros
    require(cursor == len(payload), "promoted CSR trailing bytes")
    return offsets, indices, values


def write_integral_system(
    path: Path,
    offsets: array,
    columns: array,
    values: array,
    rhs: array,
) -> None:
    with path.open("xb") as handle:
        handle.write(b"HC4ZI181")
        handle.write(struct.pack("<QQQ", 85_651, 35_881, 1_354_540))
        handle.write(offsets.tobytes())
        handle.write(columns.tobytes())
        handle.write(values.tobytes())
        handle.write(rhs.tobytes())


def write_modular_csr(path: Path, offsets: array, columns: array, values: array) -> None:
    residues = bytes(value % P for value in values)
    with path.open("xb") as handle:
        handle.write(b"HC4AC181")
        handle.write(struct.pack("<QQQ", 85_651, 35_881, 1_354_540))
        handle.write(offsets.tobytes())
        handle.write(columns.tobytes())
        handle.write(residues)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    require(file_hash(GAUGE) == GAUGE_SHA256, "pivot gauge drift")
    require(file_hash(AUDITED_RHS) == AUDITED_RHS_SHA256, "audited RHS drift")
    require(file_hash(MODULAR_SOLUTION) == MODULAR_SOLUTION_SHA256, "audited modular solution drift")
    promoted_offsets, promoted_columns, promoted_values = read_promoted_csr()
    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    require(len(pivots) == 35_881 and len(set(pivots)) == len(pivots), "pivot gauge dimensions drift")
    global_to_local = {global_column: local for local, global_column in enumerate(pivots)}
    audited_rhs = AUDITED_RHS.read_bytes()
    solution = MODULAR_SOLUTION.read_bytes()
    require(len(audited_rhs) == 85_651 and len(solution) == 35_881, "modular input dimensions drift")

    block = build_rational_block(CAMPAIGN)
    require(len(block["rows"]) == 85_651, "rational row count drift")
    offsets = array("Q", [0])
    columns = array("I")
    values = array("q")
    rhs = array("q")
    row_scalars = bytearray()
    modular_solution_mismatches = 0
    coefficient_alignment_mismatches = 0
    rhs_alignment_mismatches = 0
    maximum_coefficient_bits = 0
    maximum_rhs_bits = 0
    for row_index, (row, target) in enumerate(zip(block["rows"], block["rhs"], strict=True)):
        integer_entries, integer_rhs = primitive_integer_row(row, target, block["coefficient_values"])
        selected = sorted(
            (global_to_local[global_column], value)
            for global_column, value in integer_entries
            if global_column in global_to_local
        )
        require(selected, "integral selected row is empty")
        require(len(selected) == promoted_offsets[row_index + 1] - promoted_offsets[row_index], "selected row support length drift")
        promoted_row = {
            promoted_columns[position]: promoted_values[position]
            for position in range(promoted_offsets[row_index], promoted_offsets[row_index + 1])
        }
        require(set(promoted_row) == {local for local, _value in selected}, "selected row support mismatch")
        first_local, first_value = selected[0]
        require(first_value % P != 0, "integral selected coefficient vanished modulo 181")
        scalar = (first_value % P) * pow(promoted_row[first_local], -1, P) % P
        require(scalar != 0, "zero integral/promoted row scalar")
        row_scalars.append(scalar)
        if any(value % P != scalar * promoted_row[local] % P for local, value in selected):
            coefficient_alignment_mismatches += 1
        if integer_rhs % P != scalar * audited_rhs[row_index] % P:
            rhs_alignment_mismatches += 1
        total = sum((value % P) * solution[local] for local, value in selected) % P
        if total != integer_rhs % P:
            modular_solution_mismatches += 1
        for local, value in selected:
            require(-(1 << 63) <= value < (1 << 63), "integral coefficient exceeds int64")
            columns.append(local)
            values.append(value)
            maximum_coefficient_bits = max(maximum_coefficient_bits, abs(value).bit_length())
        require(-(1 << 63) <= integer_rhs < (1 << 63), "integral RHS exceeds int64")
        rhs.append(integer_rhs)
        maximum_rhs_bits = max(maximum_rhs_bits, abs(integer_rhs).bit_length())
        offsets.append(len(columns))

    require(len(columns) == 1_354_540, "integral selected nonzero count drift")
    require(coefficient_alignment_mismatches == 0, "integral coefficient alignment failed")
    require(rhs_alignment_mismatches == 0, "integral RHS alignment failed")
    require(modular_solution_mismatches == 0, "audited modular solution failed integral rows")
    integral_path = output / "A_Z_b_Z_fixed_gauge.i64csr"
    modular_path = output / "A_Z_mod181_fixed_gauge.csr"
    scalars_path = output / "integral_to_promoted_row_scalars_mod181.u8"
    write_integral_system(integral_path, offsets, columns, values, rhs)
    write_modular_csr(modular_path, offsets, columns, values)
    scalars_path.write_bytes(row_scalars)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-source-clean-integral-lift-system.v1",
        "status": "PASS_SOURCE_CLEAN_P181_INTEGRAL_LIFT_SYSTEM",
        "dimensions": {"rows": 85_651, "columns": 35_881, "nonzeros": len(columns)},
        "checks": {
            "coefficient_alignment_mismatches": coefficient_alignment_mismatches,
            "rhs_alignment_mismatches": rhs_alignment_mismatches,
            "modular_solution_mismatches": modular_solution_mismatches,
            "row_scalar_nonzeros": sum(value != 0 for value in row_scalars),
            "maximum_coefficient_bit_length": maximum_coefficient_bits,
            "maximum_rhs_bit_length": maximum_rhs_bits,
        },
        "outputs": {
            path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
            for path in (integral_path, modular_path, scalars_path)
        },
        "bound_inputs": {
            str(PROMOTED_CSR.relative_to(CAMPAIGN)): PROMOTED_CSR_SHA256,
            str(GAUGE.relative_to(CAMPAIGN)): GAUGE_SHA256,
            str(AUDITED_RHS.relative_to(CAMPAIGN)): AUDITED_RHS_SHA256,
            str(MODULAR_SOLUTION.relative_to(CAMPAIGN)): MODULAR_SOLUTION_SHA256,
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(CAMPAIGN)),
            "sha256": file_hash(Path(__file__).resolve()),
            "python": sys.version,
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "quarantined_dixon_container_not_read": True,
            "prior_coordinate_vector_not_read": True,
            "audited_new_modular_solution_used_only_for_replay": True,
            "no_elimination_or_solve": True,
            "no_mod181_squared": True,
        },
        "claim_boundary": (
            "This PASS constructs an exact integral lifting system and binds its reduction to the audited "
            "modular identity. It supplies no higher p-adic digit, rational identity, colon, saturation, "
            "secant closure, nullcone containment, or HC4 theorem."
        ),
    }
    receipt_path = output / "integral-system.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
