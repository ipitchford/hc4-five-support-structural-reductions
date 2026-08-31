#!/usr/bin/env python3
"""Independent certificate replay for the seven exact mixed-modulus syzygies."""

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
P = 181
ROWS = 85_651
COLUMNS = 35_881
FULL_RHS = 18
CERT_RHS = 7
SELECTED_BATCH = (6, 11, 13, 14, 15, 16, 17)
SELECTED_RESIDUAL = (15, 78, 91, 104, 81, 10, 13)
P12_CERT_COLUMN = 4
EARLIER_FOUR = (43, 35, 46, 48)
EARLIER_ELEVEN = (95, 59, 56, 1, 58, 30, 74, 112, 57, 109, 47)
BASE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
CERT = CAMPAIGN / "artifacts/third-colon-p181-support7-exact-rational-replay-v1"
P8_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1"
P10_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support7-ten-digit-extension-v1"
P12_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-residual81-twelve-digit-extension-v1"
EXACT = BASE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
PAIRS = CERT / "rational_exact7_pairs_row_major.json"
COMMON = CERT / "primitive_exact7_common_denominator_vectors.json"
X8 = P8_SOURCE / "X_mod_181_power_8_support18_row_major.u64le"
D8 = P10_SOURCE / "digit_08_support7_row_major.u8"
D9 = P10_SOURCE / "digit_09_support7_row_major.u8"
D10 = P12_SOURCE / "digit_10_residual81.u8"
D11 = P12_SOURCE / "digit_11_residual81.u8"
SOURCE_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-two-digit-lift-independent-audit.json"
FOUR_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-sparse4-exact-rational-independent-audit.json"
ELEVEN_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-exact11-rational-independent-audit.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support7-exact-rational-independent-audit.json"


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
    require(not OUTPUT.exists(), "independent exact7 audit exists")
    source = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    four = json.loads(FOUR_AUDIT.read_text(encoding="utf-8"))
    eleven = json.loads(ELEVEN_AUDIT.read_text(encoding="utf-8"))
    require(source.get("status") == "PASS_INDEPENDENT_P181_SUPPORT18_TWO_DIGIT_LIFT_REPLAY", "source audit status drift")
    require(source["exact_source_reconstruction"]["coefficient_row_mismatch_count"] == 0 and source["exact_source_reconstruction"]["rhs_row_mismatch_count"] == 0, "source audit mismatch")
    require(source["bound_hashes"]["exact_system"] == digest(EXACT), "source exact-system hash drift")
    require(four.get("status") == "PASS_INDEPENDENT_P181_SPARSE4_EXACT_RATIONAL_SOURCE_SYZYGIES", "four-audit status drift")
    require(eleven.get("status") == "PASS_INDEPENDENT_P181_SUPPORT18_EXACT11_RATIONAL_SOURCE_SYZYGIES", "eleven-audit status drift")
    all_indices = EARLIER_FOUR + EARLIER_ELEVEN + SELECTED_RESIDUAL
    require(len(all_indices) == len(set(all_indices)) == 22, "aggregate residual-index independence drift")

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

    selected = np.asarray(SELECTED_BATCH, dtype=np.int64)
    x8 = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)[:, selected]
    d8 = np.frombuffer(D8.read_bytes(), dtype=np.uint8).reshape(COLUMNS, CERT_RHS)
    d9 = np.frombuffer(D9.read_bytes(), dtype=np.uint8).reshape(COLUMNS, CERT_RHS)
    d10 = np.frombuffer(D10.read_bytes(), dtype=np.uint8)
    d11 = np.frombuffer(D11.read_bytes(), dtype=np.uint8)
    require(len(d10) == len(d11) == COLUMNS, "p12 digit length drift")
    moduli = [P**12 if column == P12_CERT_COLUMN else P**10 for column in range(CERT_RHS)]
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
        "schema": "hc4.third-colon-p181-support7-exact-rational-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_SUPPORT7_EXACT_RATIONAL_SOURCE_SYZYGIES",
        "bound_hashes": {"exact_system": digest(EXACT), "pairs": digest(PAIRS), "common_denominator_vectors": digest(COMMON), "p8_residues": digest(X8), "digit8": digest(D8), "digit9": digest(D9), "digit10": digest(D10), "digit11": digest(D11), "independent_source_audit": digest(SOURCE_AUDIT), "earlier_four_audit": digest(FOUR_AUDIT), "earlier_eleven_audit": digest(ELEVEN_AUDIT)},
        "certificate_checks": {"coordinate_count": COLUMNS * CERT_RHS, "normalization_mismatch_count": normalization_mismatches, "encoding_mismatch_count": encoding_mismatches, "mixed_modulus_reduction_mismatch_count": reduction_mismatches},
        "exact_replay": {"scalar_comparisons": ROWS * CERT_RHS, "mismatch_count": mismatches, "residual_stream_sha256": residual_hash.hexdigest()},
        "aggregate_quotient_lower_bound": {"earlier_four_indices": list(EARLIER_FOUR), "earlier_eleven_indices": list(EARLIER_ELEVEN), "new_seven_indices": list(SELECTED_RESIDUAL), "distinct_index_count": len(set(all_indices)), "lower_bound": 22, "upper_bound": 114},
        "source_composition": {"exact_integer_system_independently_reconstructed_from_rational_source": True, "source_audit_status": source["status"]},
        "resources": resources,
        "declarations": {"solver_not_executed": True, "p_adic_lifter_not_imported_or_executed": True, "producer_not_imported_or_executed": True, "rational_replay_reimplemented": True, "target_not_read": True},
        "claim_boundary": "This PASS independently certifies seven rational residual syzygies and, with the earlier audited fifteen, rational quotient lower bound 22. It does not prove target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
