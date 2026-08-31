#!/usr/bin/env sage-python
"""Proof-producing sparse Macaulay certificate for the third colon candidate.

The exact finite-field statement tested is

    M*h3 = sum_{i=1}^{17} q_i*F_i + q_18*h + q_19*h2.

All inputs are frozen rational polynomials.  Total degree eight and the
``Z/12`` character-three grading isolate one sparse Macaulay block.  A passing
run proves only the displayed identity over one finite field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import sympy as sp
from sage.all import GF, Matrix

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_colon_identity_sparse_macaulay import (
    add_entry,
    residue,
    sparse_eliminate,
    verify_sparse_system,
)
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
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
    "hc4.decimic-j2-secant-r10-third-colon-identity-"
    "sparse-macaulay-certificate.v1"
)
THIRD_CANDIDATE = Path(
    "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    )


def load_third_quartic(campaign: Path, variables):
    """Load h3 termwise, refusing substituted schemas or gradings."""

    path = campaign / THIRD_CANDIDATE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != (
        "hc4.decimic-j2-secant-r10-third-colon-kernel-qq-candidate.v1"
    ):
        raise ValueError("unsupported third-colon candidate schema")
    if payload.get("status") != "RATIONAL_THIRD_COLON_CANDIDATE_RECONSTRUCTED":
        raise ValueError("third-colon candidate is not a passing reconstruction")
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError("third-colon candidate variable order changed")
    if int(payload.get("total_degree", -1)) != 4:
        raise ValueError("third-colon candidate is not quartic")
    if int(payload.get("character_weight_mod_12", -1)) != 2:
        raise ValueError("third-colon candidate has the wrong character")

    expression = sp.Integer(0)
    seen = set()
    for record in payload.get("terms", []):
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != len(variables) or exponents in seen:
            raise ValueError("malformed or duplicate third-colon term")
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
    weights = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _coefficient in polynomial.terms()
    }
    if (
        polynomial.total_degree() != 4
        or len(polynomial.terms()) != int(payload.get("term_count", -1))
        or len(polynomial.terms()) != len(seen)
        or weights != {2}
    ):
        raise ValueError("third-colon candidate profile changed")
    return expression, {
        "path": str(path),
        "sha256": sha256_bytes(path.read_bytes()),
        "term_count": len(polynomial.terms()),
        "total_degree": 4,
        "character_weight": 2,
        "discovery_primes": list(map(int, payload["discovery_primes"])),
        "crt_modulus": payload["crt_modulus"],
        "expression_sha256": hashlib.sha256(
            sp.srepr(expression).encode("utf-8")
        ).hexdigest(),
    }


def build_character_block(
    campaign: Path, characteristic: int, *, require_full_support: bool = True
) -> dict[str, object]:
    """Build the degree-eight, character-three block for M*h3 in (F,h,h2)."""

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    third_quartic, third_metadata = load_third_quartic(campaign, variables)
    generators = list(equations) + [first_quartic, second_quartic]
    generator_degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * third_quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() != 8:
        raise AssertionError("M*h3 is not homogeneous of degree eight")

    polynomial_terms = []
    generator_weights = []
    support_losses = []
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
            raise AssertionError(f"generator {index} left its grading block")
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
        lost = sum(1 for _exponents, coefficient in terms if residue(coefficient, characteristic) == 0)
        if lost:
            support_losses.append({"generator_position": index, "lost_term_count": lost})
    if generator_weights[-2:] != [4, 3]:
        raise AssertionError("the adjoined quartic characters changed")

    target_terms = [
        (tuple(map(int, exponents)), sp.Rational(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_support_loss = sum(
        1 for _exponents, coefficient in target_terms
        if residue(coefficient, characteristic) == 0
    )
    if require_full_support and (support_losses or target_support_loss):
        raise ValueError(
            "the selected prime loses rational support: "
            f"generators={support_losses}, target={target_support_loss}"
        )
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if target_weights != {3}:
        raise AssertionError(f"expected target character three, got {target_weights}")
    target_weight = 3

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
    sparse_equations = [equation_by_monomial[item] for item in monomials]
    right_hand_side = [target_by_monomial.get(item, 0) for item in monomials]
    if len(descriptors) != 38048:
        raise AssertionError(
            f"expected 38,048 multiplier coordinates, got {len(descriptors)}"
        )
    return {
        "normal_equations": equations,
        "generators": generators,
        "variables": variables,
        "first_quartic": first_quartic,
        "second_quartic": second_quartic,
        "third_quartic": third_quartic,
        "target_expression": target_expression,
        "target_polynomial": target_polynomial,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "third_metadata": third_metadata,
        "generator_degrees": generator_degrees,
        "multiplier_degrees": multiplier_degrees,
        "generator_weights": generator_weights,
        "target_weight": target_weight,
        "descriptors": descriptors,
        "monomials": monomials,
        "sparse_equations": sparse_equations,
        "right_hand_side": right_hand_side,
        "nonzero_count": sum(map(len, sparse_equations)),
        "support_losses": support_losses,
        "target_support_loss": target_support_loss,
        "build_seconds": time.perf_counter() - started,
    }


def hybrid_sparse_eliminate(
    equations,
    right_hand_side,
    unknown_count: int,
    characteristic: int,
    sparse_deadline: float,
) -> dict[str, object]:
    """Finish a late dense residual exactly after sparse Markowitz elimination."""

    solve = sparse_eliminate(
        equations,
        right_hand_side,
        unknown_count,
        characteristic,
        sparse_deadline,
    )
    if not solve.get("timed_out"):
        solve["hybrid_dense_handoff"] = None
        return solve

    dense_started = time.perf_counter()
    sparse_records = list(solve["pivot_records"])
    sparse_pivots = {int(record[0]) for record in sparse_records}
    active_rows = [
        (index, equation)
        for index, equation in enumerate(equations)
        if equation is not None
    ]
    active_unknowns = sorted(
        {
            unknown
            for _index, equation in active_rows
            for unknown in equation
            if unknown not in sparse_pivots
        }
    )
    local_column = {unknown: index for index, unknown in enumerate(active_unknowns)}
    field = GF(characteristic)
    augmented = Matrix(
        field,
        len(active_rows),
        len(active_unknowns) + 1,
        sparse=False,
    )
    row_build_started = time.perf_counter()
    for local_row, (source_row, equation) in enumerate(active_rows):
        dense_row = [0] * (len(active_unknowns) + 1)
        for unknown, coefficient in equation.items():
            dense_row[local_column[unknown]] = coefficient
        dense_row[-1] = right_hand_side[source_row]
        augmented.set_row(local_row, dense_row)
    row_build_seconds = time.perf_counter() - row_build_started
    echelon_started = time.perf_counter()
    augmented.echelonize()
    echelon_seconds = time.perf_counter() - echelon_started
    pivots = tuple(map(int, augmented.pivots()))
    rhs_column = len(active_unknowns)
    inconsistent = rhs_column in pivots
    dense_pivot_columns = [column for column in pivots if column != rhs_column]
    dense_records = []
    if not inconsistent:
        for pivot_row, pivot_column in enumerate(dense_pivot_columns):
            constant = int(augmented[pivot_row, rhs_column])
            tail = tuple(
                (
                    active_unknowns[column],
                    int(-augmented[pivot_row, column]),
                )
                for column in range(pivot_column + 1, rhs_column)
                if augmented[pivot_row, column]
            )
            dense_records.append(
                (active_unknowns[pivot_column], constant, tail)
            )
    pivot_records = sparse_records + dense_records
    values = [0] * unknown_count
    completed = not inconsistent
    if completed:
        for pivot_unknown, constant, tail in reversed(pivot_records):
            values[pivot_unknown] = (
                constant
                + sum(coefficient * values[unknown] for unknown, coefficient in tail)
            ) % characteristic
    dense_profile = {
        "trigger": "sparse phase reached its calibrated deadline",
        "active_source_equation_count": len(active_rows),
        "active_unknown_count": len(active_unknowns),
        "dense_augmented_shape": [len(active_rows), len(active_unknowns) + 1],
        "dense_pivot_count": len(dense_pivot_columns),
        "dense_free_unknown_count": len(active_unknowns) - len(dense_pivot_columns),
        "inconsistent": inconsistent,
        "row_build_seconds": row_build_seconds,
        "echelon_seconds": echelon_seconds,
        "wall_seconds": time.perf_counter() - dense_started,
    }
    return {
        **solve,
        "completed": completed,
        "timed_out": False,
        "consistent": not inconsistent,
        "inconsistent_equation": "dense_rhs_pivot" if inconsistent else None,
        "values": values,
        "pivot_records": pivot_records,
        "pivot_count": len(pivot_records),
        "free_unknown_count": unknown_count - len(pivot_records),
        "active_equation_count": 0 if completed else len(active_rows),
        "solve_seconds": solve["solve_seconds"] + dense_profile["wall_seconds"],
        "hybrid_dense_handoff": dense_profile,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=103)
    parser.add_argument("--timeout", type=float, default=220.0)
    parser.add_argument(
        "--sparse-phase",
        type=float,
        default=None,
        help="handoff deadline in seconds; defaults to the full timeout",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    parser.add_argument(
        "--gauge-from",
        type=Path,
        help="freeze the source certificate's free coordinates to zero",
    )
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if not 1 < arguments.timeout <= 900:
        parser.error("timeout must be greater than one and at most 900 seconds")
    if arguments.sparse_phase is not None and not (
        1 < arguments.sparse_phase < arguments.timeout
    ):
        parser.error("--sparse-phase must lie strictly between one and --timeout")

    started = time.perf_counter()
    deadline = started + arguments.timeout
    sparse_deadline = (
        deadline
        if arguments.sparse_phase is None
        else started + arguments.sparse_phase
    )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    shared_solver_path = (
        campaign / "scripts/certify_j2_secant_r10_colon_identity_sparse_macaulay.py"
    )
    second_loader_path = (
        campaign
        / "scripts/certify_j2_secant_r10_second_colon_identity_sparse_macaulay.py"
    )
    block = build_character_block(campaign, arguments.characteristic)
    pristine_equations = [dict(item) for item in block["sparse_equations"]]
    pristine_rhs = list(block["right_hand_side"])
    descriptor_hash = canonical_hash(block["descriptors"])
    monomial_hash = canonical_hash(block["monomials"])
    generator_hash = digest(tuple(block["generators"]))
    target_hash = digest((block["target_expression"],))

    gauge_source = None
    source_pivots = []
    source_free = []
    removed_free_column_nonzeros = 0
    if arguments.gauge_from is not None:
        gauge_path = arguments.gauge_from
        if not gauge_path.is_absolute():
            gauge_path = campaign / gauge_path
        source = json.loads(gauge_path.read_text(encoding="ascii"))
        if source.get("schema") != CERTIFICATE_SCHEMA:
            raise ValueError("--gauge-from requires a third-colon certificate")
        if source.get("row_descriptor_sha256") != descriptor_hash:
            raise ValueError("gauge descriptor stream changed")
        if source.get("monomial_stream_sha256") != monomial_hash:
            raise ValueError("gauge monomial stream changed")
        if source.get("generator_stream_sha256") != generator_hash:
            raise ValueError("gauge generator stream changed")
        if source.get("target_sha256") != target_hash:
            raise ValueError("gauge target changed")
        source_pivots = list(map(int, source["pivot_unknown_indices"]))
        source_free = list(map(int, source["free_unknown_indices"]))
        unknowns = set(range(len(block["descriptors"])))
        if (
            len(set(source_pivots)) != len(source_pivots)
            or source_free != sorted(set(source_free))
            or set(source_pivots) & set(source_free)
            or set(source_pivots) | set(source_free) != unknowns
        ):
            raise ValueError("gauge pivot/free profile is not a partition")
        free_set = set(source_free)
        for equation in block["sparse_equations"]:
            for unknown in tuple(equation):
                if unknown in free_set:
                    del equation[unknown]
                    removed_free_column_nonzeros += 1
        gauge_source = {
            "path": str(gauge_path),
            "sha256": sha256_bytes(gauge_path.read_bytes()),
            "characteristic": int(source["characteristic"]),
            "pivot_unknown_set_sha256": canonical_hash(sorted(source_pivots)),
            "free_unknown_indices_sha256": canonical_hash(source_free),
            "pivot_count": len(source_pivots),
            "free_unknown_count": len(source_free),
            "removed_free_column_nonzeros": removed_free_column_nonzeros,
            "policy": "freeze source free-coordinate set; adapt pivot order",
        }

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
    actual_pivots = [int(record[0]) for record in solve["pivot_records"]]
    coverage = (
        gauge_source is None
        or (
            values is not None
            and set(actual_pivots) == set(source_pivots)
            and len(actual_pivots) == len(source_pivots)
            and all(values[index] == 0 for index in source_free)
        )
    )
    passed = (
        solve.get("completed") is True
        and solve.get("timed_out") is False
        and solve.get("consistent") is True
        and replay.get("identity_zero") is True
        and coverage
    )

    certificate_output = arguments.certificate_output or Path(
        "artifacts/"
        f"j2-secant-r10-third-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
    )
    if not certificate_output.is_absolute():
        certificate_output = campaign / certificate_output
    certificate_record = None
    support = []
    pivot_hash = free_hash = vector_hash = None
    if passed:
        pivot_set = set(actual_pivots)
        free = sorted(set(range(len(block["descriptors"]))) - pivot_set)
        if len(pivot_set) != len(actual_pivots) or len(free) != solve["free_unknown_count"]:
            raise AssertionError("pivot/free partition changed")
        if gauge_source is not None and free != source_free:
            raise AssertionError("fixed-free gauge changed")
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
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "first_quartic": block["first_metadata"],
            "second_quartic": block["second_metadata"],
            "third_quartic": block["third_metadata"],
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "deterministic_gauge": "all unpivoted multiplier coordinates set to zero",
            "pivot_unknown_indices": actual_pivots,
            "pivot_unknown_indices_sha256": pivot_hash,
            "free_unknown_indices": free,
            "free_unknown_indices_sha256": free_hash,
            "gauge_source": gauge_source,
            "coordinate_vector": vector,
            "coordinate_vector_sha256": vector_hash,
            "solution_support": support,
            "source_dependencies": {
                str(shared_solver_path.relative_to(campaign)): sha256_bytes(
                    shared_solver_path.read_bytes()
                ),
                str(second_loader_path.relative_to(campaign)): sha256_bytes(
                    second_loader_path.read_bytes()
                ),
            },
            "claim_boundary": (
                "Exact identity M*h3 in (F_1,...,F_17,h,h2) over the displayed "
                "finite field only; not a QQ identity, colon, saturation, secant "
                "closure, or HC4 certificate."
            ),
        }
        text = json.dumps(certificate, indent=2, sort_keys=True) + "\n"
        certificate_output.parent.mkdir(parents=True, exist_ok=True)
        certificate_output.write_text(text, encoding="ascii")
        certificate_record = {
            "path": str(certificate_output),
            "sha256": sha256_bytes(text.encode("ascii")),
            "byte_count": len(text.encode("ascii")),
        }

    usage = resource.getrusage(resource.RUSAGE_SELF)
    status = (
        "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        if passed
        else "CANDIDATE_MODULAR_THIRD_COLON_NONMEMBERSHIP_REQUIRES_INDEPENDENT_REPLAY"
        if (
            solve.get("hybrid_dense_handoff") is not None
            and solve["hybrid_dense_handoff"].get("inconsistent") is True
        )
        else "TIMEOUT_THIRD_COLON_IDENTITY_NO_MEMBERSHIP_DECISION"
        if solve.get("timed_out")
        else "INCOMPLETE_THIRD_COLON_IDENTITY"
    )
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-identity-sparse-macaulay.v1",
        "status": status,
        "assurance": "exact finite-field polynomial identity" if passed else "solver telemetry only",
        "characteristic": arguments.characteristic,
        "algorithm": (
            "degree-eight character-three sparse Macaulay block; degree-five "
            "multipliers for 17 cubics and degree-four multipliers for h,h2; "
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
        "solver": {key: value for key, value in solve.items() if key not in {"values", "pivot_records"}},
        "same_process_sparse_replay": replay,
        "gauge": {
            "source": gauge_source,
            "coverage_verified": coverage,
            "pivot_unknown_indices_sha256": pivot_hash,
            "free_unknown_indices_sha256": free_hash,
            "coordinate_vector_sha256": vector_hash,
        },
        "solution_support_count": len(support),
        "certificate": certificate_record,
        "hashes": {
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "shared_solver_source_sha256": sha256_bytes(shared_solver_path.read_bytes()),
            "second_quartic_loader_source_sha256": sha256_bytes(
                second_loader_path.read_bytes()
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
            "A PASS proves only M*h3 in (F_1,...,F_17,h,h2) over the displayed "
            "finite field. It does not prove a QQ identity, colon or saturation, "
            "close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/"
        f"hsop-j2-secant-r10-third-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "output": str(output),
        "certificate": certificate_record,
        "dimensions": result["dimensions"],
        "solver": result["solver"],
        "replay": replay,
        "timings": result["timings"],
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
