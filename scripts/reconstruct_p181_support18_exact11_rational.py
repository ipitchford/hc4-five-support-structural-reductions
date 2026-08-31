#!/usr/bin/env -S sage -python
"""Exactly reconstruct and replay the eleven p^8-complete residual columns."""

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
SELECTED_BATCH = (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 12)
SELECTED_RESIDUAL = (95, 59, 56, 1, 58, 30, 74, 112, 57, 109, 47)
EXACT = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1/integral/A_Z_b4_Z_coefficient_primitive.i64csr"
X8 = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1/X_mod_181_power_8_support18_row_major.u64le"


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
    modulus = P**8
    all_residues = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)
    residues = all_residues[:, np.asarray(SELECTED_BATCH, dtype=np.int64)]
    pairs = []
    for row in residues:
        reconstructed = [rr_base.rr(value, modulus) for value in row]
        require(all(value is not None for value in reconstructed), "selected coordinate unresolved")
        pairs.append(reconstructed)
    selected_count = len(SELECTED_BATCH)
    denominators = [math.lcm(*(pairs[row][column][1] for row in range(COLUMNS))) for column in range(selected_count)]
    numerators = [[pairs[row][column][0] * (denominators[column] // pairs[row][column][1]) for column in range(selected_count)] for row in range(COLUMNS)]
    reduction_mismatches = sum((numerators[row][column] % modulus) * pow(denominators[column] % modulus, -1, modulus) % modulus != int(residues[row, column]) for row in range(COLUMNS) for column in range(selected_count))
    require(reduction_mismatches == 0, "p8 reduction mismatch")
    offsets, indices, values, rhs = read_exact()
    exact_mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        totals = [0] * selected_count
        for position in range(int(offsets[row]), int(offsets[row + 1])):
            coefficient = int(values[position])
            vector = numerators[int(indices[position])]
            for column in range(selected_count):
                totals[column] += coefficient * vector[column]
        for column in range(selected_count):
            residual = totals[column] - denominators[column] * int(rhs[row, column])
            exact_mismatches += residual != 0
            residual_hash.update(f"{residual}\n".encode("ascii"))
    require(exact_mismatches == 0, "exact rational replay mismatch")
    pairs_path = output / "rational_exact11_pairs_row_major.json"
    integer_path = output / "primitive_exact11_common_denominator_vectors.json"
    pairs_path.write_text(json.dumps(pairs, separators=(",", ":")) + "\n", encoding="ascii")
    integer_path.write_text(json.dumps({"denominators": denominators, "integer_numerator_matrix_row_major": numerators}, separators=(",", ":")) + "\n", encoding="ascii")
    support = [sum(pairs[row][column][0] != 0 for row in range(COLUMNS)) for column in range(selected_count)]
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-support18-exact11-rational-replay.v1",
        "status": "PASS_P181_SUPPORT18_EXACT11_RATIONAL_SYSTEM_REPLAY",
        "selection": {"batch_local_columns": list(SELECTED_BATCH), "residual_local_indices": list(SELECTED_RESIDUAL)},
        "inputs": {"exact_system_sha256": digest(EXACT), "p8_residues_sha256": digest(X8)},
        "reconstruction": {"modulus": modulus, "equal_height_bound": math.isqrt((modulus - 1) // 2), "coordinate_count": COLUMNS * selected_count, "unresolved_count": 0, "support_counts": support, "global_denominators": denominators, "global_denominator_bit_lengths": [value.bit_length() for value in denominators], "maximum_absolute_numerators": [max(abs(pairs[row][column][0]) for row in range(COLUMNS)) for column in range(selected_count)], "maximum_denominators": [max(pairs[row][column][1] for row in range(COLUMNS)) for column in range(selected_count)], "p8_reduction_mismatch_count": reduction_mismatches},
        "exact_replay": {"scalar_comparisons": ROWS * selected_count, "mismatch_count": exact_mismatches, "residual_stream_sha256": residual_hash.hexdigest()},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (pairs_path, integer_path)},
        "resources": resources,
        "claim_boundary": "This PASS proves eleven rational source syzygies and raises the rational quotient lower bound with the earlier four to 15. It does not prove target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "replay.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
