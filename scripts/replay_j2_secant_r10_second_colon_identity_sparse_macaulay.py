#!/usr/bin/env sage-python
"""Independently replay a second-colon sparse Macaulay certificate.

This verifier does not import the second-colon producer or its eliminator.  It
reconstructs the frozen rational quartics, rebuilds the mixed-degree multiplier
coordinate stream, validates the complete modular coordinate vector, and checks
the polynomial identity coefficientwise with SymPy over the displayed field.
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
    exact_exponent_tuples,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-second-colon-identity-"
    "sparse-macaulay-certificate.v1"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def residue(coefficient: sp.Rational, characteristic: int) -> int:
    """Independently map one exact rational coefficient to the prime field."""

    coefficient = sp.Rational(coefficient)
    denominator = int(coefficient.q) % characteristic
    if denominator == 0:
        raise ZeroDivisionError("coefficient denominator vanishes in the replay field")
    return int(coefficient.p) % characteristic * pow(
        denominator, -1, characteristic
    ) % characteristic


def load_second_quartic(campaign: Path, variables) -> tuple[sp.Expr, dict[str, object]]:
    path = campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_schema = (
        "hc4.decimic-j2-secant-r10-second-colon-kernel-qq-candidate.v1"
    )
    if payload.get("schema") != expected_schema:
        raise ValueError("unsupported second-colon candidate schema")
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError("second-colon candidate variable stream changed")
    expression = sp.Integer(0)
    seen = set()
    for record in payload.get("terms", []):
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != len(variables) or exponents in seen:
            raise ValueError("malformed or duplicate second-colon term")
        seen.add(exponents)
        coefficient = sp.Rational(
            int(record["numerator"]), int(record["denominator"])
        )
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += coefficient * monomial
    expression = sp.expand(expression)
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    if (
        polynomial.total_degree() != 4
        or len(polynomial.terms()) != int(payload.get("term_count", -1))
        or {
            character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in polynomial.terms()
        }
        != {3}
    ):
        raise ValueError("second-colon candidate profile changed")
    return expression, {"path": str(path), "sha256": sha256_file(path)}


def polynomial_mod(expression, variables, characteristic: int) -> sp.Poly:
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    terms = {}
    for exponents, coefficient in polynomial.terms():
        coefficient_residue = residue(coefficient, characteristic)
        if coefficient_residue:
            terms[tuple(map(int, exponents))] = coefficient_residue
    return sp.Poly.from_dict(
        terms,
        variables,
        modulus=characteristic,
    )


def canonical_problem(campaign: Path):
    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    generators = list(equations) + [first_quartic]
    generator_degrees = [3] * len(equations) + [4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    generator_weights = []
    for generator, degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        weights = {
            character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in polynomial.terms()
        }
        degrees = {
            sum(map(int, exponents)) for exponents, _coefficient in polynomial.terms()
        }
        if len(weights) != 1 or degrees != {degree}:
            raise ValueError("generator grading changed")
        generator_weights.append(next(iter(weights)))
    target = sp.expand(open_factor * second_quartic)
    target_polynomial = sp.Poly(target, *variables, domain=sp.QQ)
    if (
        target_polynomial.total_degree() != 8
        or {
            character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in target_polynomial.terms()
        }
        != {4}
    ):
        raise ValueError("target grading changed")

    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (weight, degree) in enumerate(
        zip(generator_weights, multiplier_degrees, strict=True)
    ):
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(degree, (4 - weight) % CHARACTER_MODULUS)]
        )
    if len(descriptors) != 37476:
        raise AssertionError("the canonical 37,476-coordinate stream changed")

    monomial_set = set()
    for (generator_index, multiplier) in descriptors:
        for generator_exponents, _coefficient in sp.Poly(
            generators[generator_index], *variables, domain=sp.QQ
        ).terms():
            monomial_set.add(
                tuple(
                    int(left) + right
                    for left, right in zip(
                        generator_exponents, multiplier, strict=True
                    )
                )
            )
    monomial_set.update(
        tuple(map(int, exponents)) for exponents, _coefficient in target_polynomial.terms()
    )
    return {
        "equations": equations,
        "variables": variables,
        "generators": generators,
        "generator_degrees": generator_degrees,
        "multiplier_degrees": multiplier_degrees,
        "generator_weights": generator_weights,
        "target": target,
        "descriptors": descriptors,
        "monomials": sorted(monomial_set),
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("certificate", type=Path)
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
    if certificate.get("schema") != CERTIFICATE_SCHEMA:
        raise ValueError("unsupported certificate schema")
    characteristic = int(certificate["characteristic"])
    if characteristic <= 5 or not sp.isprime(characteristic):
        raise ValueError("certificate characteristic is not admissible")

    problem = canonical_problem(campaign)
    variables = problem["variables"]
    descriptors = problem["descriptors"]
    expected_descriptor_hash = canonical_hash(descriptors)
    expected_monomial_hash = canonical_hash(problem["monomials"])
    expected_generator_hash = digest(tuple(problem["generators"]))
    expected_target_hash = digest((problem["target"],))

    checks: dict[str, object] = {
        "variable_names_match": certificate.get("variable_names")
        == [str(variable) for variable in variables],
        "grading_metadata_match": (
            certificate.get("character_modulus") == CHARACTER_MODULUS
            and certificate.get("character_weights") == list(CHARACTER_WEIGHTS)
            and certificate.get("target_character_weight") == 4
            and certificate.get("generator_degrees") == problem["generator_degrees"]
            and certificate.get("multiplier_degrees") == problem["multiplier_degrees"]
            and certificate.get("generator_character_weights")
            == problem["generator_weights"]
        ),
        "generator_stream_sha256_match": certificate.get("generator_stream_sha256")
        == expected_generator_hash,
        "target_sha256_match": certificate.get("target_sha256") == expected_target_hash,
        "row_descriptor_sha256_match": certificate.get("row_descriptor_sha256")
        == expected_descriptor_hash,
        "monomial_stream_sha256_match": certificate.get("monomial_stream_sha256")
        == expected_monomial_hash,
    }

    pivots = list(map(int, certificate.get("pivot_unknown_indices", [])))
    free = list(map(int, certificate.get("free_unknown_indices", [])))
    checks["pivot_profile_sha256_match"] = (
        certificate.get("pivot_unknown_indices_sha256") == canonical_hash(pivots)
    )
    checks["free_profile_sha256_match"] = (
        certificate.get("free_unknown_indices_sha256") == canonical_hash(free)
    )
    checks["gauge_partition_valid"] = (
        len(set(pivots)) == len(pivots)
        and free == sorted(set(free))
        and set(pivots).isdisjoint(free)
        and set(pivots) | set(free) == set(range(len(descriptors)))
    )

    vector = list(map(int, certificate.get("coordinate_vector", [])))
    checks["coordinate_vector_length_match"] = len(vector) == len(descriptors)
    checks["coordinate_vector_sha256_match"] = (
        certificate.get("coordinate_vector_sha256") == canonical_hash(vector)
    )
    checks["free_coordinates_zero"] = (
        len(vector) == len(descriptors)
        and all(vector[index] % characteristic == 0 for index in free)
    )

    support_records = certificate.get("solution_support", [])
    seen_support = set()
    support_well_formed = True
    support_vector = [0] * len(descriptors)
    for record in support_records:
        unknown_index = int(record["unknown_index"])
        if unknown_index in seen_support or not 0 <= unknown_index < len(descriptors):
            support_well_formed = False
            continue
        seen_support.add(unknown_index)
        generator_index, exponents = descriptors[unknown_index]
        if (
            int(record["generator_position"]) != generator_index
            or tuple(map(int, record["multiplier_exponents"])) != exponents
        ):
            support_well_formed = False
        coefficient = int(record["coefficient"]) % characteristic
        if coefficient == 0:
            support_well_formed = False
        support_vector[unknown_index] = coefficient
    checks["support_well_formed"] = support_well_formed
    checks["support_matches_complete_vector"] = (
        len(vector) == len(descriptors)
        and [value % characteristic for value in vector] == support_vector
    )

    multipliers = [sp.Poly(0, *variables, modulus=characteristic) for _ in problem["generators"]]
    if len(vector) == len(descriptors):
        multiplier_terms = [{} for _ in problem["generators"]]
        for unknown_index, coefficient in enumerate(vector):
            coefficient %= characteristic
            if coefficient:
                generator_index, exponents = descriptors[unknown_index]
                multiplier_terms[generator_index][exponents] = coefficient
        multipliers = [
            sp.Poly.from_dict(terms, variables, modulus=characteristic)
            for terms in multiplier_terms
        ]
    generators_mod = [
        polynomial_mod(generator, variables, characteristic)
        for generator in problem["generators"]
    ]
    observed = sp.Poly(0, *variables, modulus=characteristic)
    for multiplier, generator in zip(multipliers, generators_mod, strict=True):
        observed += multiplier * generator
    target = polynomial_mod(problem["target"], variables, characteristic)
    remainder = target - observed
    checks["identity_zero"] = remainder.is_zero
    checks["remainder_term_count"] = 0 if remainder.is_zero else len(remainder.terms())
    checks["nonzero_multiplier_count"] = sum(not item.is_zero for item in multipliers)
    checks["multiplier_term_count"] = sum(
        len(item.terms()) for item in multipliers if not item.is_zero
    )
    checks["maximum_multiplier_total_degree"] = max(
        (item.total_degree() for item in multipliers if not item.is_zero),
        default=None,
    )

    gauge_source_file_match = True
    if certificate.get("gauge_source") is not None:
        source = certificate["gauge_source"]
        source_path = Path(source["path"])
        gauge_source_file_match = (
            source_path.is_file() and sha256_file(source_path) == source["sha256"]
        )
    checks["gauge_source_file_sha256_match"] = gauge_source_file_match

    boolean_checks = [value for value in checks.values() if isinstance(value, bool)]
    passed = all(boolean_checks)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": (
            "hc4.decimic-j2-secant-r10-second-colon-identity-"
            "sparse-macaulay-replay.v1"
        ),
        "status": (
            "PASS_INDEPENDENT_SECOND_COLON_IDENTITY_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_SECOND_COLON_IDENTITY_REPLAY"
        ),
        "assurance": "independent exact finite-field polynomial replay",
        "characteristic": characteristic,
        "certificate": {
            "path": str(certificate_path),
            "sha256": certificate_sha256,
            "byte_count": certificate_path.stat().st_size,
            "solution_support_count": len(support_records),
        },
        "dimensions": {
            "multiplier_coordinates": len(descriptors),
            "monomial_equations": len(problem["monomials"]),
            "generators": len(problem["generators"]),
        },
        "checks": checks,
        "first_quartic_reconstruction": problem["first_metadata"],
        "second_quartic": problem["second_metadata"],
        "wall_seconds": time.perf_counter() - started,
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "source_sha256": sha256_file(script_path),
        "claim_boundary": (
            "This replay proves only the displayed M*h2 identity over the displayed "
            "finite field. It does not prove the QQ identity, determine a colon or "
            "saturated ideal, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/"
        f"hsop-j2-secant-r10-second-colon-identity-sparse-macaulay-replay-p{characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
