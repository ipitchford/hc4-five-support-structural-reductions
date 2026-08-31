#!/usr/bin/env python3
"""Independent certificate replay for the eleven exact p^8 syzygies."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path

import numpy as np


CAMPAIGN = Path(__file__).resolve().parents[1]
ROWS = 85_651
COLUMNS = 35_881
FULL_RHS = 18
CERT_RHS = 11
P = 181
SELECTED_BATCH = (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 12)
BASE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
CERT = CAMPAIGN / "artifacts/third-colon-p181-support18-exact11-rational-replay-v1"
EXACT = BASE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
PAIRS = CERT / "rational_exact11_pairs_row_major.json"
COMMON = CERT / "primitive_exact11_common_denominator_vectors.json"
X8 = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1/X_mod_181_power_8_support18_row_major.u64le"
SOURCE_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-two-digit-lift-independent-audit.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-exact11-rational-independent-audit.json"


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
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent exact11 audit exists")
    source = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    require(source.get("status") == "PASS_INDEPENDENT_P181_SUPPORT18_TWO_DIGIT_LIFT_REPLAY", "source audit status drift")
    require(source["exact_source_reconstruction"]["coefficient_row_mismatch_count"] == 0 and source["exact_source_reconstruction"]["rhs_row_mismatch_count"] == 0, "source audit mismatch")
    require(source["bound_hashes"]["exact_system"] == digest(EXACT), "source exact-system hash drift")
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    common = json.loads(COMMON.read_text(encoding="utf-8"))
    denominators = list(map(int, common["denominators"]))
    numerators = [[int(value) for value in row] for row in common["integer_numerator_matrix_row_major"]]
    require(len(pairs) == len(numerators) == COLUMNS and all(len(row) == CERT_RHS for row in pairs) and len(denominators) == CERT_RHS, "certificate dimensions drift")
    normalization_mismatches = 0
    encoding_mismatches = 0
    for row in range(COLUMNS):
        for column in range(CERT_RHS):
            numerator, denominator = map(int, pairs[row][column])
            normalization_mismatches += denominator <= 0 or math.gcd(abs(numerator), denominator) != 1 or denominators[column] % denominator != 0
            encoding_mismatches += numerators[row][column] != numerator * (denominators[column] // denominator)
    require(normalization_mismatches == 0 and encoding_mismatches == 0, "certificate encoding mismatch")
    modulus = P**8
    all_residues = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)
    residues = all_residues[:, np.asarray(SELECTED_BATCH, dtype=np.int64)]
    reduction_mismatches = sum(numerators[row][column] % modulus * pow(denominators[column] % modulus, -1, modulus) % modulus != int(residues[row, column]) for row in range(COLUMNS) for column in range(CERT_RHS))
    require(reduction_mismatches == 0, "p8 reduction mismatch")
    offsets, indices, values, rhs = read_exact()
    mismatches = 0
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
            mismatches += residual != 0
            residual_hash.update(f"{residual}\n".encode("ascii"))
    require(mismatches == 0, "independent exact replay mismatch")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-support18-exact11-rational-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_SUPPORT18_EXACT11_RATIONAL_SOURCE_SYZYGIES",
        "bound_hashes": {"exact_system": digest(EXACT), "pairs": digest(PAIRS), "common_denominator_vectors": digest(COMMON), "p8_residues": digest(X8), "independent_source_audit": digest(SOURCE_AUDIT)},
        "certificate_checks": {"coordinate_count": COLUMNS * CERT_RHS, "normalization_mismatch_count": normalization_mismatches, "encoding_mismatch_count": encoding_mismatches, "p8_reduction_mismatch_count": reduction_mismatches},
        "exact_replay": {"scalar_comparisons": ROWS * CERT_RHS, "mismatch_count": mismatches, "residual_stream_sha256": residual_hash.hexdigest()},
        "source_composition": {"exact_integer_system_independently_reconstructed_from_rational_source": True, "source_audit_status": source["status"]},
        "resources": resources,
        "declarations": {"solver_not_executed": True, "p_adic_lifter_not_imported_or_executed": True, "rational_replay_reimplemented": True},
        "claim_boundary": "This PASS independently certifies eleven rational residual syzygies and, with the earlier four, rational quotient lower bound 15. It does not prove target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
