#!/usr/bin/env -S sage -python
"""Build the exact fixed-gauge p173 lifting system for the fourth target."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from array import array
from fractions import Fraction
from pathlib import Path

import sympy as sp

from audit_j2_secant_r10_fourth_colon_identity_preflight import load_fourth_quartic
from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import load_second_quartic
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import canonical_hash, load_third_quartic
from certify_j2_secant_r10_z12_macaulay import CHARACTER_MODULUS, character_weight, exact_exponent_tuples
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
GLOBAL_COLUMNS = 38_826
LOCAL_COLUMNS = 36_587
MODULAR_CERTIFICATE = CAMPAIGN / "artifacts/j2-secant-r10-fourth-colon-identity-sparse-macaulay-hybrid-p173.json"
MODULAR_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-identity-p173-independent-replay.json"
H3_QQ_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-exact-polynomial-identity-audit.json"
EXPECTED_HASHES = {
    "generator": "688352a1e62824bdc4300d58e37bc681414d2755cee9da021cd47257d0832378",
    "target": "1d38a51f026483c3dc28ee80652bfc1c9d66f856903374c8a2e6c7392a6f262d",
    "descriptor": "478302e341969ae2d8edec433bfd7fc12374598502b7f4e661884b31c4bd5f67",
    "monomial": "ae88030860e7dc4de0ddf446c2b66a97285c4d98d42c6388c783c1c029b66446",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rational_pair(value: object) -> tuple[int, int]:
    rational = sp.Rational(value)
    return int(rational.p), int(rational.q)


def add_pairs(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    value = Fraction(*left) + Fraction(*right)
    return value.numerator, value.denominator


def primitive_row(entries: list[tuple[int, tuple[int, int]]], rhs: tuple[int, int]) -> tuple[list[tuple[int, int]], int]:
    denominator = rhs[1]
    for _column, pair in entries:
        denominator = math.lcm(denominator, pair[1])
    integer_entries = [(column, pair[0] * (denominator // pair[1])) for column, pair in entries]
    integer_rhs = rhs[0] * (denominator // rhs[1])
    content_values = [abs(value) for _column, value in integer_entries if value]
    if integer_rhs:
        content_values.append(abs(integer_rhs))
    if not content_values:
        return [], 0
    content = math.gcd(*content_values)
    integer_entries = [(column, value // content) for column, value in integer_entries if value]
    integer_rhs //= content
    first = integer_entries[0][1] if integer_entries else integer_rhs
    if first < 0:
        integer_entries = [(column, -value) for column, value in integer_entries]
        integer_rhs = -integer_rhs
    return integer_entries, integer_rhs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    modular_audit = json.loads(MODULAR_AUDIT.read_text(encoding="ascii"))
    h3_audit = json.loads(H3_QQ_AUDIT.read_text(encoding="ascii"))
    require(modular_audit.get("status") == "PASS_INDEPENDENT_EXACT_MODULAR_FOURTH_COLON_IDENTITY_REPLAY", "modular audit status drift")
    require(h3_audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_EXACT_POLYNOMIAL_IDENTITY", "h3 QQ audit status drift")
    certificate = json.loads(MODULAR_CERTIFICATE.read_text(encoding="ascii"))
    require(certificate.get("characteristic") == P, "source prime drift")
    pivots = [int(value) for value in certificate["pivot_unknown_indices"]]
    vector = [int(value) for value in certificate["coordinate_vector"]]
    require(len(pivots) == LOCAL_COLUMNS and len(vector) == GLOBAL_COLUMNS and len(set(pivots)) == LOCAL_COLUMNS, "gauge dimensions drift")
    global_to_local = {global_coordinate: local for local, global_coordinate in enumerate(pivots)}
    local_solution = [vector[global_coordinate] for global_coordinate in pivots]

    equations, variables, _leading, open_factor = homogeneous_saturation_system()
    first, first_metadata = reconstruct_quartic(CAMPAIGN, variables)
    second, second_metadata = load_second_quartic(CAMPAIGN, variables)
    third, third_metadata = load_third_quartic(CAMPAIGN, variables)
    fourth, fourth_metadata = load_fourth_quartic(CAMPAIGN, variables)
    generators = list(equations) + [first, second, third]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * fourth)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    term_tables = []
    generator_weights = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [(tuple(map(int, exponents)), rational_pair(coefficient)) for exponents, coefficient in polynomial.terms()]
        require({sum(exponents) for exponents, _pair in terms} == {expected_degree}, "generator degree drift")
        weights = {character_weight(exponents) for exponents, _pair in terms}
        require(len(weights) == 1, "generator character drift")
        term_tables.append(terms)
        generator_weights.append(next(iter(weights)))
    target_terms = [(tuple(map(int, exponents)), rational_pair(coefficient)) for exponents, coefficient in target_polynomial.terms()]
    require(generator_weights[-3:] == [4, 3, 2] and {character_weight(exponents) for exponents, _pair in target_terms} == {2}, "character ladder drift")
    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    rows_by_monomial: dict[tuple[int, ...], dict[int, tuple[int, int]]] = {}
    descriptors = []
    for generator_index, (terms, weight, degree) in enumerate(zip(term_tables, generator_weights, multiplier_degrees, strict=True)):
        multiplier_weight = (2 - weight) % CHARACTER_MODULUS
        for multiplier in pools.get((degree, multiplier_weight), []):
            coordinate = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(left + right for left, right in zip(exponents, multiplier, strict=True))
                row = rows_by_monomial.setdefault(product, {})
                row[coordinate] = add_pairs(row[coordinate], pair) if coordinate in row else pair
                if row[coordinate][0] == 0:
                    del row[coordinate]
    target_map = dict(target_terms)
    for monomial in target_map:
        rows_by_monomial.setdefault(monomial, {})
    monomials = sorted(rows_by_monomial)
    observed_hashes = {"generator": digest(tuple(generators)), "target": digest((target_expression,)), "descriptor": canonical_hash(descriptors), "monomial": canonical_hash(monomials)}
    require(observed_hashes == EXPECTED_HASHES, f"fourth block hash drift: {observed_hashes}")
    require(len(descriptors) == GLOBAL_COLUMNS and len(monomials) == ROWS, "fourth block dimensions drift")

    offsets = array("Q", [0])
    columns = array("I")
    values = array("q")
    rhs_values = array("q")
    replay_mismatches = 0
    maximum_coefficient_bits = maximum_rhs_bits = 0
    empty_zero_rows = 0
    for monomial in monomials:
        row = rows_by_monomial[monomial]
        selected = sorted((global_to_local[global_coordinate], pair) for global_coordinate, pair in row.items() if global_coordinate in global_to_local)
        integer_entries, integer_rhs = primitive_row(selected, target_map.get(monomial, (0, 1)))
        empty_zero_rows += not integer_entries and integer_rhs == 0
        total = sum(value * local_solution[local] for local, value in integer_entries) % P
        replay_mismatches += total != integer_rhs % P
        for local, value in integer_entries:
            require(-(1 << 63) <= value < (1 << 63), "coefficient exceeds int64")
            columns.append(local); values.append(value)
            maximum_coefficient_bits = max(maximum_coefficient_bits, abs(value).bit_length())
        require(-(1 << 63) <= integer_rhs < (1 << 63), "RHS exceeds int64")
        rhs_values.append(integer_rhs)
        maximum_rhs_bits = max(maximum_rhs_bits, abs(integer_rhs).bit_length())
        offsets.append(len(columns))
    require(replay_mismatches == 0, "frozen modular solution failed exact selected rows")
    integral_path = output / "A_Z_b_Z_fixed_gauge_p173.i64csr"
    modular_path = output / "A_Z_mod173_fixed_gauge.csr"
    solution_path = output / "solution_mod173.u8"
    with integral_path.open("xb") as handle:
        handle.write(b"HC4ZI173"); handle.write(struct.pack("<QQQ", ROWS, LOCAL_COLUMNS, len(columns))); handle.write(offsets.tobytes()); handle.write(columns.tobytes()); handle.write(values.tobytes()); handle.write(rhs_values.tobytes())
    with modular_path.open("xb") as handle:
        handle.write(b"HC4AC173"); handle.write(struct.pack("<QQQ", ROWS, LOCAL_COLUMNS, len(columns))); handle.write(offsets.tobytes()); handle.write(columns.tobytes()); handle.write(bytes(value % P for value in values))
    solution_path.write_bytes(bytes(value % P for value in local_solution))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.fourth-colon-p173-fixed-gauge-integral-lift-system.v1",
        "status": "PASS_FOURTH_COLON_P173_FIXED_GAUGE_INTEGRAL_LIFT_SYSTEM",
        "dimensions": {"rows": ROWS, "global_columns": GLOBAL_COLUMNS, "selected_columns": LOCAL_COLUMNS, "selected_nonzeros": len(columns), "empty_zero_rows": empty_zero_rows},
        "checks": {"modular_solution_mismatches": replay_mismatches, "maximum_coefficient_bit_length": maximum_coefficient_bits, "maximum_rhs_bit_length": maximum_rhs_bits, "algebra_hashes": observed_hashes},
        "inputs": {"modular_certificate": file_hash(MODULAR_CERTIFICATE), "modular_independent_audit": file_hash(MODULAR_AUDIT), "h3_qq_polynomial_audit": file_hash(H3_QQ_AUDIT)},
        "quartics": {"first": first_metadata, "second": second_metadata, "third": third_metadata, "fourth": fourth_metadata},
        "outputs": {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size} for path in (integral_path, modular_path, solution_path)},
        "resources": resources,
        "declarations": {"no_elimination_or_solve": True, "no_mod173_squared": True, "h3_predecessor_identity_independently_proved": True},
        "claim_boundary": "This PASS constructs an exact fixed-gauge p173 lifting interface for M*h4. It adds no p-adic digit and proves no rational fourth identity, colon equality, saturation, secant closure, or HC4 theorem."
    }
    receipt_path = output / "integral-system.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path), "dimensions": receipt["dimensions"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
