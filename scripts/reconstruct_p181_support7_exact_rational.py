#!/usr/bin/env -S sage -python
"""Reconstruct and exactly replay the seven completed residual columns."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path

import numpy as np

import reconstruct_p181_sparse4_exact_rational as rr_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
FULL_RHS = 18
CERT_RHS = 7
SELECTED_BATCH = (6, 11, 13, 14, 15, 16, 17)
SELECTED_RESIDUAL = (15, 78, 91, 104, 81, 10, 13)
P12_CERT_COLUMN = 4
BASE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
P8_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1"
P10_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support7-ten-digit-extension-v1"
P12_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-residual81-twelve-digit-extension-v1"
EXACT = BASE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
X8 = P8_SOURCE / "X_mod_181_power_8_support18_row_major.u64le"
D8 = P10_SOURCE / "digit_08_support7_row_major.u8"
D9 = P10_SOURCE / "digit_09_support7_row_major.u8"
D10 = P12_SOURCE / "digit_10_residual81.u8"
D11 = P12_SOURCE / "digit_11_residual81.u8"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_exact():
    payload = EXACT.read_bytes()
    require(payload[:8] == b"HC4S4181", "exact magic drift")
    rows, columns, nonzeros, rhs_count = struct.unpack_from("<QQQQ", payload, 8)
    require((rows, columns, rhs_count) == (ROWS, COLUMNS, FULL_RHS), "exact dimensions drift")
    cursor = 40
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy(); cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy(); cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy(); cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows * rhs_count, offset=cursor).copy().reshape(rows, rhs_count); cursor += 8 * rows * rhs_count
    require(cursor == len(payload), "exact trailing bytes")
    return offsets, indices, values, rhs[:, np.asarray(SELECTED_BATCH, dtype=np.int64)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    selected = np.asarray(SELECTED_BATCH, dtype=np.int64)
    x8 = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)[:, selected]
    d8 = np.frombuffer(D8.read_bytes(), dtype=np.uint8).reshape(COLUMNS, CERT_RHS)
    d9 = np.frombuffer(D9.read_bytes(), dtype=np.uint8).reshape(COLUMNS, CERT_RHS)
    d10 = np.frombuffer(D10.read_bytes(), dtype=np.uint8)
    d11 = np.frombuffer(D11.read_bytes(), dtype=np.uint8)
    require(len(d10) == len(d11) == COLUMNS, "p12 digit length drift")
    moduli = [P**12 if column == P12_CERT_COLUMN else P**10 for column in range(CERT_RHS)]
    pairs = []
    for row in range(COLUMNS):
        reconstructed = []
        for column in range(CERT_RHS):
            residue = int(x8[row, column]) + (P**8) * int(d8[row, column]) + (P**9) * int(d9[row, column])
            if column == P12_CERT_COLUMN:
                residue += (P**10) * int(d10[row]) + (P**11) * int(d11[row])
            reconstructed.append(rr_base.rr(residue, moduli[column]))
        require(all(value is not None for value in reconstructed), "selected coordinate unresolved")
        pairs.append(reconstructed)

    denominators = [math.lcm(*(pairs[row][column][1] for row in range(COLUMNS))) for column in range(CERT_RHS)]
    numerators = [[pairs[row][column][0] * (denominators[column] // pairs[row][column][1]) for column in range(CERT_RHS)] for row in range(COLUMNS)]
    reduction_mismatches = 0
    for row in range(COLUMNS):
        for column in range(CERT_RHS):
            modulus = moduli[column]
            saved = int(x8[row, column]) + (P**8) * int(d8[row, column]) + (P**9) * int(d9[row, column])
            if column == P12_CERT_COLUMN:
                saved += (P**10) * int(d10[row]) + (P**11) * int(d11[row])
            encoded = numerators[row][column] % modulus * pow(denominators[column] % modulus, -1, modulus) % modulus
            reduction_mismatches += encoded != saved
    require(reduction_mismatches == 0, "mixed-modulus reduction mismatch")

    offsets, indices, values, rhs = read_exact()
    exact_mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        totals = [0] * CERT_RHS
        for position in range(int(offsets[row]), int(offsets[row + 1])):
            coefficient = int(values[position])
            vector = numerators[int(indices[position])]
            for column in range(CERT_RHS):
                totals[column] += coefficient * vector[column]
        for column in range(CERT_RHS):
            residual = totals[column] - denominators[column] * int(rhs[row, column])
            exact_mismatches += residual != 0
            residual_hash.update(f"{residual}\n".encode("ascii"))
    require(exact_mismatches == 0, "exact rational replay mismatch")

    pairs_path = output / "rational_exact7_pairs_row_major.json"
    integer_path = output / "primitive_exact7_common_denominator_vectors.json"
    pairs_path.write_text(json.dumps(pairs, separators=(",", ":")) + "\n", encoding="ascii")
    integer_path.write_text(json.dumps({"denominators": denominators, "integer_numerator_matrix_row_major": numerators}, separators=(",", ":")) + "\n", encoding="ascii")
    support = [sum(pairs[row][column][0] != 0 for row in range(COLUMNS)) for column in range(CERT_RHS)]
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-support7-exact-rational-replay.v1",
        "status": "PASS_P181_SUPPORT7_EXACT_RATIONAL_SYSTEM_REPLAY",
        "selection": {"support18_batch_local_columns": list(SELECTED_BATCH), "residual_local_indices": list(SELECTED_RESIDUAL), "p12_certificate_column": P12_CERT_COLUMN},
        "inputs": {"exact_system_sha256": digest(EXACT), "p8_residues_sha256": digest(X8), "digit8_support7_sha256": digest(D8), "digit9_support7_sha256": digest(D9), "digit10_residual81_sha256": digest(D10), "digit11_residual81_sha256": digest(D11)},
        "reconstruction": {"moduli_by_column": moduli, "equal_height_bounds_by_column": [math.isqrt((modulus - 1) // 2) for modulus in moduli], "coordinate_count": COLUMNS * CERT_RHS, "unresolved_count": 0, "support_counts": support, "global_denominators": denominators, "global_denominator_bit_lengths": [value.bit_length() for value in denominators], "maximum_absolute_numerators": [max(abs(pairs[row][column][0]) for row in range(COLUMNS)) for column in range(CERT_RHS)], "maximum_denominators": [max(pairs[row][column][1] for row in range(COLUMNS)) for column in range(CERT_RHS)], "mixed_modulus_reduction_mismatch_count": reduction_mismatches},
        "exact_replay": {"scalar_comparisons": ROWS * CERT_RHS, "mismatch_count": exact_mismatches, "residual_stream_sha256": residual_hash.hexdigest()},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (pairs_path, integer_path)},
        "resources": resources,
        "declarations": {"solver_not_executed": True, "p_adic_correction_not_executed": True, "target_not_read": True},
        "claim_boundary": "This PASS proves seven rational residual syzygies and raises the rational quotient lower bound with the earlier fifteen to 22. It does not prove target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "replay.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
