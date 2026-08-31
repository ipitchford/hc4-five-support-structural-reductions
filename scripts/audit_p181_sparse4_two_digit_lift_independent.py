#!/usr/bin/env -S sage -python
"""Independent exact-source and p^2 replay for the sparse-four lift."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import resource
import struct
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

import audit_j2_secant_r10_third_colon_residual_114_quotient_independent as qa


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
GLOBAL = 38_048
RHS_COUNT = 4
SELECTED_LOCAL = (43, 35, 46, 48)
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-sparse4-two-digit-lift-v2"
EXACT = ARTIFACT / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
QUOTIENT = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-sparse4-two-digit-lift-independent-audit.json"
EXPECTED = {
    "terminal": "906658091abd421c8e706a613d8a5803c400c3efd66cc4a2218a689805edd3ab",
    "exact": "94dc88f592c4a41630ae51f04fffe8f6b64d696dace5a14e49e46392d159be3e",
    "integral_receipt": "aad83c9bc76d8bd062c97434ce074bb9205e222d2c5f64409ec412b964a634b9",
    "lift_receipt": "e37eb0adcf9516e6e9ffb9bf15d190b95d538237fbd6d5e8e2ca7a77835e7770",
    "digit_zero": "51c818f61ab52abacb62deedd1abe336d99646d9b52f28384491af5694aa5e38",
    "digit_one": "0ab13cd9cd70cd424af089176d86007c224b101db47bd6fac83960e8ce941fb8",
    "x2": "afa8fe484bc8a5bbb6c97b506b5678dc7e3179e5aeb8fb105a89d37efd81711c",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def native_rss() -> int:
    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw if platform.system() == "Darwin" else raw * 1024


def reconstruct_rows(started):
    sys.path.insert(0, str(CAMPAIGN / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system
    equations, variables, _leading, _open = homogeneous_saturation_system()
    cubics = [qa.rational_terms(item, variables) for item in equations]
    h_terms, h = qa.load_quartic(CAMPAIGN / "artifacts/j2-secant-r10-first-colon-kernel-qq.json", "h_rational_terms", variables, 189, 4)
    h2_terms, h2 = qa.load_quartic(CAMPAIGN / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json", "terms", variables, 211, 3)
    terms = cubics + [h_terms, h2_terms]
    degrees = [3] * 17 + [4, 4]
    characters = []
    for records, degree in zip(terms, degrees, strict=True):
        require({sum(e) for e, _c in records} == {degree}, "degree drift")
        observed = {qa.character(e) for e, _c in records}
        require(len(observed) == 1, "character drift")
        characters.append(next(iter(observed)))
    require(qa.expression_hash(list(equations) + [h, h2]) == qa.GENERATOR_HASH, "generator hash drift")
    pools = {}
    for degree in (4, 5):
        for monomial in qa.exponent_tuples(18, degree):
            pools.setdefault((degree, qa.character(monomial)), []).append(monomial)
    descriptors, row_maps = [], {}
    for generator, (records, degree, character) in enumerate(zip(terms, degrees, characters, strict=True)):
        for multiplier in pools[(8 - degree, (3 - character) % 12)]:
            coordinate = len(descriptors)
            descriptors.append((generator, multiplier))
            for exponents, coefficient in records:
                row_maps.setdefault(qa.add_exponents(multiplier, exponents), {})[coordinate] = coefficient
        if time.perf_counter() - started >= 300 or native_rss() >= 1_500_000_000:
            raise RuntimeError("resource cap during independent row reconstruction")
    monomials = sorted(row_maps)
    rows = [row_maps[m] for m in monomials]
    require(len(descriptors) == GLOBAL and len(rows) == ROWS and sum(map(len, rows)) == 1_473_071, "coefficient profile drift")
    require(qa.canonical_hash(descriptors) == qa.DESCRIPTOR_HASH, "descriptor drift")
    return rows


def primitive(row):
    denominator = math.lcm(*(value.denominator for value in row.values()))
    result = {coordinate: value.numerator * (denominator // value.denominator) for coordinate, value in row.items()}
    content = math.gcd(*(abs(value) for value in result.values()))
    result = {coordinate: value // content for coordinate, value in result.items()}
    if result[min(result)] < 0:
        result = {coordinate: -value for coordinate, value in result.items()}
    return result


def read_exact():
    payload = EXACT.read_bytes()
    require(payload[:8] == b"HC4S4181", "exact magic drift")
    rows, columns, nonzeros, rhs_count = struct.unpack_from("<QQQQ", payload, 8)
    require((rows, columns, rhs_count) == (ROWS, COLUMNS, RHS_COUNT), "exact dimensions drift")
    cursor = 40
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy(); cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy(); cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy(); cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows * rhs_count, offset=cursor).copy().reshape(rows, rhs_count); cursor += 8 * rows * rhs_count
    require(cursor == len(payload), "exact trailing bytes")
    return offsets, indices, values, rhs


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent p2 audit exists")
    terminal = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-sparse4-two-digit-lift-terminal-v2.json"
    integral_receipt = ARTIFACT / "integral/integral-system.json"
    lift_receipt = ARTIFACT / "lift/lift.json"
    digit_zero_path = ARTIFACT / "integral/digit_00_sparse4_row_major.u8"
    digit_one_path = ARTIFACT / "lift/digit_01_sparse4_row_major.u8"
    x2_path = ARTIFACT / "lift/X_mod_181_power_2_sparse4_row_major.u16le"
    for name, path in (("terminal", terminal), ("exact", EXACT), ("integral_receipt", integral_receipt), ("lift_receipt", lift_receipt), ("digit_zero", digit_zero_path), ("digit_one", digit_one_path), ("x2", x2_path)):
        require(file_hash(path) == EXPECTED[name], f"bound hash drift: {name}")
    offsets, indices, values, rhs = read_exact()
    quotient = json.loads(QUOTIENT.read_text(encoding="utf-8"))
    complement = list(map(int, quotient["ordered_complement_absolute_coordinates"]))
    selected_absolute = [complement[index] for index in SELECTED_LOCAL]
    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    ppos = {absolute: local for local, absolute in enumerate(pivots)}
    rows = reconstruct_rows(started)
    coefficient_mismatches = rhs_mismatches = 0
    expected_nonzeros = 0
    for row_index, rational in enumerate(rows):
        integral = primitive(rational)
        selected = sorted((ppos[a], v) for a, v in integral.items() if a in ppos)
        start, stop = int(offsets[row_index]), int(offsets[row_index + 1])
        observed = [(int(indices[k]), int(values[k])) for k in range(start, stop)]
        coefficient_mismatches += observed != selected
        expected_rhs = [-integral.get(a, 0) for a in selected_absolute]
        rhs_mismatches += expected_rhs != rhs[row_index, :].astype(int).tolist()
        expected_nonzeros += len(selected)
    require(coefficient_mismatches == 0 and rhs_mismatches == 0 and expected_nonzeros == len(indices), "independent exact system reconstruction failed")

    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    x0 = np.frombuffer(digit_zero_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    x1 = np.frombuffer(digit_one_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    x2 = np.frombuffer(x2_path.read_bytes(), dtype="<u2").reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    require(np.array_equal(x2, x0 + P * x1), "independent x2 assembly failed")
    residual0 = rhs - coefficient @ x0
    require(int(np.count_nonzero(residual0 % P)) == 0, "independent digit-zero divisibility failed")
    q1 = residual0 // P
    padded_expected = np.zeros((ROWS, 114), dtype=np.uint8); padded_expected[:, :RHS_COUNT] = (q1 % P).astype(np.uint8)
    padded_saved = (ARTIFACT / "lift/correction_rhs_digit_01_padded114.u8").read_bytes()
    correction_rhs_mismatches = sum(a != b for a, b in zip(padded_expected.tobytes(order="C"), padded_saved, strict=True))
    require(correction_rhs_mismatches == 0, "independent correction RHS failed")
    numerator1 = q1 - coefficient @ x1
    digit_one_divisibility_mismatches = int(np.count_nonzero(numerator1 % P))
    require(digit_one_divisibility_mismatches == 0, "independent digit-one divisibility failed")
    q2 = numerator1 // P
    invariant_mismatches = int(np.count_nonzero(rhs - coefficient @ x2 - P**2 * q2))
    require(invariant_mismatches == 0, "independent p2 invariant failed")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_bytes": native_rss(), "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_bytes"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-sparse4-two-digit-lift-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_SPARSE4_TWO_DIGIT_LIFT_REPLAY",
        "bound_hashes": {"terminal": file_hash(terminal), "exact_system": file_hash(EXACT), "integral_receipt": file_hash(integral_receipt), "lift_receipt": file_hash(lift_receipt), "digit_zero": file_hash(digit_zero_path), "digit_one": file_hash(digit_one_path), "x2": file_hash(x2_path)},
        "exact_source_reconstruction": {"row_count": len(rows), "exact_nonzero_count": expected_nonzeros, "coefficient_row_mismatch_count": coefficient_mismatches, "rhs_row_mismatch_count": rhs_mismatches},
        "p_adic_replay": {"correction_rhs_byte_comparisons": len(padded_saved), "correction_rhs_byte_mismatch_count": correction_rhs_mismatches, "digit_one_divisibility_mismatch_count": digit_one_divisibility_mismatches, "direct_p2_invariant_mismatch_count": invariant_mismatches, "digit_zero_support": np.count_nonzero(x0, axis=0).astype(int).tolist(), "digit_one_support": np.count_nonzero(x1, axis=0).astype(int).tolist(), "two_digit_support": np.count_nonzero(x2, axis=0).astype(int).tolist()},
        "resources": resources,
        "declarations": {"builder_not_imported_or_executed": True, "lifter_not_imported_or_executed": True, "producer_not_imported_or_executed": True, "exact_primitive_rows_rebuilt": True, "no_third_digit": True},
        "claim_boundary": "This PASS independently certifies only the exact integer normalization and finite p^2 replay for four fixed canonical residual columns. It proves no QQ lift, colon, saturation, secant closure, nullcone containment, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
