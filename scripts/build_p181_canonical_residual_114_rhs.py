#!/usr/bin/env -S sage -python
"""Build the target-free canonical residual-114 RHS matrix modulo 181."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import load_second_quartic
from certify_j2_secant_r10_z12_macaulay import CHARACTER_MODULUS, character_weight, exact_exponent_tuples
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
PIVOT_COLUMNS = 35_881
GLOBAL_COLUMNS = 38_048
QUOTIENT_COLUMNS = 114
CSR_NONZEROS = 1_354_540
CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
QUOTIENT = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
PREREGISTRATION = CAMPAIGN / "research/THIRD_COLON_P181_CANONICAL_RESIDUAL_114_SECTION_PREREGISTRATION.md"
EXPECTED = {
    "csr": "eb419a8348852cb784f308ebd32eef682c731bafe77533e3b37ff5241b2228cc",
    "gauge": "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2",
    "quotient": "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74",
    "preregistration": "b7466845d9c441196f32600aff2546f8ee3ba2bca823583b67526adbff9b15b7",
    "descriptors": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomials": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generators": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rational_pair(value: object) -> tuple[int, int]:
    rational = sp.Rational(value)
    return int(rational.p), int(rational.q)


def coefficient_only_block():
    equations, variables, _leading_form, _open_factor = homogeneous_saturation_system()
    first_quartic, _first_metadata = reconstruct_quartic(CAMPAIGN, variables)
    second_quartic, _second_metadata = load_second_quartic(CAMPAIGN, variables)
    generators = list(equations) + [first_quartic, second_quartic]
    degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - degree for degree in degrees]
    terms = []
    weights = []
    for generator, degree in zip(generators, degrees):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        records = [(tuple(map(int, exponents)), rational_pair(coefficient)) for exponents, coefficient in polynomial.terms()]
        require({sum(exponents) for exponents, _coefficient in records} == {degree}, "generator degree drift")
        observed_weights = {character_weight(exponents) for exponents, _coefficient in records}
        require(len(observed_weights) == 1, "generator character drift")
        terms.append(records)
        weights.append(next(iter(observed_weights)))
    require(weights[-2:] == [4, 3], "adjoined generator character drift")
    pools = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    descriptors = []
    rows = {}
    target_weight = 3
    for generator_index, (records, weight, multiplier_degree) in enumerate(zip(terms, weights, multiplier_degrees)):
        multiplier_weight = (target_weight - weight) % CHARACTER_MODULUS
        for multiplier in pools.get((multiplier_degree, multiplier_weight), []):
            unknown = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in records:
                monomial = tuple(left + right for left, right in zip(exponents, multiplier))
                require(sum(monomial) == 8 and character_weight(monomial) == target_weight, "coefficient left block")
                row = rows.setdefault(monomial, {})
                require(unknown not in row, "within-column coefficient collision")
                row[unknown] = pair
    monomials = sorted(rows)
    ordered_rows = [rows[monomial] for monomial in monomials]
    require(len(descriptors) == GLOBAL_COLUMNS, "descriptor count drift")
    require(len(ordered_rows) == ROWS, "coefficient-only row count drift")
    require(sum(map(len, ordered_rows)) == 1_473_071, "coefficient-only support drift")
    require(canonical_hash(descriptors) == EXPECTED["descriptors"], "descriptor hash drift")
    require(canonical_hash(monomials) == EXPECTED["monomials"], "monomial hash drift")
    require(digest(tuple(generators)) == EXPECTED["generators"], "generator hash drift")
    return ordered_rows, descriptors, monomials


def read_csr():
    payload = CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, PIVOT_COLUMNS, CSR_NONZEROS), "CSR dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = list(payload[cursor:cursor + nonzeros])
    cursor += nonzeros
    require(cursor == len(payload), "CSR trailing bytes")
    return offsets, indices, values


def mod_pair(pair: tuple[int, int]) -> int:
    numerator, denominator = pair
    require(denominator % P != 0, "coefficient denominator nonunit at p181")
    return numerator % P * pow(denominator % P, -1, P) % P


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    for name, path in (("csr", CSR), ("gauge", GAUGE), ("quotient", QUOTIENT), ("preregistration", PREREGISTRATION)):
        require(file_hash(path) == EXPECTED[name], f"{name} hash drift")
    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    require(len(pivots) == PIVOT_COLUMNS and len(set(pivots)) == PIVOT_COLUMNS, "main pivot gauge drift")
    quotient = json.loads(QUOTIENT.read_text(encoding="utf-8"))
    selected = list(map(int, quotient["ordered_complement_absolute_coordinates"]))
    require(len(selected) == QUOTIENT_COLUMNS and len(set(selected)) == QUOTIENT_COLUMNS, "quotient complement drift")
    require(not set(selected).intersection(pivots), "quotient complement intersects main pivots")
    selected_position = {absolute: local for local, absolute in enumerate(selected)}
    pivot_position = {absolute: local for local, absolute in enumerate(pivots)}
    rows, descriptors, monomials = coefficient_only_block()
    offsets, indices, observed_values = read_csr()
    rhs = bytearray(ROWS * QUOTIENT_COLUMNS)
    normalization_mismatches = 0
    rhs_nonzeros = 0
    column_nonzeros = [0] * QUOTIENT_COLUMNS
    scale_histogram = {}
    for row_index, row in enumerate(rows):
        observed = {indices[position]: observed_values[position] for position in range(offsets[row_index], offsets[row_index + 1])}
        raw_pivots = []
        for absolute, pair in row.items():
            local = pivot_position.get(absolute)
            if local is not None:
                raw_value = mod_pair(pair)
                if raw_value:
                    raw_pivots.append((local, raw_value))
        require(raw_pivots and len(raw_pivots) == len(observed), f"pivot support drift at row {row_index}")
        first_local, first_raw = raw_pivots[0]
        require(first_raw != 0 and first_local in observed, f"zero normalization anchor at row {row_index}")
        scale = observed[first_local] * pow(first_raw, -1, P) % P
        require(scale != 0, f"zero row scale at row {row_index}")
        scale_histogram[str(scale)] = scale_histogram.get(str(scale), 0) + 1
        for local, raw_value in raw_pivots:
            normalization_mismatches += int(observed.get(local) != scale * raw_value % P)
        for absolute, pair in row.items():
            local = selected_position.get(absolute)
            if local is None:
                continue
            value = (-scale * mod_pair(pair)) % P
            if value:
                rhs[row_index * QUOTIENT_COLUMNS + local] = value
                rhs_nonzeros += 1
                column_nonzeros[local] += 1
    require(normalization_mismatches == 0, "source-clean row normalization replay failed")
    rhs_path = output / "minus_A_S_row_major.u8"
    rhs_path.write_bytes(rhs)
    receipt = {
        "schema": "hc4.third-colon-p181-canonical-residual-114-rhs.v1",
        "status": "PASS_SOURCE_CLEAN_P181_CANONICAL_RESIDUAL_114_RHS",
        "inputs": {"csr_sha256": file_hash(CSR), "gauge_sha256": file_hash(GAUGE), "quotient_chart_sha256": file_hash(QUOTIENT), "preregistration_sha256": file_hash(PREREGISTRATION)},
        "dimensions": {"rows": ROWS, "main_pivot_columns": PIVOT_COLUMNS, "quotient_rhs_columns": QUOTIENT_COLUMNS, "coefficient_only_global_columns": len(descriptors)},
        "algebra_hashes": {"descriptor_sha256": canonical_hash(descriptors), "monomial_sha256": canonical_hash(monomials), "ordered_S_absolute_sha256": canonical_hash(selected)},
        "normalization": {"pivot_scalar_comparisons": CSR_NONZEROS, "mismatch_count": normalization_mismatches, "nonzero_scale_histogram": scale_histogram},
        "rhs": {"path": rhs_path.name, "sha256": file_hash(rhs_path), "bytes": len(rhs), "nonzero_count": rhs_nonzeros, "column_nonzero_counts": column_nonzeros},
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"coefficient_only_builder": True, "third_quartic_not_imported_or_loaded": True, "target_rhs_not_read": True, "target_solution_not_read": True, "legacy_residual_kernel_not_read": True, "no_elimination": True},
        "claim_boundary": "This PASS constructs only the canonical 114-column coefficient RHS over GF(181). It does not solve it, construct kernel vectors over QQ, prove target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "rhs.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
