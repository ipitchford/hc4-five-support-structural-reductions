#!/usr/bin/env sage-python
"""Independently replay a sparse Macaulay colon-identity certificate.

The producer uses custom sparse Gaussian elimination on coefficient equations.
This verifier does not import that implementation.  It reconstructs multiplier
polynomials from the frozen sparse support and asks SymPy's finite-field
polynomial arithmetic whether their combination of the seventeen cubics equals
``M*h`` coefficientwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polynomial_mod(expression, variables, characteristic: int) -> sp.Poly:
    """Map a rational polynomial coefficientwise into a prime field."""

    rational_polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    terms = {}
    for exponents, coefficient in rational_polynomial.terms():
        rational = sp.Rational(coefficient)
        denominator = int(rational.q) % characteristic
        if denominator == 0:
            raise ZeroDivisionError(
                f"coefficient denominator is zero modulo {characteristic}"
            )
        terms[tuple(map(int, exponents))] = (
            (int(rational.p) % characteristic)
            * pow(denominator, -1, characteristic)
            % characteristic
        )
    return sp.Poly.from_dict(terms, variables, modulus=characteristic)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "certificate",
        type=Path,
        nargs="?",
        default=Path("artifacts/j2-secant-r10-colon-identity-sparse-macaulay-p103.json"),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    certificate_path = arguments.certificate
    if not certificate_path.is_absolute():
        certificate_path = campaign / certificate_path
    certificate_sha256 = sha256_file(certificate_path)
    certificate = json.loads(certificate_path.read_text(encoding="ascii"))
    if certificate.get("schema") != (
        "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2"
    ):
        raise ValueError("unsupported certificate schema")
    characteristic = int(certificate["characteristic"])
    if characteristic <= 5 or not sp.isprime(characteristic):
        raise ValueError("certificate characteristic is not an admissible prime")

    equations, variables, _, open_factor = homogeneous_saturation_system()
    quartic, reconstruction = reconstruct_quartic(campaign, variables)
    target_expression = sp.expand(open_factor * quartic)
    variable_names_match = certificate["variable_names"] == [
        str(variable) for variable in variables
    ]
    generator_hash_match = certificate["normal_equation_stream_sha256"] == digest(
        tuple(equations)
    )
    target_hash_match = certificate["target_sha256"] == digest((target_expression,))
    grading_match = (
        certificate["character_modulus"] == CHARACTER_MODULUS
        and certificate["character_weights"] == list(CHARACTER_WEIGHTS)
        and certificate["target_character_weight"] == 5
    )

    multiplier_terms: list[dict[tuple[int, ...], int]] = [
        {} for _ in equations
    ]
    support_well_formed = True
    duplicate_count = 0
    wrong_degree_count = 0
    wrong_character_count = 0
    generator_polynomials = [
        polynomial_mod(equation, variables, characteristic) for equation in equations
    ]
    generator_weights = []
    for polynomial in generator_polynomials:
        weights = {
            character_weight(tuple(map(int, exponents)))
            for exponents, _ in polynomial.terms()
        }
        if len(weights) != 1:
            raise AssertionError("replayed generator is not character homogeneous")
        generator_weights.append(next(iter(weights)))

    for record in certificate["solution_support"]:
        generator_index = int(record["normal_generator_position"])
        exponents = tuple(map(int, record["multiplier_exponents"]))
        coefficient = int(record["coefficient"]) % characteristic
        if not (0 <= generator_index < len(equations)) or len(exponents) != len(variables):
            support_well_formed = False
            continue
        if sum(exponents) != 5:
            wrong_degree_count += 1
        expected_weight = (5 - generator_weights[generator_index]) % CHARACTER_MODULUS
        if character_weight(exponents) != expected_weight:
            wrong_character_count += 1
        if exponents in multiplier_terms[generator_index]:
            duplicate_count += 1
        if not coefficient:
            support_well_formed = False
        multiplier_terms[generator_index][exponents] = coefficient

    support_well_formed = support_well_formed and not (
        duplicate_count or wrong_degree_count or wrong_character_count
    )
    pivot_unknown_indices = list(map(int, certificate["pivot_unknown_indices"]))
    free_unknown_indices = list(map(int, certificate["free_unknown_indices"]))
    pivot_profile_hash_match = certificate["pivot_unknown_indices_sha256"] == hashlib.sha256(
        json.dumps(pivot_unknown_indices, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    free_profile_hash_match = certificate["free_unknown_indices_sha256"] == hashlib.sha256(
        json.dumps(free_unknown_indices, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    gauge_partition_valid = (
        len(set(pivot_unknown_indices)) == len(pivot_unknown_indices)
        and free_unknown_indices == sorted(set(free_unknown_indices))
        and set(pivot_unknown_indices).isdisjoint(free_unknown_indices)
        and set(pivot_unknown_indices) | set(free_unknown_indices)
        == set(range(len(pivot_unknown_indices) + len(free_unknown_indices)))
        and all(
            not certificate_record["coefficient"]
            for certificate_record in certificate["solution_support"]
            if int(certificate_record["unknown_index"]) in set(free_unknown_indices)
        )
    )
    pivot_coordinate_vector = certificate.get("pivot_coordinate_vector")
    pivot_coordinate_vector_hash_match = (
        pivot_coordinate_vector is None
        and certificate.get("pivot_coordinate_vector_sha256") is None
    ) or (
        pivot_coordinate_vector is not None
        and certificate.get("pivot_coordinate_vector_sha256")
        == hashlib.sha256(
            json.dumps(pivot_coordinate_vector, separators=(",", ":")).encode("ascii")
        ).hexdigest()
    )
    gauge_source_file_match = True
    pivot_coordinate_vector_matches_support = True
    if certificate.get("gauge_source") is not None:
        gauge_source = certificate["gauge_source"]
        gauge_source_path = Path(gauge_source["path"])
        gauge_source_file_match = (
            gauge_source_path.is_file()
            and sha256_file(gauge_source_path) == gauge_source["sha256"]
        )
        if gauge_source_file_match:
            gauge_payload = json.loads(gauge_source_path.read_text(encoding="ascii"))
            source_pivots = list(map(int, gauge_payload["pivot_unknown_indices"]))
            support_by_unknown = {
                int(record["unknown_index"]): int(record["coefficient"]) % characteristic
                for record in certificate["solution_support"]
            }
            pivot_coordinate_vector_matches_support = (
                pivot_coordinate_vector
                == [support_by_unknown.get(index, 0) for index in source_pivots]
            )
        else:
            pivot_coordinate_vector_matches_support = False
    multipliers = [
        sp.Poly.from_dict(terms, variables, modulus=characteristic)
        for terms in multiplier_terms
    ]
    reconstructed = sp.Poly(0, *variables, modulus=characteristic)
    for multiplier, generator in zip(multipliers, generator_polynomials, strict=True):
        reconstructed += multiplier * generator
    target = polynomial_mod(target_expression, variables, characteristic)
    remainder = target - reconstructed
    identity_zero = remainder.is_zero

    passed = all(
        (
            variable_names_match,
            generator_hash_match,
            target_hash_match,
            grading_match,
            support_well_formed,
            pivot_profile_hash_match,
            free_profile_hash_match,
            gauge_partition_valid,
            pivot_coordinate_vector_hash_match,
            gauge_source_file_match,
            pivot_coordinate_vector_matches_support,
            identity_zero,
        )
    )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-replay.v1",
        "status": (
            "PASS_INDEPENDENT_SYMPY_MODULAR_COLON_IDENTITY_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_SYMPY_MODULAR_COLON_IDENTITY_REPLAY"
        ),
        "assurance": "independent exact finite-field polynomial replay",
        "characteristic": characteristic,
        "certificate": {
            "path": str(certificate_path),
            "sha256": certificate_sha256,
            "solution_support_count": len(certificate["solution_support"]),
        },
        "checks": {
            "variable_names_match": variable_names_match,
            "normal_equation_stream_sha256_match": generator_hash_match,
            "target_sha256_match": target_hash_match,
            "grading_metadata_match": grading_match,
            "support_well_formed": support_well_formed,
            "pivot_profile_sha256_match": pivot_profile_hash_match,
            "free_profile_sha256_match": free_profile_hash_match,
            "gauge_partition_valid": gauge_partition_valid,
            "pivot_coordinate_vector_sha256_match": pivot_coordinate_vector_hash_match,
            "gauge_source_file_sha256_match": gauge_source_file_match,
            "pivot_coordinate_vector_matches_support": pivot_coordinate_vector_matches_support,
            "duplicate_support_records": duplicate_count,
            "wrong_multiplier_degree_records": wrong_degree_count,
            "wrong_multiplier_character_records": wrong_character_count,
            "identity_zero": identity_zero,
            "remainder_term_count": 0 if identity_zero else len(remainder.terms()),
            "nonzero_multiplier_count": sum(not multiplier.is_zero for multiplier in multipliers),
            "multiplier_term_count": sum(
                len(multiplier.terms()) for multiplier in multipliers if not multiplier.is_zero
            ),
            "maximum_multiplier_total_degree": max(
                multiplier.total_degree() for multiplier in multipliers if not multiplier.is_zero
            ),
        },
        "quartic_reconstruction": reconstruction,
        "wall_seconds": time.perf_counter() - started,
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "source_sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
        "claim_boundary": (
            "This replay independently proves the displayed M*h identity only over "
            "the displayed finite field. It does not lift it to QQ, determine the full "
            "colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-colon-identity-sparse-macaulay-replay-p{characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
