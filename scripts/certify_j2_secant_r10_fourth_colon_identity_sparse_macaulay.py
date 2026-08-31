#!/usr/bin/env -S sage -python
"""One-prime sparse/hybrid certificate for the conditional fourth identity.

The exact finite-field statement tested is

    M*h4 = sum_{i=1}^{17} q_i*F_i + q_18*h + q_19*h2 + q_20*h3.

The script first refuses any drift from the frozen lightweight preflight, then
solves the degree-eight, character-two block.  A PASS proves only the displayed
identity over GF(173); it is not a QQ, colon, saturation, secant, or HC4 proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import sympy as sp

from audit_j2_secant_r10_fourth_colon_identity_preflight import (
    load_fourth_quartic,
)
from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_colon_identity_sparse_macaulay import (
    add_entry,
    residue,
    verify_sparse_system,
)
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    canonical_hash,
    hybrid_sparse_eliminate,
    load_third_quartic,
    sha256_bytes,
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
    "hc4.decimic-j2-secant-r10-fourth-colon-identity-"
    "sparse-macaulay-certificate.v1"
)
RECEIPT_SCHEMA = (
    "hc4.decimic-j2-secant-r10-fourth-colon-identity-"
    "sparse-macaulay.v1"
)
PREFLIGHT = Path(
    "receipts/hsop-j2-secant-r10-fourth-colon-identity-preflight-p173.json"
)


def equation_support_hash(monomials) -> str:
    return hashlib.sha256(
        json.dumps(sorted(monomials), separators=(",", ":")).encode("ascii")
    ).hexdigest()


def build_character_block(campaign: Path, characteristic: int) -> dict[str, object]:
    """Build and verify the frozen degree-eight, character-two block."""

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    third_quartic, third_metadata = load_third_quartic(campaign, variables)
    fourth_quartic, fourth_metadata = load_fourth_quartic(campaign, variables)
    generators = list(equations) + [first_quartic, second_quartic, third_quartic]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * fourth_quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() != 8:
        raise AssertionError("M*h4 is not homogeneous of degree eight")

    polynomial_terms = []
    generator_weights = []
    support_losses = []
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
            raise AssertionError(f"generator {position} left its grading block")
        lost = sum(
            residue(coefficient, characteristic) == 0
            for _exponents, coefficient in terms
        )
        if lost:
            support_losses.append(
                {"generator_position": position, "lost_term_count": lost}
            )
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
    if generator_weights[-3:] != [4, 3, 2]:
        raise AssertionError("the h,h2,h3 character ladder changed")

    target_terms = [
        (tuple(map(int, exponents)), sp.Rational(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if target_weights != {2}:
        raise AssertionError(f"expected target character two, got {target_weights}")
    target_support_loss = sum(
        residue(coefficient, characteristic) == 0
        for _exponents, coefficient in target_terms
    )
    if support_losses or target_support_loss:
        raise ValueError(
            "the source prime loses rational support: "
            f"generators={support_losses}, target={target_support_loss}"
        )
    target_weight = 2

    pools = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)

    equation_by_monomial = {}
    descriptors = []
    for generator_index, (terms, generator_weight, multiplier_degree) in enumerate(
        zip(polynomial_terms, generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        for multiplier in pools.get((multiplier_degree, multiplier_weight), []):
            unknown_index = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, coefficient in terms:
                product = tuple(
                    left + right
                    for left, right in zip(exponents, multiplier, strict=True)
                )
                if sum(product) != 8 or character_weight(product) != target_weight:
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
    sparse_equations = [equation_by_monomial[item] for item in monomials]
    right_hand_side = [target_by_monomial.get(item, 0) for item in monomials]
    nonzero_count = sum(map(len, sparse_equations))

    preflight_path = campaign / PREFLIGHT
    preflight = json.loads(preflight_path.read_text(encoding="ascii"))
    if preflight.get("status") != (
        "PASS_LIGHTWEIGHT_FOURTH_COLON_IDENTITY_PREFLIGHT_FULL_SUPPORT"
    ) or int(preflight.get("characteristic", -1)) != characteristic:
        raise ValueError("the frozen preflight is not a full-support source-prime pass")
    expected_dimensions = preflight["dimensions"]
    observed_dimensions = {
        "unknown_multiplier_coordinates": len(descriptors),
        "monomial_equations": len(monomials),
        "rational_matrix_nonzeros": nonzero_count,
        "matrix_nonzeros_mod_p": nonzero_count,
        "target_rational_terms": len(target_terms),
        "target_live_terms_mod_p": len(target_terms),
        "normal_cubic_generators": len(equations),
        "total_generators": len(generators),
    }
    if observed_dimensions != expected_dimensions:
        raise ValueError(
            f"the frozen block dimensions changed: {observed_dimensions}"
        )
    generator_hash = digest(tuple(generators))
    target_hash = digest((target_expression,))
    support_hash = equation_support_hash(monomials)
    expected_hashes = preflight["hashes"]
    if (
        generator_hash != expected_hashes["generator_stream_sha256"]
        or target_hash != expected_hashes["target_sha256"]
        or support_hash != expected_hashes["equation_support_sha256"]
    ):
        raise ValueError("the frozen preflight streams changed")

    return {
        "normal_equations": equations,
        "generators": generators,
        "variables": variables,
        "target_expression": target_expression,
        "target_polynomial": target_polynomial,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "third_metadata": third_metadata,
        "fourth_metadata": fourth_metadata,
        "generator_degrees": generator_degrees,
        "multiplier_degrees": multiplier_degrees,
        "generator_weights": generator_weights,
        "target_weight": target_weight,
        "descriptors": descriptors,
        "monomials": monomials,
        "sparse_equations": sparse_equations,
        "right_hand_side": right_hand_side,
        "nonzero_count": nonzero_count,
        "preflight": {
            "path": str(PREFLIGHT),
            "sha256": sha256_bytes(preflight_path.read_bytes()),
            "dimensions_and_streams_verified": True,
        },
        "generator_hash": generator_hash,
        "target_hash": target_hash,
        "support_hash": support_hash,
        "build_seconds": time.perf_counter() - started,
    }


def solve_and_record(arguments, script_path: Path, campaign: Path) -> int:
    started = time.perf_counter()
    sparse_deadline = started + arguments.sparse_phase
    block = build_character_block(campaign, arguments.characteristic)
    pristine_equations = [dict(item) for item in block["sparse_equations"]]
    pristine_rhs = list(block["right_hand_side"])
    descriptor_hash = canonical_hash(block["descriptors"])
    monomial_hash = canonical_hash(block["monomials"])

    solve = hybrid_sparse_eliminate(
        block["sparse_equations"],
        block["right_hand_side"],
        len(block["descriptors"]),
        arguments.characteristic,
        sparse_deadline,
    )
    values = solve.get("values")
    replay = {"completed": False, "identity_zero": False, "reason": "solve incomplete"}
    if solve.get("completed") and solve.get("consistent") and values is not None:
        replay = verify_sparse_system(
            pristine_equations, pristine_rhs, values, arguments.characteristic
        )
    passed = (
        solve.get("completed") is True
        and solve.get("timed_out") is False
        and solve.get("consistent") is True
        and replay.get("identity_zero") is True
    )

    certificate_record = None
    support = []
    pivot_hash = free_hash = vector_hash = None
    if passed:
        actual_pivots = [int(record[0]) for record in solve["pivot_records"]]
        pivot_set = set(actual_pivots)
        free = sorted(set(range(len(block["descriptors"]))) - pivot_set)
        if len(pivot_set) != len(actual_pivots) or len(free) != solve["free_unknown_count"]:
            raise AssertionError("pivot/free partition changed")
        for unknown_index, coefficient in enumerate(values):
            if coefficient:
                generator_index, multiplier = block["descriptors"][unknown_index]
                support.append(
                    {
                        "unknown_index": unknown_index,
                        "generator_position": generator_index,
                        "multiplier_exponents": list(multiplier),
                        "coefficient": int(coefficient),
                    }
                )
        vector = list(map(int, values))
        pivot_hash = canonical_hash(actual_pivots)
        free_hash = canonical_hash(free)
        vector_hash = canonical_hash(vector)
        certificate = {
            "schema": CERTIFICATE_SCHEMA,
            "characteristic": arguments.characteristic,
            "variable_names": [str(item) for item in block["variables"]],
            "character_modulus": CHARACTER_MODULUS,
            "character_weights": list(CHARACTER_WEIGHTS),
            "target_character_weight": block["target_weight"],
            "generator_count": len(block["generators"]),
            "normal_cubic_generator_count": len(block["normal_equations"]),
            "generator_degrees": block["generator_degrees"],
            "multiplier_degrees": block["multiplier_degrees"],
            "generator_character_weights": block["generator_weights"],
            "generator_stream_sha256": block["generator_hash"],
            "target_sha256": block["target_hash"],
            "first_quartic": block["first_metadata"],
            "second_quartic": block["second_metadata"],
            "third_quartic": block["third_metadata"],
            "fourth_quartic": block["fourth_metadata"],
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "equation_support_sha256": block["support_hash"],
            "deterministic_gauge": "all unpivoted multiplier coordinates set to zero",
            "pivot_unknown_indices": actual_pivots,
            "pivot_unknown_indices_sha256": pivot_hash,
            "free_unknown_indices": free,
            "free_unknown_indices_sha256": free_hash,
            "coordinate_vector": vector,
            "coordinate_vector_sha256": vector_hash,
            "solution_support": support,
            "preflight": block["preflight"],
            "source_dependencies": {
                str(script_path.relative_to(campaign)): sha256_bytes(script_path.read_bytes()),
            },
            "claim_boundary": (
                "Exact identity M*h4 in (F_1,...,F_17,h,h2,h3) over GF(173) "
                "only; not a QQ identity, colon, saturation, secant closure, or "
                "HC4 certificate."
            ),
        }
        text = json.dumps(certificate, indent=2, sort_keys=True) + "\n"
        certificate_path = arguments.certificate_output
        if not certificate_path.is_absolute():
            certificate_path = campaign / certificate_path
        certificate_path.parent.mkdir(parents=True, exist_ok=True)
        certificate_path.write_text(text, encoding="ascii")
        certificate_record = {
            "path": str(certificate_path),
            "sha256": sha256_bytes(text.encode("ascii")),
            "byte_count": len(text.encode("ascii")),
        }

    status = (
        "PASS_EXACT_MODULAR_FOURTH_COLON_IDENTITY"
        if passed
        else "CANDIDATE_MODULAR_FOURTH_COLON_NONMEMBERSHIP_REQUIRES_INDEPENDENT_REPLAY"
        if (
            solve.get("hybrid_dense_handoff") is not None
            and solve["hybrid_dense_handoff"].get("inconsistent") is True
        )
        else "TIMEOUT_FOURTH_COLON_IDENTITY_NO_MEMBERSHIP_DECISION"
        if solve.get("timed_out")
        else "INCOMPLETE_FOURTH_COLON_IDENTITY"
    )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "assurance": "exact finite-field polynomial identity" if passed else "solver telemetry only",
        "characteristic": arguments.characteristic,
        "algorithm": (
            "degree-eight character-two sparse Macaulay block; degree-five "
            "multipliers for 17 cubics and degree-four multipliers for h,h2,h3; "
            + (
                "adaptive sparse Markowitz elimination followed by an exact Sage "
                "dense finite-field row reduction of the late residual"
                if solve.get("hybrid_dense_handoff") is not None
                else "adaptive sparse Markowitz elimination"
            )
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
        "third_quartic": block["third_metadata"],
        "fourth_quartic": block["fourth_metadata"],
        "preflight": block["preflight"],
        "solver": {
            key: value
            for key, value in solve.items()
            if key not in {"values", "pivot_records"}
        },
        "same_process_sparse_replay": replay,
        "gauge": {
            "pivot_unknown_indices_sha256": pivot_hash,
            "free_unknown_indices_sha256": free_hash,
            "coordinate_vector_sha256": vector_hash,
        },
        "solution_support_count": len(support),
        "certificate": certificate_record,
        "hashes": {
            "generator_stream_sha256": block["generator_hash"],
            "target_sha256": block["target_hash"],
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "equation_support_sha256": block["support_hash"],
            "source_sha256": sha256_bytes(script_path.read_bytes()),
        },
        "operational_guard": {
            "authorized_wall_ceiling_seconds": arguments.timeout,
            "sparse_phase_seconds": arguments.sparse_phase,
            "maximum_process_rss_native": 4_500_000_000,
            "maximum_additional_swap_bytes": 1_000_000_000,
            "enforcement": "external process monitor plus fail-closed receipt",
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
            "A PASS proves only M*h4 in (F_1,...,F_17,h,h2,h3) over GF(173). "
            "It does not prove a QQ identity, colon or saturation statement, "
            "close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=173)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--sparse-phase", type=float, default=340.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-fourth-colon-identity-"
            "sparse-macaulay-hybrid-p173.json"
        ),
    )
    parser.add_argument(
        "--certificate-output",
        type=Path,
        default=Path(
            "artifacts/j2-secant-r10-fourth-colon-identity-"
            "sparse-macaulay-hybrid-p173.json"
        ),
    )
    arguments = parser.parse_args()
    if arguments.characteristic != 173:
        parser.error("this frozen source attempt is restricted to p=173")
    if arguments.timeout != 600.0:
        parser.error("this frozen source attempt requires the 600-second ceiling")
    if not 1 < arguments.sparse_phase < arguments.timeout:
        parser.error("--sparse-phase must lie strictly within the wall ceiling")
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    try:
        return solve_and_record(arguments, script_path, campaign)
    except Exception as exc:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        failure = {
            "schema": RECEIPT_SCHEMA,
            "status": "FAIL_CLOSED_FOURTH_COLON_IDENTITY_EXCEPTION",
            "assurance": "exception telemetry only",
            "characteristic": arguments.characteristic,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "script": {
                "path": str(script_path.relative_to(campaign)),
                "sha256": sha256_bytes(script_path.read_bytes()),
            },
            "resources": {
                "maximum_rss_native": usage.ru_maxrss,
                "user_cpu_seconds": usage.ru_utime,
                "system_cpu_seconds": usage.ru_stime,
            },
            "claim_boundary": (
                "No identity or nonmembership conclusion follows from this failed run."
            ),
        }
        output = arguments.output
        if not output.is_absolute():
            output = campaign / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
