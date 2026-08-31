#!/usr/bin/env sage-python
"""Proof-producing sparse Macaulay certificate for the second colon candidate.

The exact finite-field statement tested is

    M*h2 = sum_{i=1}^{17} q_i*F_i + q_18*h,

where the ``F_i`` are the frozen cubics, ``h`` is the first rational quartic,
``h2`` is the second rational quartic candidate, and ``M`` is the degree-four
open factor.  Exact total degree and the frozen ``Z/12`` character reduce the
calculation to one degree-eight block.  The sparse Gaussian eliminator is
shared with the independently certified first-colon calculation, but all
problem construction, schemas, artifacts, and receipts here are distinct.

A passing run proves one identity over one displayed finite field only.  It
does not lift the identity to QQ or determine a colon or saturated ideal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import (
    RECONSTRUCTION_PRIMES,
    reconstruct_quartic,
)
from certify_j2_secant_r10_colon_identity_sparse_macaulay import (
    add_entry,
    residue,
    sparse_eliminate,
    verify_sparse_system,
)
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
    exact_exponent_tuples,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-second-colon-identity-"
    "sparse-macaulay-certificate.v1"
)
SECOND_CANDIDATE = Path(
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_second_quartic(campaign: Path, variables) -> tuple[sp.Expr, dict[str, object]]:
    """Load the frozen rational h2 candidate without trusting an expression string."""

    path = campaign / SECOND_CANDIDATE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != (
        "hc4.decimic-j2-secant-r10-second-colon-kernel-qq-candidate.v1"
    ):
        raise ValueError("unsupported second-colon candidate schema")
    if payload.get("status") != (
        "RATIONAL_CANDIDATE_RECONSTRUCTED_FROM_TWO_MODULAR_TAPS"
    ):
        raise ValueError("second-colon candidate is not a passing reconstruction")
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError("second-colon candidate variable order changed")
    if int(payload.get("total_degree", -1)) != 4:
        raise ValueError("second-colon candidate is not quartic")
    if int(payload.get("character_weight_mod_12", -1)) != 3:
        raise ValueError("second-colon candidate has the wrong character")

    terms: dict[tuple[int, ...], sp.Rational] = {}
    expression = sp.Integer(0)
    for record in payload.get("terms", []):
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != len(variables) or exponents in terms:
            raise ValueError("malformed or duplicate second-colon exponent vector")
        coefficient = sp.Rational(
            int(record["numerator"]), int(record["denominator"])
        )
        terms[exponents] = coefficient
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += coefficient * monomial
    expression = sp.expand(expression)
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    if (
        polynomial.total_degree() != 4
        or len(polynomial.terms()) != int(payload.get("term_count", -1))
        or len(polynomial.terms()) != len(terms)
    ):
        raise ValueError("second-colon polynomial profile changed")
    observed_characters = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _coefficient in polynomial.terms()
    }
    if observed_characters != {3}:
        raise ValueError("second-colon terms are not character-three homogeneous")
    return expression, {
        "path": str(path),
        "sha256": sha256_bytes(path.read_bytes()),
        "term_count": len(polynomial.terms()),
        "total_degree": polynomial.total_degree(),
        "character_weight": 3,
        "discovery_primes": list(map(int, payload["discovery_primes"])),
        "crt_modulus": payload["crt_modulus"],
        "expression_sha256": hashlib.sha256(
            sp.srepr(expression).encode("utf-8")
        ).hexdigest(),
    }


def build_character_block(campaign: Path, characteristic: int) -> dict[str, object]:
    """Build the mixed degree-(5,4), target-character-four Macaulay block."""

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    generators = list(equations) + [first_quartic]
    generator_degrees = [3] * len(equations) + [4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * second_quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() != 8:
        raise AssertionError("M*h2 is not homogeneous of degree eight")

    polynomial_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    generator_weights: list[int] = []
    for index, (generator, expected_degree) in enumerate(
        zip(generators, generator_degrees, strict=True)
    ):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), sp.Rational(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        weights = {character_weight(exponents) for exponents, _ in terms}
        degrees = {sum(exponents) for exponents, _ in terms}
        if len(weights) != 1 or degrees != {expected_degree}:
            raise AssertionError(
                f"generator {index} left its homogeneous character block"
            )
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
    if generator_weights[-1] != 4:
        raise AssertionError("the adjoined first quartic changed character")

    target_terms = [
        (tuple(map(int, exponents)), sp.Rational(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if target_weights != {4}:
        raise AssertionError(f"expected target character four, received {target_weights}")
    target_weight = 4

    monomials_by_degree_weight: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            key = (degree, character_weight(monomial))
            monomials_by_degree_weight.setdefault(key, []).append(monomial)

    equation_by_monomial: dict[tuple[int, ...], dict[int, int]] = {}
    descriptors: list[tuple[int, tuple[int, ...]]] = []
    for generator_index, (terms, generator_weight, multiplier_degree) in enumerate(
        zip(
            polynomial_terms,
            generator_weights,
            multiplier_degrees,
            strict=True,
        )
    ):
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        for multiplier in monomials_by_degree_weight.get(
            (multiplier_degree, multiplier_weight), []
        ):
            unknown_index = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, coefficient in terms:
                product = tuple(
                    left + right
                    for left, right in zip(exponents, multiplier, strict=True)
                )
                if character_weight(product) != target_weight or sum(product) != 8:
                    raise AssertionError("Macaulay product left the selected block")
                sparse_equation = equation_by_monomial.setdefault(product, {})
                add_entry(
                    sparse_equation,
                    unknown_index,
                    residue(coefficient, characteristic),
                    characteristic,
                )

    target_by_monomial = {
        exponents: residue(coefficient, characteristic)
        for exponents, coefficient in target_terms
    }
    for exponents in target_by_monomial:
        equation_by_monomial.setdefault(exponents, {})
    monomials = sorted(equation_by_monomial)
    sparse_equations = [equation_by_monomial[monomial] for monomial in monomials]
    right_hand_side = [target_by_monomial.get(monomial, 0) for monomial in monomials]
    if len(descriptors) != 37476:
        raise AssertionError(
            f"expected 37,476 mixed-degree coordinates, received {len(descriptors)}"
        )
    return {
        "normal_equations": equations,
        "generators": generators,
        "variables": variables,
        "open_factor": open_factor,
        "first_quartic": first_quartic,
        "second_quartic": second_quartic,
        "target_expression": target_expression,
        "target_polynomial": target_polynomial,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "generator_degrees": generator_degrees,
        "multiplier_degrees": multiplier_degrees,
        "generator_weights": generator_weights,
        "target_weight": target_weight,
        "descriptors": descriptors,
        "monomials": monomials,
        "sparse_equations": sparse_equations,
        "right_hand_side": right_hand_side,
        "nonzero_count": sum(map(len, sparse_equations)),
        "build_seconds": time.perf_counter() - started,
    }


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=103)
    parser.add_argument("--timeout", type=float, default=170.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    parser.add_argument(
        "--gauge-from",
        type=Path,
        help="freeze the source certificate's free-coordinate set to zero",
    )
    parser.add_argument(
        "--allow-reconstruction-prime",
        action="store_true",
        help="permit a prime used to reconstruct h or h2, recording the dependency",
    )
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if not 1 < arguments.timeout <= 240:
        parser.error("timeout must be greater than one and at most 240 seconds")
    if (
        arguments.characteristic in RECONSTRUCTION_PRIMES
        and not arguments.allow_reconstruction_prime
    ):
        parser.error("reconstruction-prime reuse requires explicit authorization")

    started = time.perf_counter()
    deadline = started + arguments.timeout
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    shared_solver_path = (
        campaign / "scripts/certify_j2_secant_r10_colon_identity_sparse_macaulay.py"
    )
    block = build_character_block(campaign, arguments.characteristic)
    pristine_equations = [dict(equation) for equation in block["sparse_equations"]]
    pristine_rhs = list(block["right_hand_side"])
    descriptor_hash = canonical_hash(block["descriptors"])
    monomial_hash = canonical_hash(block["monomials"])
    generator_hash = digest(tuple(block["generators"]))
    target_hash = digest((block["target_expression"],))

    gauge_source = None
    source_pivots: list[int] = []
    source_free: list[int] = []
    removed_free_column_nonzeros = 0
    if arguments.gauge_from is not None:
        gauge_path = arguments.gauge_from
        if not gauge_path.is_absolute():
            gauge_path = campaign / gauge_path
        gauge_payload = json.loads(gauge_path.read_text(encoding="ascii"))
        if gauge_payload.get("schema") != CERTIFICATE_SCHEMA:
            raise ValueError("--gauge-from requires a second-colon certificate")
        if gauge_payload.get("row_descriptor_sha256") != descriptor_hash:
            raise ValueError("gauge multiplier-coordinate stream changed")
        if gauge_payload.get("monomial_stream_sha256") != monomial_hash:
            raise ValueError("gauge monomial stream changed")
        if gauge_payload.get("generator_stream_sha256") != generator_hash:
            raise ValueError("gauge generator stream changed")
        if gauge_payload.get("target_sha256") != target_hash:
            raise ValueError("gauge target changed")
        source_pivots = list(map(int, gauge_payload["pivot_unknown_indices"]))
        source_free = list(map(int, gauge_payload["free_unknown_indices"]))
        unknowns = set(range(len(block["descriptors"])))
        if (
            len(set(source_pivots)) != len(source_pivots)
            or source_free != sorted(set(source_free))
            or set(source_pivots) & set(source_free)
            or set(source_pivots) | set(source_free) != unknowns
        ):
            raise ValueError("gauge pivot/free coordinates do not partition the block")
        free_set = set(source_free)
        for sparse_equation in block["sparse_equations"]:
            for unknown in tuple(sparse_equation):
                if unknown in free_set:
                    del sparse_equation[unknown]
                    removed_free_column_nonzeros += 1
        gauge_source = {
            "path": str(gauge_path),
            "sha256": sha256_bytes(gauge_path.read_bytes()),
            "characteristic": int(gauge_payload["characteristic"]),
            "pivot_unknown_set_sha256": canonical_hash(sorted(source_pivots)),
            "free_unknown_indices_sha256": canonical_hash(source_free),
            "pivot_count": len(source_pivots),
            "free_unknown_count": len(source_free),
            "removed_free_column_nonzeros": removed_free_column_nonzeros,
            "policy": "freeze source free-coordinate set; adapt pivot order",
        }

    solve = sparse_eliminate(
        block["sparse_equations"],
        block["right_hand_side"],
        len(block["descriptors"]),
        arguments.characteristic,
        deadline,
    )
    values = solve.get("values")
    replay = {"completed": False, "identity_zero": False, "reason": "solve incomplete"}
    if solve.get("completed") and solve.get("consistent") and values is not None:
        replay = verify_sparse_system(
            pristine_equations,
            pristine_rhs,
            values,
            arguments.characteristic,
        )

    actual_pivots = [int(record[0]) for record in solve["pivot_records"]]
    actual_pivot_set = set(actual_pivots)
    gauge_coverage_verified = (
        gauge_source is None
        or (
            values is not None
            and len(actual_pivots) == len(source_pivots)
            and actual_pivot_set == set(source_pivots)
            and all(values[index] == 0 for index in source_free)
        )
    )
    passed = (
        solve.get("completed") is True
        and solve.get("timed_out") is False
        and solve.get("consistent") is True
        and replay.get("identity_zero") is True
        and gauge_coverage_verified
    )

    certificate_output = arguments.certificate_output or Path(
        "artifacts/"
        f"j2-secant-r10-second-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
    )
    if not certificate_output.is_absolute():
        certificate_output = campaign / certificate_output
    certificate_record = None
    solution_support = []
    pivot_profile_hash = None
    free_profile_hash = None
    vector_hash = None
    if passed:
        pivot_unknown_indices = actual_pivots
        pivot_unknown_set = set(pivot_unknown_indices)
        if len(pivot_unknown_set) != len(pivot_unknown_indices):
            raise AssertionError("a multiplier coordinate was pivoted twice")
        free_unknown_indices = sorted(
            set(range(len(block["descriptors"]))) - pivot_unknown_set
        )
        if len(free_unknown_indices) != solve["free_unknown_count"]:
            raise AssertionError("free-coordinate count changed")
        if gauge_source is not None and free_unknown_indices != source_free:
            raise AssertionError("fixed-free gauge changed")
        for unknown_index, coefficient in enumerate(values):
            if coefficient:
                generator_index, multiplier = block["descriptors"][unknown_index]
                solution_support.append(
                    {
                        "unknown_index": unknown_index,
                        "generator_position": generator_index,
                        "multiplier_exponents": list(multiplier),
                        "coefficient": int(coefficient),
                    }
                )
        pivot_profile_hash = canonical_hash(pivot_unknown_indices)
        free_profile_hash = canonical_hash(free_unknown_indices)
        vector = list(map(int, values))
        vector_hash = canonical_hash(vector)
        certificate_payload = {
            "schema": CERTIFICATE_SCHEMA,
            "characteristic": arguments.characteristic,
            "prime_roles": {
                "used_in_quartic_reconstruction": (
                    arguments.characteristic in RECONSTRUCTION_PRIMES
                ),
                "explicit_reuse_authorized": arguments.allow_reconstruction_prime,
            },
            "variable_names": [str(variable) for variable in block["variables"]],
            "character_modulus": CHARACTER_MODULUS,
            "character_weights": list(CHARACTER_WEIGHTS),
            "target_character_weight": block["target_weight"],
            "generator_count": len(block["generators"]),
            "normal_cubic_generator_count": len(block["normal_equations"]),
            "generator_degrees": block["generator_degrees"],
            "multiplier_degrees": block["multiplier_degrees"],
            "generator_character_weights": block["generator_weights"],
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "first_quartic": block["first_metadata"],
            "second_quartic": block["second_metadata"],
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "deterministic_gauge": "all unpivoted multiplier coordinates set to zero",
            "pivot_unknown_indices": pivot_unknown_indices,
            "pivot_unknown_indices_sha256": pivot_profile_hash,
            "free_unknown_indices": free_unknown_indices,
            "free_unknown_indices_sha256": free_profile_hash,
            "gauge_source": gauge_source,
            "coordinate_vector": vector,
            "coordinate_vector_sha256": vector_hash,
            "solution_support": solution_support,
            "source_dependencies": {
                str(shared_solver_path.relative_to(campaign)): sha256_bytes(
                    shared_solver_path.read_bytes()
                )
            },
            "claim_boundary": (
                "Exact identity M*h2 in (F_1,...,F_17,h) over the displayed finite "
                "field only; this is not a QQ identity, a colon or saturation "
                "certificate, a secant-chart closure, or HC4."
            ),
        }
        certificate_text = json.dumps(
            certificate_payload, indent=2, sort_keys=True
        ) + "\n"
        certificate_output.parent.mkdir(parents=True, exist_ok=True)
        certificate_output.write_text(certificate_text, encoding="ascii")
        certificate_record = {
            "path": str(certificate_output),
            "sha256": sha256_bytes(certificate_text.encode("ascii")),
            "byte_count": len(certificate_text.encode("ascii")),
        }

    usage = resource.getrusage(resource.RUSAGE_SELF)
    status = (
        "PASS_EXACT_MODULAR_SECOND_COLON_IDENTITY"
        if passed
        else "TIMEOUT_SECOND_COLON_IDENTITY_NO_MEMBERSHIP_DECISION"
        if solve.get("timed_out")
        else "INCOMPLETE_SECOND_COLON_IDENTITY"
    )
    result = {
        "schema": (
            "hc4.decimic-j2-secant-r10-second-colon-identity-"
            "sparse-macaulay.v1"
        ),
        "status": status,
        "assurance": "exact finite-field polynomial identity only" if passed else "solver telemetry only",
        "characteristic": arguments.characteristic,
        "algorithm": (
            "degree-eight character-four sparse Macaulay block; degree-five "
            "multipliers for 17 cubics and degree-four multiplier for h; "
            "deterministic sparse Gaussian elimination"
        ),
        "dimensions": {
            "unknown_multiplier_coordinates": len(block["descriptors"]),
            "monomial_equations": len(block["monomials"]),
            "matrix_nonzeros": block["nonzero_count"],
            "target_terms": len(block["target_polynomial"].terms()),
            "normal_cubic_generators": len(block["normal_equations"]),
            "total_generators": len(block["generators"]),
        },
        "generator_degrees": block["generator_degrees"],
        "multiplier_degrees": block["multiplier_degrees"],
        "generator_character_weights": block["generator_weights"],
        "target_character_weight": block["target_weight"],
        "first_quartic": block["first_metadata"],
        "second_quartic": block["second_metadata"],
        "solver": {
            key: value
            for key, value in solve.items()
            if key not in {"values", "pivot_records"}
        },
        "same_process_sparse_replay": replay,
        "gauge": {
            "source": gauge_source,
            "coverage_verified": gauge_coverage_verified,
            "pivot_unknown_indices_sha256": pivot_profile_hash,
            "free_unknown_indices_sha256": free_profile_hash,
            "coordinate_vector_sha256": vector_hash,
        },
        "solution_support_count": len(solution_support),
        "certificate": certificate_record,
        "hashes": {
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "shared_solver_source_sha256": sha256_bytes(
                shared_solver_path.read_bytes()
            ),
        },
        "timings": {
            "block_build_seconds": block["build_seconds"],
            "solve_seconds": solve["solve_seconds"],
            "wall_seconds": time.perf_counter() - started,
        },
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "claim_boundary": (
            "A PASS proves only M*h2 in (F_1,...,F_17,h) over the displayed finite "
            "field. It does not prove the QQ identity, determine a colon or saturated "
            "ideal, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/"
        f"hsop-j2-secant-r10-second-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "output": str(output),
                "certificate": certificate_record,
                "dimensions": result["dimensions"],
                "solver": result["solver"],
                "replay": replay,
                "timings": result["timings"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
