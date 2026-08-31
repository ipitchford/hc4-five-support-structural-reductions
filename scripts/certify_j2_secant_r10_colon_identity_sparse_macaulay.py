#!/usr/bin/env sage-python
"""Target-directed sparse Macaulay certificate for the first colon kernel.

This script proves a single finite-field statement

    M*h = sum_i q_i*F_i

without computing a standard basis.  Here the ``F_i`` are the frozen seventeen
homogeneous cubics, ``M`` is the degree-four open factor, and ``h`` is the
reconstructed homogeneous quartic.  The exact ``Z/12`` character splits the
degree-eight Macaulay matrix before construction.

The linear solver is deliberately elementary and proof-producing.  It performs
sparse Gaussian elimination on monomial equations, chooses pivots
deterministically, sets any surviving free variables to zero, and emits the
resulting multiplier coefficients.  A PASS still proves only the displayed
identity in one finite field; a separate replay script is required for the
frozen certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import resource
import time
from collections import Counter
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import (
    RECONSTRUCTION_PRIMES,
    reconstruct_quartic,
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def residue(coefficient: sp.Rational, characteristic: int) -> int:
    """Map one exact rational coefficient into ``GF(characteristic)``."""

    rational = sp.Rational(coefficient)
    denominator = int(rational.q) % characteristic
    if denominator == 0:
        raise ZeroDivisionError(
            f"coefficient denominator is zero modulo {characteristic}"
        )
    return (int(rational.p) % characteristic) * pow(
        denominator, -1, characteristic
    ) % characteristic


def add_entry(polynomial: dict[int, int], key: int, value: int, characteristic: int) -> None:
    """Accumulate one sparse coefficient, deleting exact modular zeros."""

    new_value = (polynomial.get(key, 0) + value) % characteristic
    if new_value:
        polynomial[key] = new_value
    else:
        polynomial.pop(key, None)


def build_character_block(campaign: Path, characteristic: int) -> dict[str, object]:
    """Build only the degree-eight, character-five Macaulay block."""

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    quartic, reconstruction = reconstruct_quartic(campaign, variables)
    target_expression = sp.expand(open_factor * quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() != 8:
        raise AssertionError("M*h is not homogeneous of degree eight")

    polynomial_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    generator_weights: list[int] = []
    for index, equation in enumerate(equations):
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), sp.Rational(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        weights = {character_weight(exponents) for exponents, _ in terms}
        degrees = {sum(exponents) for exponents, _ in terms}
        if len(weights) != 1 or degrees != {3}:
            raise AssertionError(f"generator {index} left the homogeneous character block")
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))

    target_terms = [
        (tuple(map(int, exponents)), sp.Rational(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if len(target_weights) != 1:
        raise AssertionError("M*h is not character homogeneous")
    target_weight = next(iter(target_weights))
    if target_weight != 5:
        raise AssertionError(f"expected target character 5, received {target_weight}")

    degree_five_by_weight: list[list[tuple[int, ...]]] = [
        [] for _ in range(CHARACTER_MODULUS)
    ]
    for monomial in exact_exponent_tuples(len(variables), 5):
        degree_five_by_weight[character_weight(monomial)].append(monomial)

    # Each dictionary is a monomial equation and maps multiplier-coordinate
    # indices to coefficients.  Exponent tuples remain the outer keys until a
    # canonical lexicographic equation order is frozen below.
    equation_by_monomial: dict[tuple[int, ...], dict[int, int]] = {}
    descriptors: list[tuple[int, tuple[int, ...]]] = []
    for generator_index, (terms, generator_weight) in enumerate(
        zip(polynomial_terms, generator_weights, strict=True)
    ):
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        for multiplier in degree_five_by_weight[multiplier_weight]:
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
    nonzero_count = sum(len(equation) for equation in sparse_equations)
    return {
        "equations": equations,
        "variables": variables,
        "open_factor": open_factor,
        "quartic": quartic,
        "target_expression": target_expression,
        "target_polynomial": target_polynomial,
        "reconstruction": reconstruction,
        "generator_weights": generator_weights,
        "target_weight": target_weight,
        "descriptors": descriptors,
        "monomials": monomials,
        "sparse_equations": sparse_equations,
        "right_hand_side": right_hand_side,
        "nonzero_count": nonzero_count,
        "build_seconds": time.perf_counter() - started,
    }


def sparse_eliminate(
    equations: list[dict[int, int]],
    right_hand_side: list[int],
    unknown_count: int,
    characteristic: int,
    deadline: float,
    prescribed_pivots: list[int] | None = None,
) -> dict[str, object]:
    """Solve an overdetermined sparse system with deterministic exact pivots."""

    started = time.perf_counter()
    incidence: list[set[int]] = [set() for _ in range(unknown_count)]
    heap: list[tuple[int, int]] = []
    for equation_index, equation in enumerate(equations):
        for unknown in equation:
            incidence[unknown].add(equation_index)
        heap.append((len(equation), equation_index))
    heapq.heapify(heap)

    # Each pivot record is x_p = constant + sum coefficient*x_j.  Its remaining
    # variables have not yet been pivoted, so reverse traversal is triangular.
    pivot_records: list[tuple[int, int, tuple[tuple[int, int], ...]]] = []
    active_equation_count = len(equations)
    inconsistent_equation = None
    update_count = 0
    fill_added = 0
    fill_deleted = 0
    maximum_active_equation_length = max(map(len, equations), default=0)
    peak_total_nonzeros = sum(map(len, equations))
    current_total_nonzeros = peak_total_nonzeros
    length_at_pivot = Counter()
    prescribed_position = 0
    fixed_gauge_failure = None

    while heap:
        # Every live equation has already been consumed.  The heap can still
        # contain many obsolete length records, but they carry no mathematical
        # information and need not be drained one by one.
        if active_equation_count == 0:
            heap.clear()
            break
        if time.perf_counter() >= deadline:
            return {
                "completed": False,
                "timed_out": True,
                "pivot_records": pivot_records,
                "pivot_count": len(pivot_records),
                "free_unknown_count": unknown_count - len(pivot_records),
                "fixed_gauge_failure": fixed_gauge_failure,
                "prescribed_pivot_count": (
                    None if prescribed_pivots is None else len(prescribed_pivots)
                ),
                "completed_prescribed_pivots": prescribed_position,
                "active_equation_count": active_equation_count,
                "current_total_nonzeros": current_total_nonzeros,
                "peak_total_nonzeros": peak_total_nonzeros,
                "maximum_active_equation_length": maximum_active_equation_length,
                "update_count": update_count,
                "fill_added": fill_added,
                "fill_deleted": fill_deleted,
                "pivot_length_distribution": dict(sorted(length_at_pivot.items())),
                "solve_seconds": time.perf_counter() - started,
            }

        if prescribed_pivots is not None:
            if prescribed_position == len(prescribed_pivots):
                break
            pivot_unknown = prescribed_pivots[prescribed_position]
            candidates = [
                equation_index
                for equation_index in incidence[pivot_unknown]
                if equations[equation_index] is not None
                and pivot_unknown in equations[equation_index]
            ]
            if not candidates:
                fixed_gauge_failure = {
                    "prescribed_position": prescribed_position,
                    "pivot_unknown": pivot_unknown,
                    "reason": "no active equation contains the prescribed pivot",
                }
                break
            equation_index = min(
                candidates,
                key=lambda index: (len(equations[index]), index),
            )
            equation = equations[equation_index]
        else:
            queued_length, equation_index = heapq.heappop(heap)
            equation = equations[equation_index]
            if equation is None or queued_length != len(equation):
                continue
            if not equation:
                if right_hand_side[equation_index] % characteristic:
                    inconsistent_equation = equation_index
                    break
                equations[equation_index] = None
                active_equation_count -= 1
                continue

            # Markowitz within the globally shortest equation.  The tie-breaks
            # are frozen by incidence count and coordinate index.
            pivot_unknown = min(
                equation,
                key=lambda unknown: (len(incidence[unknown]), unknown),
            )
        pivot_coefficient = equation[pivot_unknown]
        pivot_inverse = pow(pivot_coefficient, -1, characteristic)
        normalized_constant = right_hand_side[equation_index] * pivot_inverse % characteristic
        normalized_tail = tuple(
            sorted(
                (
                    unknown,
                    (-coefficient * pivot_inverse) % characteristic,
                )
                for unknown, coefficient in equation.items()
                if unknown != pivot_unknown
            )
        )
        pivot_records.append((pivot_unknown, normalized_constant, normalized_tail))
        if prescribed_pivots is not None:
            prescribed_position += 1
        length_at_pivot[len(equation)] += 1

        # The pivot row becomes a back-substitution record and is no longer an
        # active constraint.
        for unknown in tuple(equation):
            incidence[unknown].discard(equation_index)
        equations[equation_index] = None
        active_equation_count -= 1
        current_total_nonzeros -= len(equation)

        # Eliminate the pivot coordinate from every other active equation.
        affected = sorted(incidence[pivot_unknown])
        incidence[pivot_unknown].clear()
        for other_index in affected:
            other = equations[other_index]
            if other is None or pivot_unknown not in other:
                continue
            old_length = len(other)
            factor = other.pop(pivot_unknown)
            current_total_nonzeros -= 1
            right_hand_side[other_index] = (
                right_hand_side[other_index] - factor * normalized_constant
            ) % characteristic
            for unknown, substitution_coefficient in normalized_tail:
                old_value = other.get(unknown, 0)
                new_value = (
                    old_value + factor * substitution_coefficient
                ) % characteristic
                if new_value:
                    other[unknown] = new_value
                    if not old_value:
                        incidence[unknown].add(other_index)
                        current_total_nonzeros += 1
                        fill_added += 1
                elif old_value:
                    del other[unknown]
                    incidence[unknown].discard(other_index)
                    current_total_nonzeros -= 1
                    fill_deleted += 1
            update_count += 1
            maximum_active_equation_length = max(
                maximum_active_equation_length, len(other)
            )
            peak_total_nonzeros = max(peak_total_nonzeros, current_total_nonzeros)
            heapq.heappush(heap, (len(other), other_index))

        # Keep the deadline observable even during a long fill-producing pivot.
        if time.perf_counter() >= deadline:
            continue

    prescribed_finished = (
        prescribed_pivots is None
        or prescribed_position == len(prescribed_pivots)
    )
    if prescribed_finished and prescribed_pivots is not None:
        for equation_index, equation in enumerate(equations):
            if equation is None:
                continue
            if equation:
                fixed_gauge_failure = {
                    "prescribed_position": prescribed_position,
                    "reason": "nonzero coefficient row remains after all prescribed pivots",
                    "equation_index": equation_index,
                    "remaining_term_count": len(equation),
                }
                break
            if right_hand_side[equation_index] % characteristic:
                inconsistent_equation = equation_index
                break
            equations[equation_index] = None
            active_equation_count -= 1

    completed = (
        fixed_gauge_failure is None
        and (inconsistent_equation is not None or prescribed_finished)
        if prescribed_pivots is not None
        else inconsistent_equation is not None or not heap
    )
    consistent = inconsistent_equation is None and fixed_gauge_failure is None
    values = [0] * unknown_count
    if consistent and completed:
        for pivot_unknown, constant, tail in reversed(pivot_records):
            values[pivot_unknown] = (
                constant
                + sum(coefficient * values[unknown] for unknown, coefficient in tail)
            ) % characteristic

    return {
        "completed": completed,
        "timed_out": False,
        "consistent": consistent,
        "inconsistent_equation": inconsistent_equation,
        "fixed_gauge_failure": fixed_gauge_failure,
        "prescribed_pivot_count": (
            None if prescribed_pivots is None else len(prescribed_pivots)
        ),
        "completed_prescribed_pivots": prescribed_position,
        "values": values,
        "pivot_records": pivot_records,
        "pivot_count": len(pivot_records),
        "free_unknown_count": unknown_count - len(pivot_records),
        "active_equation_count": active_equation_count,
        "current_total_nonzeros": current_total_nonzeros,
        "peak_total_nonzeros": peak_total_nonzeros,
        "maximum_active_equation_length": maximum_active_equation_length,
        "update_count": update_count,
        "fill_added": fill_added,
        "fill_deleted": fill_deleted,
        "pivot_length_distribution": dict(sorted(length_at_pivot.items())),
        "solve_seconds": time.perf_counter() - started,
    }


def verify_sparse_system(
    equations: list[dict[int, int]],
    right_hand_side: list[int],
    values: list[int],
    characteristic: int,
) -> dict[str, object]:
    """Coefficientwise replay against a pristine copy of the sparse block."""

    started = time.perf_counter()
    mismatch_count = 0
    first_mismatch = None
    for equation_index, (equation, expected) in enumerate(
        zip(equations, right_hand_side, strict=True)
    ):
        actual = sum(
            coefficient * values[unknown] for unknown, coefficient in equation.items()
        ) % characteristic
        if actual != expected:
            mismatch_count += 1
            if first_mismatch is None:
                first_mismatch = {
                    "equation_index": equation_index,
                    "actual": actual,
                    "expected": expected,
                }
    return {
        "completed": True,
        "identity_zero": mismatch_count == 0,
        "mismatch_count": mismatch_count,
        "first_mismatch": first_mismatch,
        "replay_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=103)
    parser.add_argument("--timeout", type=float, default=280.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    parser.add_argument("--predecessor-certificate", type=Path)
    parser.add_argument("--gauge-from", type=Path)
    parser.add_argument(
        "--gauge-policy",
        choices=("ordered", "free-set"),
        default="ordered",
        help="follow the source pivot order or only freeze its free-coordinate set",
    )
    parser.add_argument(
        "--allow-quartic-reconstruction-prime",
        action="store_true",
        help="explicitly permit a prime already used to reconstruct h",
    )
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if (
        arguments.characteristic in RECONSTRUCTION_PRIMES
        and not arguments.allow_quartic_reconstruction_prime
    ):
        parser.error(
            "use an independent prime or pass --allow-quartic-reconstruction-prime "
            "and preserve that dependency"
        )
    if arguments.timeout <= 1:
        parser.error("timeout must exceed one second")

    started = time.perf_counter()
    deadline = started + arguments.timeout
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    predecessor_record = None
    if arguments.predecessor_certificate is not None:
        predecessor_path = arguments.predecessor_certificate
        if not predecessor_path.is_absolute():
            predecessor_path = campaign / predecessor_path
        predecessor_record = {
            "path": str(predecessor_path),
            "sha256": sha256_bytes(predecessor_path.read_bytes()),
        }
    block = build_character_block(campaign, arguments.characteristic)
    pristine_equations = [dict(equation) for equation in block["sparse_equations"]]
    pristine_rhs = list(block["right_hand_side"])
    gauge_source = None
    prescribed_pivots = None
    frozen_free_unknowns: list[int] = []
    removed_free_column_nonzeros = 0
    if arguments.gauge_from is not None:
        gauge_path = arguments.gauge_from
        if not gauge_path.is_absolute():
            gauge_path = campaign / gauge_path
        gauge_payload = json.loads(gauge_path.read_text(encoding="ascii"))
        if gauge_payload.get("schema") != (
            "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2"
        ):
            raise ValueError("--gauge-from requires a v2 sparse Macaulay certificate")
        descriptor_hash = sha256_bytes(
            json.dumps(block["descriptors"], separators=(",", ":")).encode("ascii")
        )
        monomial_hash = sha256_bytes(
            json.dumps(block["monomials"], separators=(",", ":")).encode("ascii")
        )
        if gauge_payload["row_descriptor_sha256"] != descriptor_hash:
            raise ValueError("gauge row-descriptor hash does not match this block")
        if gauge_payload["monomial_stream_sha256"] != monomial_hash:
            raise ValueError("gauge monomial-stream hash does not match this block")
        if gauge_payload["variable_names"] != [str(variable) for variable in block["variables"]]:
            raise ValueError("gauge variable order does not match this block")
        gauge_pivots = list(map(int, gauge_payload["pivot_unknown_indices"]))
        frozen_free_unknowns = list(map(int, gauge_payload["free_unknown_indices"]))
        if (
            len(set(gauge_pivots)) != len(gauge_pivots)
            or frozen_free_unknowns != sorted(set(frozen_free_unknowns))
            or set(gauge_pivots).isdisjoint(frozen_free_unknowns) is False
            or set(gauge_pivots) | set(frozen_free_unknowns)
            != set(range(len(block["descriptors"])))
        ):
            raise ValueError("gauge pivot/free coordinates do not partition the block")
        frozen_free_unknown_set = set(frozen_free_unknowns)
        for sparse_equation in block["sparse_equations"]:
            for free_unknown in tuple(sparse_equation):
                if free_unknown in frozen_free_unknown_set:
                    del sparse_equation[free_unknown]
                    removed_free_column_nonzeros += 1
        gauge_source = {
            "path": str(gauge_path),
            "sha256": sha256_bytes(gauge_path.read_bytes()),
            "characteristic": int(gauge_payload["characteristic"]),
            "pivot_unknown_indices_sha256": gauge_payload["pivot_unknown_indices_sha256"],
            "free_unknown_indices_sha256": gauge_payload["free_unknown_indices_sha256"],
            "pivot_count": len(gauge_pivots),
            "free_unknown_count": len(frozen_free_unknowns),
            "removed_free_column_nonzeros": removed_free_column_nonzeros,
            "policy": arguments.gauge_policy,
        }
        prescribed_pivots = gauge_pivots if arguments.gauge_policy == "ordered" else None
    solve = sparse_eliminate(
        block["sparse_equations"],
        block["right_hand_side"],
        len(block["descriptors"]),
        arguments.characteristic,
        deadline,
        prescribed_pivots=prescribed_pivots,
    )

    replay = {"completed": False, "identity_zero": False, "reason": "solve incomplete"}
    values = solve.get("values")
    if solve.get("completed") and solve.get("consistent") and values is not None:
        replay = verify_sparse_system(
            pristine_equations,
            pristine_rhs,
            values,
            arguments.characteristic,
        )

    actual_pivot_indices = [int(record[0]) for record in solve["pivot_records"]]
    gauge_coverage_verified = (
        gauge_source is None
        or (
            len(actual_pivot_indices) == gauge_source["pivot_count"]
            and set(actual_pivot_indices) == set(gauge_pivots)
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
        f"artifacts/j2-secant-r10-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
    )
    if not certificate_output.is_absolute():
        certificate_output = campaign / certificate_output

    solution_support = []
    if passed:
        pivot_unknown_indices = [
            int(record[0]) for record in solve["pivot_records"]
        ]
        pivot_unknown_set = set(pivot_unknown_indices)
        if len(pivot_unknown_set) != len(pivot_unknown_indices):
            raise AssertionError("a multiplier coordinate was pivoted more than once")
        free_unknown_indices = sorted(
            set(range(len(block["descriptors"]))) - pivot_unknown_set
        )
        if len(free_unknown_indices) != solve["free_unknown_count"]:
            raise AssertionError("the recorded free-coordinate count changed")
        pivot_profile_sha256 = sha256_bytes(
            json.dumps(pivot_unknown_indices, separators=(",", ":")).encode("ascii")
        )
        free_profile_sha256 = sha256_bytes(
            json.dumps(free_unknown_indices, separators=(",", ":")).encode("ascii")
        )
        for unknown_index, coefficient in enumerate(values):
            if not coefficient:
                continue
            generator_index, multiplier = block["descriptors"][unknown_index]
            solution_support.append(
                {
                    "unknown_index": unknown_index,
                    "normal_generator_position": generator_index,
                    "multiplier_exponents": list(multiplier),
                    "coefficient": coefficient,
                }
            )
        pivot_coordinate_order = (
            gauge_pivots
            if gauge_source is not None
            else prescribed_pivots
        )
        pivot_coordinate_vector = (
            None
            if pivot_coordinate_order is None
            else [int(values[index]) for index in pivot_coordinate_order]
        )
        pivot_coordinate_vector_sha256 = (
            None
            if pivot_coordinate_vector is None
            else sha256_bytes(
                json.dumps(pivot_coordinate_vector, separators=(",", ":")).encode("ascii")
            )
        )
        certificate_payload = {
            "schema": "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2",
            "characteristic": arguments.characteristic,
            "prime_roles": {
                "used_in_quartic_reconstruction": (
                    arguments.characteristic in RECONSTRUCTION_PRIMES
                ),
                "explicit_reuse_authorized": arguments.allow_quartic_reconstruction_prime,
            },
            "variable_names": [str(variable) for variable in block["variables"]],
            "character_modulus": CHARACTER_MODULUS,
            "character_weights": list(CHARACTER_WEIGHTS),
            "target_character_weight": block["target_weight"],
            "normal_generator_count": len(block["equations"]),
            "normal_equation_stream_sha256": digest(tuple(block["equations"])),
            "target_sha256": digest((block["target_expression"],)),
            "row_descriptor_sha256": sha256_bytes(
                json.dumps(block["descriptors"], separators=(",", ":")).encode("ascii")
            ),
            "monomial_stream_sha256": sha256_bytes(
                json.dumps(block["monomials"], separators=(",", ":")).encode("ascii")
            ),
            "deterministic_gauge": "all unpivoted multiplier coordinates set to zero",
            "pivot_unknown_indices": pivot_unknown_indices,
            "pivot_unknown_indices_sha256": pivot_profile_sha256,
            "free_unknown_indices": free_unknown_indices,
            "free_unknown_indices_sha256": free_profile_sha256,
            "gauge_source": gauge_source,
            "pivot_coordinate_vector": pivot_coordinate_vector,
            "pivot_coordinate_vector_sha256": pivot_coordinate_vector_sha256,
            "solution_support": solution_support,
            "claim_boundary": (
                "Exact identity over the displayed finite field only; this is not a "
                "characteristic-zero colon identity, a saturation certificate, or HC4."
            ),
        }
        certificate_text = json.dumps(certificate_payload, indent=2, sort_keys=True) + "\n"
        certificate_output.parent.mkdir(parents=True, exist_ok=True)
        certificate_output.write_text(certificate_text, encoding="ascii")
        certificate_sha256 = sha256_bytes(certificate_text.encode("ascii"))
    else:
        certificate_sha256 = None
        pivot_profile_sha256 = None
        free_profile_sha256 = None
        pivot_coordinate_vector_sha256 = None

    usage = resource.getrusage(resource.RUSAGE_SELF)
    status = (
        "PASS_EXACT_MODULAR_SPARSE_MACAULAY_COLON_IDENTITY"
        if passed
        else "TIMEOUT_SPARSE_MACAULAY_NO_MEMBERSHIP_DECISION"
        if solve.get("timed_out")
        else "INCOMPLETE_SPARSE_MACAULAY_COLON_IDENTITY"
    )
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay.v1",
        "status": status,
        "assurance": "exact finite-field polynomial identity only" if passed else "solver telemetry only",
        "characteristic": arguments.characteristic,
        "prime_roles": {
            "used_in_quartic_reconstruction": (
                arguments.characteristic in RECONSTRUCTION_PRIMES
            ),
            "explicit_reuse_authorized": arguments.allow_quartic_reconstruction_prime,
        },
        "algorithm": (
            "degree-eight character-five supported Macaulay block; deterministic "
            "sparse Gaussian elimination; free coordinates zero"
        ),
        "dimensions": {
            "unknown_multiplier_coordinates": len(block["descriptors"]),
            "monomial_equations": len(block["monomials"]),
            "matrix_nonzeros": block["nonzero_count"],
            "target_terms": len(block["target_polynomial"].terms()),
        },
        "generator_character_weights": block["generator_weights"],
        "target_character_weight": block["target_weight"],
        "quartic_reconstruction": block["reconstruction"],
        "solver": {
            key: value
            for key, value in solve.items()
            if key not in {"values", "pivot_records"}
        },
        "same_process_sparse_replay": replay,
        "solution_support_count": len(solution_support),
        "gauge_profile": (
            None
            if not passed
            else {
                "pivot_unknown_indices_sha256": pivot_profile_sha256,
                "free_unknown_indices_sha256": free_profile_sha256,
                "pivot_count": len(pivot_unknown_indices),
                "free_unknown_count": len(free_unknown_indices),
                "coefficient_dependent": prescribed_pivots is None,
                "gauge_source": gauge_source,
                "gauge_coverage_verified": gauge_coverage_verified,
                "pivot_coordinate_vector_sha256": pivot_coordinate_vector_sha256,
            }
        ),
        "certificate": (
            None
            if not passed
            else {
                "path": str(certificate_output),
                "sha256": certificate_sha256,
            }
        ),
        "predecessor_certificate": predecessor_record,
        "hashes": {
            "normal_equation_stream_sha256": digest(tuple(block["equations"])),
            "target_sha256": digest((block["target_expression"],)),
            "row_descriptor_sha256": sha256_bytes(
                json.dumps(block["descriptors"], separators=(",", ":")).encode("ascii")
            ),
            "monomial_stream_sha256": sha256_bytes(
                json.dumps(block["monomials"], separators=(",", ":")).encode("ascii")
            ),
            "source_sha256": sha256_bytes(script_path.read_bytes()),
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
            "A PASS proves only M*h in (F_1,...,F_17) over the displayed finite "
            "field. It does not prove the reconstructed QQ identity, determine the "
            "full colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-colon-identity-sparse-macaulay-p{arguments.characteristic}.json"
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
                "certificate": result["certificate"],
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
