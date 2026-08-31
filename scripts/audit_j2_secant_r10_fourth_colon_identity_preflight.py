#!/usr/bin/env -S sage -python
"""Lightweight graded-block preflight for the conditional fourth colon identity.

This script does *not* solve a Macaulay system.  It verifies the frozen input
profiles and counts the exact degree-eight, character-two block for

    M*h4 in (F_1,...,F_17,h,h2,h3).

The receipt is resource-planning evidence only.  In particular it proves no
identity, colon equality, saturation statement, secant closure, or HC4 case.
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
from certify_j2_secant_r10_colon_identity_sparse_macaulay import residue
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    load_third_quartic,
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


SCHEMA = "hc4.decimic-j2-secant-r10-fourth-colon-identity-preflight.v1"
FOURTH_CANDIDATE = Path(
    "artifacts/j2-secant-r10-fourth-colon-kernel-qq-candidate.json"
)
THIRD_SOURCE_RECEIPT = Path(
    "receipts/hsop-j2-secant-r10-third-colon-identity-"
    "sparse-macaulay-hybrid-p173.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_fourth_quartic(campaign: Path, variables):
    """Load h4 termwise and refuse any drift in its conditional schema."""

    path = campaign / FOURTH_CANDIDATE
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected_schema = (
        "hc4.decimic-j2-secant-r10-fourth-colon-kernel-qq-candidate.v1"
    )
    if payload.get("schema") != expected_schema:
        raise ValueError("unsupported fourth-colon candidate schema")
    if payload.get("status") != (
        "RATIONAL_FOURTH_COLON_CANDIDATE_RECONSTRUCTED_CONDITIONALLY"
    ):
        raise ValueError("fourth-colon candidate is not the frozen reconstruction")
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError("fourth-colon candidate variable order changed")
    if int(payload.get("total_degree", -1)) != 4:
        raise ValueError("fourth-colon candidate is not quartic")
    if int(payload.get("character_weight_mod_12", -1)) != 1:
        raise ValueError("fourth-colon candidate has the wrong character")

    expression = sp.Integer(0)
    seen = set()
    for record in payload.get("terms", []):
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != len(variables) or exponents in seen:
            raise ValueError("malformed or duplicate fourth-colon term")
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
    observed_weights = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _coefficient in polynomial.terms()
    }
    if (
        polynomial.total_degree() != 4
        or len(polynomial.terms()) != int(payload.get("term_count", -1))
        or len(polynomial.terms()) != len(seen)
        or observed_weights != {1}
    ):
        raise ValueError("fourth-colon candidate profile changed")
    return expression, {
        "path": str(path),
        "sha256": sha256_bytes(path.read_bytes()),
        "term_count": len(polynomial.terms()),
        "total_degree": 4,
        "character_weight": 1,
        "discovery_primes": list(map(int, payload["discovery_primes"])),
        "crt_modulus": str(payload["crt_modulus"]),
        "expression_sha256": hashlib.sha256(
            sp.srepr(expression).encode("utf-8")
        ).hexdigest(),
        "conditional_predecessor_statement": payload.get(
            "conditional_predecessor_statement"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=173)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-fourth-colon-identity-preflight-p173.json"
        ),
    )
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    third_quartic, third_metadata = load_third_quartic(campaign, variables)
    fourth_quartic, fourth_metadata = load_fourth_quartic(campaign, variables)

    generators = list(equations) + [
        first_quartic,
        second_quartic,
        third_quartic,
    ]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    polynomial_terms = []
    generator_weights = []
    generator_profiles = []
    for position, (generator, expected_degree) in enumerate(
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
            raise AssertionError(f"generator {position} left its frozen grading")
        live_terms = sum(
            residue(coefficient, arguments.characteristic) != 0
            for _exponents, coefficient in terms
        )
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
        generator_profiles.append(
            {
                "generator_position": position,
                "degree": expected_degree,
                "character_weight": generator_weights[-1],
                "rational_term_count": len(terms),
                "live_term_count_mod_p": live_terms,
                "lost_term_count_mod_p": len(terms) - live_terms,
            }
        )
    if generator_weights[-3:] != [4, 3, 2]:
        raise AssertionError("the h,h2,h3 character ladder changed")

    open_polynomial = sp.Poly(open_factor, *variables, domain=sp.QQ)
    open_weights = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _coefficient in open_polynomial.terms()
    }
    if open_polynomial.total_degree() != 4 or open_weights != {1}:
        raise AssertionError("the open factor M profile changed")

    target_expression = sp.expand(open_factor * fourth_quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    target_terms = [
        (tuple(map(int, exponents)), sp.Rational(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if target_polynomial.total_degree() != 8 or target_weights != {2}:
        raise AssertionError("M*h4 left degree eight or character two")
    target_weight = 2
    target_live_terms = sum(
        residue(coefficient, arguments.characteristic) != 0
        for _exponents, coefficient in target_terms
    )

    pools = {}
    for degree in (4, 5):
        for monomial in exact_exponent_tuples(len(variables), degree):
            weight = character_weight(monomial)
            pools.setdefault((degree, weight), []).append(monomial)

    equation_support = set(exponents for exponents, _coefficient in target_terms)
    generator_blocks = []
    unknown_count = 0
    rational_nonzeros = 0
    modular_nonzeros = 0
    for position, (terms, generator_weight, generator_degree, profile) in enumerate(
        zip(
            polynomial_terms,
            generator_weights,
            generator_degrees,
            generator_profiles,
            strict=True,
        )
    ):
        multiplier_degree = 8 - generator_degree
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        multipliers = pools[(multiplier_degree, multiplier_weight)]
        multiplier_count = len(multipliers)
        unknown_count += multiplier_count
        rational_nonzeros += multiplier_count * len(terms)
        modular_nonzeros += multiplier_count * profile["live_term_count_mod_p"]
        for multiplier in multipliers:
            for exponents, _coefficient in terms:
                product = tuple(
                    left + right
                    for left, right in zip(exponents, multiplier, strict=True)
                )
                if sum(product) != 8 or character_weight(product) != target_weight:
                    raise AssertionError("a product left the selected block")
                equation_support.add(product)
        generator_blocks.append(
            {
                **profile,
                "multiplier_degree": multiplier_degree,
                "multiplier_character_weight": multiplier_weight,
                "multiplier_coordinate_count": multiplier_count,
                "rational_matrix_nonzeros": multiplier_count * len(terms),
                "matrix_nonzeros_mod_p": (
                    multiplier_count * profile["live_term_count_mod_p"]
                ),
            }
        )

    third_receipt_path = campaign / THIRD_SOURCE_RECEIPT
    third_receipt = json.loads(third_receipt_path.read_text(encoding="ascii"))
    third_dimensions = third_receipt["dimensions"]
    dimensions = {
        "unknown_multiplier_coordinates": unknown_count,
        "monomial_equations": len(equation_support),
        "rational_matrix_nonzeros": rational_nonzeros,
        "matrix_nonzeros_mod_p": modular_nonzeros,
        "target_rational_terms": len(target_terms),
        "target_live_terms_mod_p": target_live_terms,
        "normal_cubic_generators": len(equations),
        "total_generators": len(generators),
    }
    comparison = {
        "third_identity_receipt": {
            "path": str(THIRD_SOURCE_RECEIPT),
            "sha256": sha256_bytes(third_receipt_path.read_bytes()),
            "characteristic": int(third_receipt["characteristic"]),
            "dimensions": third_dimensions,
            "maximum_rss_native": int(
                third_receipt["resources"]["maximum_rss_native"]
            ),
            "solve_seconds": float(third_receipt["timings"]["solve_seconds"]),
            "wall_seconds": float(third_receipt["timings"]["wall_seconds"]),
        },
        "dimension_ratios_fourth_over_third": {
            "unknown_multiplier_coordinates": (
                unknown_count / third_dimensions["unknown_multiplier_coordinates"]
            ),
            "monomial_equations": (
                len(equation_support) / third_dimensions["monomial_equations"]
            ),
            "matrix_nonzeros": (
                modular_nonzeros / third_dimensions["matrix_nonzeros"]
            ),
            "target_terms": len(target_terms) / third_dimensions["target_terms"],
        },
        "calibration_warning": (
            "Raw block ratios do not determine elimination fill, pivot order, dense "
            "handoff size, runtime, or peak RSS.  They support a bounded launch plan, "
            "not a resource guarantee."
        ),
    }
    nnz_ratio = modular_nonzeros / third_dimensions["matrix_nonzeros"]
    calibrated_central_estimate = {
        "method": (
            "multiply the measured third-identity p173 resource by the raw "
            "matrix-nonzero ratio; descriptive extrapolation only"
        ),
        "matrix_nonzero_ratio": nnz_ratio,
        "solve_seconds": float(third_receipt["timings"]["solve_seconds"])
        * nnz_ratio,
        "wall_seconds": float(third_receipt["timings"]["wall_seconds"])
        * nnz_ratio,
        "maximum_rss_native": round(
            int(third_receipt["resources"]["maximum_rss_native"]) * nnz_ratio
        ),
        "not_a_bound_because": (
            "sparse fill, pivot profile, and dense residual dimensions are unknown"
        ),
    }

    full_support = (
        modular_nonzeros == rational_nonzeros
        and target_live_terms == len(target_terms)
    )
    result = {
        "schema": SCHEMA,
        "status": (
            "PASS_LIGHTWEIGHT_FOURTH_COLON_IDENTITY_PREFLIGHT_FULL_SUPPORT"
            if full_support
            else "PREFLIGHT_PRIME_LOSES_RATIONAL_SUPPORT"
        ),
        "assurance": "exact graded support and dimension audit; no linear solve",
        "characteristic": arguments.characteristic,
        "statement_preflighted": "M*h4 in (F_1,...,F_17,h,h2,h3)",
        "conditional_on": (
            "the frozen h4 candidate and predecessor h3 data; this audit neither "
            "proves nor assumes the QQ identity M*h3 in (F_1,...,F_17,h,h2)"
        ),
        "grading": {
            "variable_count": len(variables),
            "character_modulus": CHARACTER_MODULUS,
            "character_weights": list(CHARACTER_WEIGHTS),
            "target_total_degree": 8,
            "open_factor_degree": 4,
            "open_factor_character_weight": 1,
            "fourth_quartic_character_weight": 1,
            "target_character_weight": target_weight,
        },
        "dimensions": dimensions,
        "generator_blocks": generator_blocks,
        "quartics": {
            "first": first_metadata,
            "second": second_metadata,
            "third": third_metadata,
            "fourth": fourth_metadata,
        },
        "hashes": {
            "normal_equation_stream_sha256": digest(tuple(equations)),
            "generator_stream_sha256": digest(tuple(generators)),
            "target_sha256": digest((target_expression,)),
            "equation_support_sha256": hashlib.sha256(
                json.dumps(sorted(equation_support), separators=(",", ":")).encode(
                    "ascii"
                )
            ).hexdigest(),
        },
        "comparison_to_third_identity_source_run": comparison,
        "bounded_launch_plan": {
            "precondition": (
                "the h3 QQ reconstruction/replay has finished and no other "
                "multi-gigabyte algebra job is running"
            ),
            "implementation": (
                "specialize the third-identity producer to load h4, adjoin h3, "
                "select target character two, and assert this receipt's frozen "
                "dimensions and stream hashes before elimination"
            ),
            "source_prime": arguments.characteristic,
            "source_prime_has_full_rational_support": full_support,
            "calibrated_central_estimate": calibrated_central_estimate,
            "operational_ceiling": {
                "wall_seconds": 600,
                "maximum_process_rss_native": 4_500_000_000,
                "maximum_additional_swap_bytes": 1_000_000_000,
                "response_at_ceiling": (
                    "stop or allow the hard timeout to emit a fail-closed telemetry "
                    "receipt; do not infer nonmembership"
                ),
            },
            "successor_steps_only_after_source_pass": [
                "independent modular replay at the source prime",
                "one fixed-free transfer prime using the new h4 gauge",
                "then decide whether QQ reconstruction is tractable",
            ],
        },
        "reuse_assessment": {
            "sparse_hybrid_algorithm_reusable": True,
            "third_identity_gauge_reusable": False,
            "reason_gauge_is_not_reusable": (
                "the target character, multiplier descriptor stream, generator "
                "stream, and monomial stream all change"
            ),
            "required_first_step": (
                "one fresh source-prime solve in this fourth-identity block; only a "
                "passing fourth-identity certificate may seed fixed-free transfers"
            ),
            "safe_launch_policy": (
                "do not overlap the fresh solve with rational reconstruction or any "
                "other multi-gigabyte algebra process; monitor RSS/swap and retain a "
                "hard timeout plus fail-closed receipt"
            ),
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256_bytes(script_path.read_bytes()),
        },
        "resources": {
            "maximum_rss_native": resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss,
            "wall_seconds": time.perf_counter() - started,
        },
        "claim_boundary": (
            "This receipt counts and hashes the candidate fourth-identity Macaulay "
            "block.  It proves no modular or rational polynomial identity, colon "
            "equality, saturation statement, secant closure, or HC4 case."
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.write_text(text, encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if full_support else 2


if __name__ == "__main__":
    raise SystemExit(main())
