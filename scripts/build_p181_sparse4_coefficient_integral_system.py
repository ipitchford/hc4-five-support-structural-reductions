#!/usr/bin/env -S sage -python
"""Build the exact coefficient-only integral system for four sparse sections."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from array import array
from pathlib import Path

import numpy as np

import audit_p181_canonical_residual_114_section_independent as source_audit


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
RHS_COUNT = 4
SELECTED_LOCAL = (43, 35, 46, 48)
EXPECTED_SUPPORT = (136, 194, 194, 194)
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
PROMOTED_CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
QUOTIENT = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
SECTION = CAMPAIGN / "artifacts/third-colon-p181-canonical-residual-114-section-v1"
INDEPENDENT_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-canonical-residual-114-section-independent-audit.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def primitive_row(row):
    denominator = math.lcm(*(value.denominator for value in row.values()))
    integral = {
        coordinate: value.numerator * (denominator // value.denominator)
        for coordinate, value in row.items()
    }
    content = math.gcd(*(abs(value) for value in integral.values()))
    integral = {coordinate: value // content for coordinate, value in integral.items()}
    first = min(integral)
    if integral[first] < 0:
        integral = {coordinate: -value for coordinate, value in integral.items()}
    require(math.gcd(*(abs(value) for value in integral.values())) == 1, "nonprimitive coefficient row")
    return integral


def read_promoted_csr():
    payload = PROMOTED_CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "promoted CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, 1_354_540), "promoted CSR dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy()
    cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy()
    cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype=np.uint8, count=nonzeros, offset=cursor).copy()
    cursor += nonzeros
    require(cursor == len(payload), "promoted CSR trailing bytes")
    return offsets, indices, values


def write_exact(path, offsets, indices, values, rhs):
    with path.open("xb") as handle:
        handle.write(b"HC4S4181")
        handle.write(struct.pack("<QQQQ", ROWS, COLUMNS, len(indices), RHS_COUNT))
        handle.write(offsets.tobytes())
        handle.write(indices.tobytes())
        handle.write(values.tobytes())
        handle.write(rhs.tobytes())


def write_modular(path, offsets, indices, values):
    with path.open("xb") as handle:
        handle.write(b"HC4AC181")
        handle.write(struct.pack("<QQQ", ROWS, COLUMNS, len(indices)))
        handle.write(offsets.tobytes())
        handle.write(indices.tobytes())
        handle.write(bytes(values))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)

    audit = json.loads(INDEPENDENT_AUDIT.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION", "independent audit PASS drift")
    support = audit["section_normalization"]["column_support_counts"]
    require(tuple(support[index] for index in SELECTED_LOCAL) == EXPECTED_SUPPORT, "sparse-four support selection drift")
    quotient = json.loads(QUOTIENT.read_text(encoding="utf-8"))
    complement = list(map(int, quotient["ordered_complement_absolute_coordinates"]))
    selected_absolute = tuple(complement[index] for index in SELECTED_LOCAL)

    gauge_payload = GAUGE.read_bytes()
    require(len(gauge_payload) == 4 * COLUMNS, "gauge length drift")
    pivots = [item[0] for item in struct.iter_unpack("<I", gauge_payload)]
    require(len(set(pivots)) == COLUMNS, "gauge duplicate")
    pivot_position = {absolute: local for local, absolute in enumerate(pivots)}
    promoted_offsets, promoted_indices, promoted_values = read_promoted_csr()

    pivot114_payload = (SECTION / "pivot_section_row_major.u8").read_bytes()
    require(len(pivot114_payload) == COLUMNS * 114, "promoted pivot section length drift")
    pivot114 = np.frombuffer(pivot114_payload, dtype=np.uint8).reshape(COLUMNS, 114)
    digit_zero = pivot114[:, np.asarray(SELECTED_LOCAL, dtype=np.int64)].copy()
    digit_zero_support = np.count_nonzero(digit_zero, axis=0).astype(int).tolist()
    require(tuple(value + 1 for value in digit_zero_support) == EXPECTED_SUPPORT, "digit-zero support drift")

    rational_rows, descriptors, monomials = source_audit.reconstruct_coefficient_rows(started)
    exact_offsets = array("Q", [0])
    exact_indices = array("I")
    exact_values = array("q")
    modular_offsets = array("Q", [0])
    modular_indices = array("I")
    modular_values = bytearray()
    rhs = array("q")
    alignment_mismatches = 0
    digit_zero_mismatches = 0
    exact_p_divisible_entries = 0
    maximum_coefficient_bits = 0
    maximum_rhs_bits = 0
    rhs_nonzeros = [0] * RHS_COUNT

    for row_index, rational in enumerate(rational_rows):
        integral = primitive_row(rational)
        selected = sorted(
            (pivot_position[absolute], value)
            for absolute, value in integral.items()
            if absolute in pivot_position
        )
        require(selected, f"empty selected row {row_index}")
        observed = {
            int(promoted_indices[position]): int(promoted_values[position])
            for position in range(int(promoted_offsets[row_index]), int(promoted_offsets[row_index + 1]))
        }
        modular_selected = [(local, value % P) for local, value in selected if value % P]
        require({local for local, _value in modular_selected} == set(observed), f"modular support drift at row {row_index}")
        anchor_local, anchor_value = modular_selected[0]
        scale = observed[anchor_local] * pow(anchor_value, -1, P) % P
        alignment_mismatches += sum(observed[local] != scale * value % P for local, value in modular_selected)

        for local, value in selected:
            require(-(1 << 63) <= value < (1 << 63), "exact coefficient exceeds int64")
            exact_indices.append(local)
            exact_values.append(value)
            maximum_coefficient_bits = max(maximum_coefficient_bits, abs(value).bit_length())
            exact_p_divisible_entries += value % P == 0
            if value % P:
                modular_indices.append(local)
                modular_values.append(value % P)
        exact_offsets.append(len(exact_indices))
        modular_offsets.append(len(modular_indices))

        row_rhs = [-integral.get(absolute, 0) for absolute in selected_absolute]
        for column, value in enumerate(row_rhs):
            require(-(1 << 63) <= value < (1 << 63), "exact sparse-four RHS exceeds int64")
            rhs.append(value)
            rhs_nonzeros[column] += value != 0
            maximum_rhs_bits = max(maximum_rhs_bits, abs(value).bit_length())
        for column in range(RHS_COUNT):
            total = sum((value % P) * int(digit_zero[local, column]) for local, value in selected) % P
            digit_zero_mismatches += total != row_rhs[column] % P
        if row_index % 4096 == 0:
            source_audit.guard(started, "sparse-four integral system build")

    require(alignment_mismatches == 0, "promoted coefficient alignment failed")
    require(digit_zero_mismatches == 0, "digit-zero integral replay failed")
    require(len(modular_indices) == 1_354_540, "modular nonzero count drift")
    exact_path = output / "A_Z_b4_Z_coefficient_primitive.i64csr"
    modular_path = output / "A_mod181_coefficient_primitive.csr"
    digit_zero_path = output / "digit_00_sparse4_row_major.u8"
    write_exact(exact_path, exact_offsets, exact_indices, exact_values, rhs)
    write_modular(modular_path, modular_offsets, modular_indices, modular_values)
    digit_zero_path.write_bytes(digit_zero.tobytes(order="C"))
    receipt = {
        "schema": "hc4.third-colon-p181-sparse4-coefficient-integral-system.v1",
        "status": "PASS_P181_SPARSE4_COEFFICIENT_PRIMITIVE_INTEGRAL_SYSTEM",
        "selection": {"residual_local_indices": list(SELECTED_LOCAL), "residual_absolute_coordinates": list(selected_absolute), "full_support_counts": list(EXPECTED_SUPPORT), "digit_zero_pivot_support_counts": digit_zero_support},
        "dimensions": {"rows": ROWS, "columns": COLUMNS, "rhs_count": RHS_COUNT, "exact_nonzeros": len(exact_indices), "modular_nonzeros": len(modular_indices)},
        "checks": {"coefficient_alignment_mismatches": alignment_mismatches, "digit_zero_mismatches": digit_zero_mismatches, "exact_coefficients_divisible_by_181": exact_p_divisible_entries, "rhs_nonzero_counts": rhs_nonzeros, "maximum_coefficient_bit_length": maximum_coefficient_bits, "maximum_rhs_bit_length": maximum_rhs_bits},
        "algebra_hashes": {"descriptor_sha256": source_audit.canonical_hash(descriptors), "monomial_sha256": source_audit.canonical_hash(monomials)},
        "outputs": {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size} for path in (exact_path, modular_path, digit_zero_path)},
        "bound_inputs": {str(path.relative_to(CAMPAIGN)): file_hash(path) for path in (GAUGE, PROMOTED_CSR, QUOTIENT, SECTION / "pivot_section_row_major.u8", INDEPENDENT_AUDIT)},
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"coefficient_only_primitive_row_normalization": True, "old_target_rhs_not_read": True, "old_target_solution_not_read": True, "third_quartic_not_read": True, "no_higher_digit": True},
        "claim_boundary": "This PASS constructs the exact coefficient-only primitive integer system and four digit-zero modular solutions. It supplies no p^2 lift, QQ identity, colon, saturation, secant closure, nullcone containment, or HC4 theorem.",
    }
    receipt_path = output / "integral-system.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
