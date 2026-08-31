#!/usr/bin/env -S sage -python
"""Independently replay the fourth-colon target as a QQ polynomial identity."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import time
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
ROWS = 85_688
GLOBAL_COLUMNS = 38_826
LOCAL_COLUMNS = 36_587
EXPECTED_HASHES = {
    "generator": "688352a1e62824bdc4300d58e37bc681414d2755cee9da021cd47257d0832378",
    "target": "1d38a51f026483c3dc28ee80652bfc1c9d66f856903374c8a2e6c7392a6f262d",
    "descriptor": "478302e341969ae2d8edec433bfd7fc12374598502b7f4e661884b31c4bd5f67",
    "monomial": "ae88030860e7dc4de0ddf446c2b66a97285c4d98d42c6388c783c1c029b66446",
}
CERTIFICATE_DIR = CAMPAIGN / "artifacts/fourth-colon-p173-target-exact-rational-replay-v1"
CERTIFICATE = CERTIFICATE_DIR / "primitive_common_denominator_vector.json"
CERTIFICATE_RECEIPT = CERTIFICATE_DIR / "replay.json"
MODULAR_CERTIFICATE = CAMPAIGN / "artifacts/j2-secant-r10-fourth-colon-identity-sparse-macaulay-hybrid-p173.json"
MODULAR_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-identity-p173-independent-replay.json"
H3_QQ_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-exact-polynomial-identity-audit.json"
OUTPUT_DIR = CAMPAIGN / "artifacts/fourth-colon-p173-target-exact-polynomial-identity-audit-v1"
OUTPUT_RECEIPT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-target-exact-polynomial-identity-audit.json"


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


def reconstruct_problem() -> dict[str, object]:
    equations, variables, _leading_form, open_factor = homogeneous_saturation_system()
    first, first_metadata = reconstruct_quartic(CAMPAIGN, variables)
    second, second_metadata = load_second_quartic(CAMPAIGN, variables)
    third, third_metadata = load_third_quartic(CAMPAIGN, variables)
    fourth, fourth_metadata = load_fourth_quartic(CAMPAIGN, variables)
    generators = list(equations) + [first, second, third]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * fourth)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)

    term_tables: list[list[tuple[tuple[int, ...], tuple[int, int]]]] = []
    generator_weights: list[int] = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), rational_pair(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        require({sum(exponents) for exponents, _pair in terms} == {expected_degree}, "generator degree drift")
        weights = {character_weight(exponents) for exponents, _pair in terms}
        require(len(weights) == 1, "generator character drift")
        term_tables.append(terms)
        generator_weights.append(next(iter(weights)))
    require(len(generators) == 20 and generator_weights[-3:] == [4, 3, 2], "generator profile drift")

    target_terms = [
        (tuple(map(int, exponents)), rational_pair(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    require({character_weight(exponents) for exponents, _pair in target_terms} == {2}, "target character drift")
    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)

    rows_by_monomial: dict[tuple[int, ...], dict[int, tuple[int, int]]] = {}
    descriptors: list[tuple[int, tuple[int, ...]]] = []
    contribution_count = 0
    for generator_index, (terms, weight, degree) in enumerate(
        zip(term_tables, generator_weights, multiplier_degrees, strict=True)
    ):
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
                contribution_count += 1
    target_map = dict(target_terms)
    for monomial in target_map:
        rows_by_monomial.setdefault(monomial, {})
    monomials = sorted(rows_by_monomial)
    observed_hashes = {
        "generator": digest(tuple(generators)),
        "target": digest((target_expression,)),
        "descriptor": canonical_hash(descriptors),
        "monomial": canonical_hash(monomials),
    }
    require(observed_hashes == EXPECTED_HASHES, "independent algebra hash drift")
    require(len(descriptors) == GLOBAL_COLUMNS and len(monomials) == ROWS, "Macaulay profile drift")
    return {
        "descriptors": descriptors,
        "monomials": monomials,
        "rows": rows_by_monomial,
        "target": target_map,
        "hashes": observed_hashes,
        "source_metadata": {
            "first": first_metadata,
            "second": second_metadata,
            "third": third_metadata,
            "fourth": fourth_metadata,
        },
        "contribution_count": contribution_count,
        "target_term_count": len(target_terms),
    }


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT_DIR.exists() and not OUTPUT_RECEIPT.exists(), "polynomial audit output already exists")
    exact_receipt = json.loads(CERTIFICATE_RECEIPT.read_text(encoding="ascii"))
    modular_audit = json.loads(MODULAR_AUDIT.read_text(encoding="ascii"))
    h3_audit = json.loads(H3_QQ_AUDIT.read_text(encoding="ascii"))
    require(exact_receipt.get("status") == "PASS_P173_FOURTH_COLON_TARGET_EXACT_RATIONAL_SYSTEM_REPLAY", "exact certificate status drift")
    require(exact_receipt["outputs"][CERTIFICATE.name]["sha256"] == file_hash(CERTIFICATE), "exact certificate hash drift")
    require(modular_audit.get("status") == "PASS_INDEPENDENT_EXACT_MODULAR_FOURTH_COLON_IDENTITY_REPLAY", "modular audit status drift")
    require(h3_audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_EXACT_POLYNOMIAL_IDENTITY", "h3 QQ audit status drift")

    certificate = json.loads(CERTIFICATE.read_text(encoding="ascii"))
    denominator = int(certificate["denominator"])
    numerators = [int(value) for value in certificate["integer_numerators"]]
    modular = json.loads(MODULAR_CERTIFICATE.read_text(encoding="ascii"))
    pivots = [int(value) for value in modular["pivot_unknown_indices"]]
    require(len(numerators) == len(pivots) == LOCAL_COLUMNS, "gauge length drift")
    require(len(set(pivots)) == LOCAL_COLUMNS and max(pivots) < GLOBAL_COLUMNS, "gauge profile drift")
    local_by_global = {global_coordinate: local for local, global_coordinate in enumerate(pivots)}

    problem = reconstruct_problem()
    residual_digest = hashlib.sha256()
    mismatches = 0
    maximum_absolute_residual = 0
    selected_contributions = 0
    for monomial in problem["monomials"]:
        row = problem["rows"][monomial]
        rhs_numerator, rhs_denominator = problem["target"].get(monomial, (0, 1))
        selected = [
            (local_by_global[global_coordinate], pair)
            for global_coordinate, pair in row.items()
            if global_coordinate in local_by_global
        ]
        row_denominator = rhs_denominator
        for _local, (_coefficient_numerator, coefficient_denominator) in selected:
            row_denominator = math.lcm(row_denominator, coefficient_denominator)
        total = sum(
            numerators[local] * coefficient_numerator * (row_denominator // coefficient_denominator)
            for local, (coefficient_numerator, coefficient_denominator) in selected
        )
        expected = denominator * rhs_numerator * (row_denominator // rhs_denominator)
        residual = total - expected
        mismatches += residual != 0
        maximum_absolute_residual = max(maximum_absolute_residual, abs(residual))
        selected_contributions += len(selected)
        residual_digest.update(f"{residual}\n".encode("ascii"))
    require(mismatches == 0, "exact polynomial coefficient replay mismatch")

    support_records = []
    support_by_generator = [0] * 20
    for local, numerator in enumerate(numerators):
        if numerator == 0:
            continue
        global_coordinate = pivots[local]
        generator_index, exponents = problem["descriptors"][global_coordinate]
        support_by_generator[generator_index] += 1
        support_records.append({
            "local_coordinate": local,
            "global_coordinate": global_coordinate,
            "generator_index": generator_index,
            "multiplier_exponents": list(exponents),
            "integer_numerator": numerator,
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    semantic_path = OUTPUT_DIR / "sparse_semantic_multipliers.json"
    semantic_path.write_text(json.dumps({
        "common_denominator": denominator,
        "support_by_generator": support_by_generator,
        "records": support_records,
    }, separators=(",", ":")) + "\n", encoding="ascii")
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "polynomial audit resource gate failed")
    receipt = {
        "schema": "hc4.fourth-colon-p173-target-exact-polynomial-identity-audit.v1",
        "status": "PASS_INDEPENDENT_P173_FOURTH_COLON_TARGET_EXACT_POLYNOMIAL_IDENTITY",
        "bound_hashes": {
            "common_denominator_vector": file_hash(CERTIFICATE),
            "exact_rational_receipt": file_hash(CERTIFICATE_RECEIPT),
            "modular_certificate": file_hash(MODULAR_CERTIFICATE),
            "modular_independent_audit": file_hash(MODULAR_AUDIT),
            "h3_qq_polynomial_audit": file_hash(H3_QQ_AUDIT),
        },
        "algebra": {
            "generator_count": 20,
            "global_multiplier_coordinates": GLOBAL_COLUMNS,
            "selected_multiplier_coordinates": LOCAL_COLUMNS,
            "fixed_zero_coordinates": GLOBAL_COLUMNS - LOCAL_COLUMNS,
            "degree_eight_rows": ROWS,
            "target_term_count": problem["target_term_count"],
            "raw_contribution_count": problem["contribution_count"],
            "selected_contribution_count": selected_contributions,
            "hashes": problem["hashes"],
            "source_metadata": problem["source_metadata"],
        },
        "certificate": {
            "common_denominator": denominator,
            "common_denominator_bit_length": denominator.bit_length(),
            "support_count": len(support_records),
            "support_by_generator": support_by_generator,
        },
        "exact_polynomial_replay": {
            "coefficient_comparisons": ROWS,
            "mismatch_count": mismatches,
            "maximum_absolute_residual": maximum_absolute_residual,
            "residual_stream_sha256": residual_digest.hexdigest(),
        },
        "outputs": {semantic_path.name: {"sha256": file_hash(semantic_path), "bytes": semantic_path.stat().st_size}},
        "resources": resources,
        "declarations": {
            "integral_target_system_not_read": True,
            "integral_system_builder_not_imported": True,
            "solver_not_executed": True,
            "p_adic_lifter_not_imported_or_executed": True,
            "polynomial_block_reconstructed_directly_over_QQ": True,
        },
        "claim_boundary": (
            "This PASS independently proves the displayed fourth-colon target polynomial identity over QQ for "
            "the frozen chart and hence h4 membership in (I,h,h2,h3):M. It does not prove colon equality, "
            "saturation, global secant closure, nullcone containment, or HC4."
        ),
    }
    receipt_path = OUTPUT_DIR / "audit.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    OUTPUT_RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT_RECEIPT), "sha256": file_hash(OUTPUT_RECEIPT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
