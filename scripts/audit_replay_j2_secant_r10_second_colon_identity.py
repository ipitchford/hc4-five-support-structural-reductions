#!/usr/bin/env sage-python
"""Independent replay of a second-colon sparse Macaulay certificate.

This verifier deliberately does not import the second-colon producer or its
block builder.  It reconstructs ``h``, ``h2``, the multiplier-coordinate
stream, and the polynomial identity from their frozen source artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import sympy as sp

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
FIRST_QUARTIC = Path("artifacts/j2-secant-r10-first-colon-kernel-qq.json")
SECOND_QUARTIC = Path("artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def expression_from_terms(records, variables) -> sp.Expr:
    expression = sp.Integer(0)
    seen = set()
    for record in records:
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != len(variables) or exponents in seen:
            raise ValueError("malformed or duplicate quartic exponent vector")
        seen.add(exponents)
        if "coefficient" in record:
            coefficient = sp.Integer(record["coefficient"])
        else:
            coefficient = sp.Rational(
                int(record["numerator"]), int(record["denominator"])
            )
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += coefficient * monomial
    return sp.expand(expression)


def polynomial_mod(expression, variables, characteristic: int) -> sp.Poly:
    rational = sp.Poly(expression, *variables, domain=sp.QQ)
    terms = {}
    for exponents, coefficient in rational.terms():
        denominator = int(coefficient.q) % characteristic
        if denominator == 0:
            raise ZeroDivisionError(
                f"coefficient denominator vanished modulo {characteristic}"
            )
        terms[tuple(map(int, exponents))] = (
            int(coefficient.p)
            * pow(denominator, -1, characteristic)
            % characteristic
        )
    return sp.Poly.from_dict(terms, variables, modulus=characteristic)


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
    certificate = json.loads(certificate_path.read_text(encoding="ascii"))
    if certificate.get("schema") != CERTIFICATE_SCHEMA:
        raise ValueError("unsupported second-colon certificate schema")
    characteristic = int(certificate["characteristic"])
    if characteristic <= 5 or not sp.isprime(characteristic):
        raise ValueError("certificate characteristic is not an admissible prime")

    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_path = campaign / FIRST_QUARTIC
    second_path = campaign / SECOND_QUARTIC
    first_payload = json.loads(first_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second_path.read_text(encoding="utf-8"))
    variable_names = [str(variable) for variable in variables]
    if (
        first_payload["variable_names"] != variable_names
        or second_payload["variable_names"] != variable_names
        or certificate["variable_names"] != variable_names
    ):
        raise ValueError("variable orders disagree")

    first_quartic = expression_from_terms(first_payload["h_rational_terms"], variables)
    second_quartic = expression_from_terms(second_payload["terms"], variables)
    generators = list(equations) + [first_quartic]
    generator_polynomials_qq = [
        sp.Poly(generator, *variables, domain=sp.QQ) for generator in generators
    ]
    generator_degrees = [polynomial.total_degree() for polynomial in generator_polynomials_qq]
    generator_weights = []
    for polynomial in generator_polynomials_qq:
        weights = {
            character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in polynomial.terms()
        }
        if len(weights) != 1:
            raise AssertionError("a replayed generator is not character homogeneous")
        generator_weights.append(next(iter(weights)))
    if generator_degrees != [3] * 17 + [4] or generator_weights[-1] != 4:
        raise AssertionError("the replayed generator profile changed")

    target_expression = sp.expand(open_factor * second_quartic)
    target_qq = sp.Poly(target_expression, *variables, domain=sp.QQ)
    target_weights = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _coefficient in target_qq.terms()
    }
    if target_qq.total_degree() != 8 or target_weights != {4}:
        raise AssertionError("the replayed target left degree eight, character four")

    multiplier_degrees = [8 - degree for degree in generator_degrees]
    monomials_by_degree_weight: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            monomials_by_degree_weight.setdefault(
                (degree, character_weight(monomial)), []
            ).append(monomial)

    descriptors: list[tuple[int, tuple[int, ...]]] = []
    monomial_set = set()
    matrix_nonzero_count = 0
    for generator_index, (polynomial, generator_weight, multiplier_degree) in enumerate(
        zip(
            generator_polynomials_qq,
            generator_weights,
            multiplier_degrees,
            strict=True,
        )
    ):
        multiplier_weight = (4 - generator_weight) % CHARACTER_MODULUS
        for multiplier in monomials_by_degree_weight[
            (multiplier_degree, multiplier_weight)
        ]:
            descriptors.append((generator_index, multiplier))
            for generator_exponents, _coefficient in polynomial.terms():
                matrix_nonzero_count += 1
                monomial_set.add(
                    tuple(
                        int(left) + right
                        for left, right in zip(
                            generator_exponents, multiplier, strict=True
                        )
                    )
                )
    monomial_set.update(tuple(map(int, exponents)) for exponents, _ in target_qq.terms())
    monomials = sorted(monomial_set)

    descriptor_hash_match = certificate["row_descriptor_sha256"] == canonical_hash(
        descriptors
    )
    monomial_hash_match = certificate["monomial_stream_sha256"] == canonical_hash(
        monomials
    )
    generator_hash_match = certificate["generator_stream_sha256"] == digest(
        tuple(generators)
    )
    target_hash_match = certificate["target_sha256"] == digest((target_expression,))
    metadata_match = (
        certificate["generator_count"] == 18
        and certificate["normal_cubic_generator_count"] == 17
        and certificate["generator_degrees"] == generator_degrees
        and certificate["multiplier_degrees"] == multiplier_degrees
        and certificate["generator_character_weights"] == generator_weights
        and certificate["target_character_weight"] == 4
        and certificate["character_modulus"] == CHARACTER_MODULUS
        and certificate["character_weights"] == list(CHARACTER_WEIGHTS)
    )

    coordinate_vector = [int(value) % characteristic for value in certificate["coordinate_vector"]]
    vector_hash_match = certificate["coordinate_vector_sha256"] == canonical_hash(
        coordinate_vector
    )
    vector_length_match = len(coordinate_vector) == len(descriptors) == 37_476
    pivots = list(map(int, certificate["pivot_unknown_indices"]))
    free = list(map(int, certificate["free_unknown_indices"]))
    pivot_hash_match = certificate["pivot_unknown_indices_sha256"] == canonical_hash(
        pivots
    )
    free_hash_match = certificate["free_unknown_indices_sha256"] == canonical_hash(free)
    gauge_partition_valid = (
        len(set(pivots)) == len(pivots)
        and free == sorted(set(free))
        and set(pivots).isdisjoint(free)
        and set(pivots) | set(free) == set(range(len(descriptors)))
        and all(coordinate_vector[index] == 0 for index in free)
    )

    expected_support = {
        index: coefficient
        for index, coefficient in enumerate(coordinate_vector)
        if coefficient
    }
    observed_support = {}
    support_descriptors_match = True
    for record in certificate["solution_support"]:
        index = int(record["unknown_index"])
        if index in observed_support or not (0 <= index < len(descriptors)):
            support_descriptors_match = False
            continue
        generator_index, multiplier = descriptors[index]
        if (
            int(record["generator_position"]) != generator_index
            or tuple(map(int, record["multiplier_exponents"])) != multiplier
        ):
            support_descriptors_match = False
        observed_support[index] = int(record["coefficient"]) % characteristic
    support_matches_vector = observed_support == expected_support

    multiplier_terms: list[dict[tuple[int, ...], int]] = [
        {} for _ in generators
    ]
    for index, coefficient in expected_support.items():
        generator_index, multiplier = descriptors[index]
        multiplier_terms[generator_index][multiplier] = coefficient
    multipliers = [
        sp.Poly.from_dict(terms, variables, modulus=characteristic)
        for terms in multiplier_terms
    ]
    generator_polynomials = [
        polynomial_mod(generator, variables, characteristic) for generator in generators
    ]
    reconstructed = sp.Poly(0, *variables, modulus=characteristic)
    for multiplier, generator in zip(multipliers, generator_polynomials, strict=True):
        reconstructed += multiplier * generator
    target = polynomial_mod(target_expression, variables, characteristic)
    remainder = target - reconstructed
    identity_zero = remainder.is_zero

    gauge_source_match = True
    gauge_source = certificate.get("gauge_source")
    if gauge_source is not None:
        source_path = Path(gauge_source["path"])
        gauge_source_match = (
            source_path.is_file()
            and sha256(source_path) == gauge_source["sha256"]
        )
        if gauge_source_match:
            source = json.loads(source_path.read_text(encoding="ascii"))
            source_free = list(map(int, source["free_unknown_indices"]))
            gauge_source_match = (
                source_free == free
                and canonical_hash(source_free)
                == gauge_source["free_unknown_indices_sha256"]
            )

    checks = {
        "descriptor_sha256_match": descriptor_hash_match,
        "monomial_stream_sha256_match": monomial_hash_match,
        "generator_stream_sha256_match": generator_hash_match,
        "target_sha256_match": target_hash_match,
        "metadata_match": metadata_match,
        "coordinate_vector_sha256_match": vector_hash_match,
        "coordinate_vector_length_match": vector_length_match,
        "pivot_profile_sha256_match": pivot_hash_match,
        "free_profile_sha256_match": free_hash_match,
        "gauge_partition_valid": gauge_partition_valid,
        "solution_support_descriptors_match": support_descriptors_match,
        "solution_support_matches_coordinate_vector": support_matches_vector,
        "gauge_source_match": gauge_source_match,
        "identity_zero": identity_zero,
        "remainder_term_count": 0 if identity_zero else len(remainder.terms()),
        "unknown_multiplier_coordinate_count": len(descriptors),
        "monomial_equation_count": len(monomials),
        "matrix_nonzero_count": matrix_nonzero_count,
        "target_term_count": len(target_qq.terms()),
        "frozen_dimension_profile_match": (
            len(descriptors) == 37_476
            and len(monomials) == 85_921
            and matrix_nonzero_count == 1_355_292
            and len(target_qq.terms()) == 412
        ),
        "solution_support_count": len(expected_support),
        "nonzero_multiplier_count": sum(not multiplier.is_zero for multiplier in multipliers),
        "maximum_multiplier_degree": max(
            multiplier.total_degree() for multiplier in multipliers if not multiplier.is_zero
        ),
    }
    passed = all(value is True for value in checks.values() if isinstance(value, bool))
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-second-colon-identity-independent-replay.v1",
        "status": (
            "PASS_INDEPENDENT_SECOND_COLON_MODULAR_IDENTITY_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_SECOND_COLON_MODULAR_IDENTITY_REPLAY"
        ),
        "assurance": "independent exact finite-field polynomial replay",
        "characteristic": characteristic,
        "certificate": {
            "path": str(certificate_path),
            "sha256": sha256(certificate_path),
        },
        "checks": checks,
        "source_artifacts": {
            str(FIRST_QUARTIC): sha256(first_path),
            str(SECOND_QUARTIC): sha256(second_path),
        },
        "wall_seconds": time.perf_counter() - started,
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "source_sha256": sha256(script_path),
        "claim_boundary": (
            "This independently replays M*h2 in (F_1,...,F_17,h) only over the "
            "displayed finite field. It does not prove the QQ identity, compute a "
            "colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/"
        f"hsop-j2-secant-r10-second-colon-identity-independent-replay-p{characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
