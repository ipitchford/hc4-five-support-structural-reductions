#!/usr/bin/env -S sage -python
"""Recover a shared denominator by a frozen simultaneous-reconstruction LLL."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path

from sage.all import Matrix, ZZ


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
MODULUS = P**54
STABLE_DENOMINATOR = 98_703_360
DIMENSIONS = (4, 8, 12, 16, 24, 32)
SAMPLE_ROWS = 512
SYSTEM = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
P54 = CAMPAIGN / "artifacts/fourth-colon-p173-target-54digit-extension-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
X54 = P54 / "X_mod_173_power_54.json"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-54digit-extension-independent-audit.json"
STABLE_RECEIPT = CAMPAIGN / "artifacts/fourth-colon-p173-stable-denominator-recovery-v1/recovery.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconstruct(residue: int, modulus: int) -> tuple[int, int] | None:
    residue %= modulus
    if residue == 0:
        return 0, 1
    bound = math.isqrt((modulus - 1) // 2)
    old_r, remainder = modulus, residue
    old_t, coefficient = 0, 1
    while abs(remainder) > bound:
        quotient = old_r // remainder
        old_r, remainder = remainder, old_r - quotient * remainder
        old_t, coefficient = coefficient, old_t - quotient * coefficient
    numerator, denominator = remainder, coefficient
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if denominator <= 0 or abs(numerator) > bound or denominator > bound:
        return None
    if math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus:
        return None
    return numerator, denominator


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI173", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]
    cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]
    cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def centered_vector(residues: list[int], denominator: int) -> list[int]:
    half = MODULUS // 2
    output = []
    for residue in residues:
        value = denominator * residue % MODULUS
        output.append(value - MODULUS if value > half else value)
    return output


def replay_rows(
    numerators: list[int], denominator: int, row_limit: int,
    offsets: list[int], indices: list[int], values: list[int], rhs: list[int],
) -> tuple[int, int, str]:
    mismatches = 0
    maximum = 0
    residual_digest = hashlib.sha256()
    for row in range(row_limit):
        total = sum(
            values[position] * numerators[indices[position]]
            for position in range(offsets[row], offsets[row + 1])
        )
        residual = total - denominator * rhs[row]
        mismatches += residual != 0
        maximum = max(maximum, abs(residual))
        residual_digest.update(f"{residual}\n".encode("ascii"))
    return mismatches, maximum, residual_digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)

    audit = json.loads(P54_AUDIT.read_text(encoding="ascii"))
    stable = json.loads(STABLE_RECEIPT.read_text(encoding="ascii"))
    require(audit.get("status") == "PASS_INDEPENDENT_P173_FOURTH_COLON_54DIGIT_LIFT_REPLAY", "p54 audit status drift")
    require(stable.get("status") == "REJECT_P173_FOURTH_COLON_STABLE_DENOMINATOR_RECOVERY", "stable-rule status drift")
    require(int(stable["stable_set"]["denominator_lcm"]) == STABLE_DENOMINATOR, "stable denominator drift")
    residues = [int(value) for value in json.loads(X54.read_text(encoding="ascii"))]
    require(len(residues) == COLUMNS, "p54 dimension drift")
    unresolved = [index for index, residue in enumerate(residues) if reconstruct(residue, MODULUS) is None]
    require(len(unresolved) == 8_961, "unresolved index count drift")
    y = [STABLE_DENOMINATOR * residue % MODULUS for residue in residues]
    offsets, indices, values, rhs = read_integral()

    seen_denominators = set()
    candidate_records = []
    lll_records = []
    passing_denominator = None
    passing_numerators = None
    passing_full = None
    for dimension in DIMENSIONS:
        selected = unresolved[:dimension]
        basis = Matrix(ZZ, dimension + 1, dimension + 1)
        for position in range(dimension):
            basis[position, position] = MODULUS
            basis[dimension, position] = y[selected[position]]
        basis[dimension, dimension] = 1
        lll_started = time.perf_counter()
        reduced = basis.LLL()
        lll_records.append({
            "dimension": dimension,
            "selected_index_sha256": hashlib.sha256(json.dumps(selected, separators=(",", ":")).encode("ascii")).hexdigest(),
            "seconds": time.perf_counter() - lll_started,
            "basis_row_norm_square_bit_lengths": [int(sum(int(value) ** 2 for value in row)).bit_length() for row in reduced.rows()],
        })
        for row_position, row in enumerate(reduced.rows()):
            missing_factor = abs(int(row[-1]))
            if missing_factor == 0:
                continue
            denominator = STABLE_DENOMINATOR * missing_factor
            if denominator in seen_denominators:
                continue
            seen_denominators.add(denominator)
            record = {
                "dimension": dimension,
                "row_position": row_position,
                "missing_factor": str(missing_factor),
                "missing_factor_bit_length": missing_factor.bit_length(),
                "denominator": str(denominator),
                "denominator_bit_length": denominator.bit_length(),
                "divisible_by_173": denominator % P == 0,
            }
            if denominator % P == 0:
                record["sample_mismatches"] = None
                candidate_records.append(record)
                continue
            numerators = centered_vector(residues, denominator)
            sample_mismatches, sample_maximum, sample_digest = replay_rows(
                numerators, denominator, SAMPLE_ROWS, offsets, indices, values, rhs
            )
            record.update({
                "sample_mismatches": sample_mismatches,
                "sample_maximum_absolute_residual": str(sample_maximum),
                "sample_residual_stream_sha256": sample_digest,
            })
            candidate_records.append(record)
            if sample_mismatches:
                continue
            full_mismatches, full_maximum, full_digest = replay_rows(
                numerators, denominator, ROWS, offsets, indices, values, rhs
            )
            record.update({
                "full_mismatches": full_mismatches,
                "full_maximum_absolute_residual": str(full_maximum),
                "full_residual_stream_sha256": full_digest,
            })
            if full_mismatches == 0:
                passing_denominator = denominator
                passing_numerators = numerators
                passing_full = record
                break
        if passing_denominator is not None:
            break

    passed = passing_denominator is not None
    vector_record = None
    if passed:
        vector_path = output / "primitive_common_denominator_vector.json"
        vector_path.write_text(json.dumps({
            "denominator": passing_denominator,
            "integer_numerators": passing_numerators,
        }, separators=(",", ":")) + "\n", encoding="ascii")
        vector_record = {"path": vector_path.name, "sha256": digest(vector_path), "bytes": vector_path.stat().st_size}
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 1_800 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    status = (
        "PASS_P173_FOURTH_COLON_SIMULTANEOUS_LLL_EXACT_RATIONAL_RECOVERY"
        if passed else "NO_P173_FOURTH_COLON_SIMULTANEOUS_LLL_DENOMINATOR_IN_FROZEN_LADDER"
    )
    receipt = {
        "schema": "hc4.fourth-colon-p173-simultaneous-denominator-lll.v1",
        "status": status,
        "inputs": {
            "integral_system_sha256": digest(INTEGRAL),
            "x54_sha256": digest(X54),
            "p54_independent_audit_sha256": digest(P54_AUDIT),
            "stable_recovery_receipt_sha256": digest(STABLE_RECEIPT),
        },
        "registered_dimensions": list(DIMENSIONS),
        "sample_rows": SAMPLE_ROWS,
        "unresolved_coordinate_count": len(unresolved),
        "unresolved_index_stream_sha256": hashlib.sha256(json.dumps(unresolved, separators=(",", ":")).encode("ascii")).hexdigest(),
        "stable_denominator": STABLE_DENOMINATOR,
        "lll_runs": lll_records,
        "candidate_count": len(candidate_records),
        "candidates": candidate_records,
        "passing_candidate": passing_full,
        "exact_vector": vector_record,
        "resources": resources,
        "declarations": {
            "alternate_coordinate_subset_forbidden": True,
            "alternate_lattice_scaling_forbidden": True,
            "alternate_lll_parameters_forbidden": True,
            "unregistered_dimension_forbidden": True,
            "candidate_factor_or_multiple_search_forbidden": True,
            "no_new_p_adic_digit": True,
        },
        "claim_boundary": (
            "A PASS proves an exact rational solution of the frozen target system and still requires an "
            "independent source-level polynomial audit. Exhaustion rejects only this registered LLL route; "
            "neither outcome proves colon equality, saturation, nullcone containment, or HC4."
        ),
    }
    receipt_path = output / "recovery.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
