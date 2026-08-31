#!/usr/bin/env python3
"""Exact Smith-form audit of the hidden grading in the last secant j2 chart.

For every retained homogeneous cubic, subtract one monomial exponent vector
from all of the others.  The resulting integer rows generate the lattice of
relations that every termwise grading must annihilate.  Its Smith normal form
therefore describes the universal abelian grading group of the displayed
monomial supports.

This script requires SageMath and performs all lattice calculations over ZZ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp
from sage.all import ZZ, matrix, vector
from sage.env import SAGE_VERSION

from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    RETAINED_NORMAL_INDICES,
    homogeneous_saturation_system,
)


EXPECTED_CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
EXPECTED_GENERATOR_WEIGHTS = (5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 7, 9, 10, 11, 0, 1)


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def expression_sha256(expression: sp.Expr) -> str:
    return hashlib.sha256(sp.srepr(sp.expand(expression)).encode("utf-8")).hexdigest()


def term_weight(exponents: tuple[int, ...], weights: tuple[int, ...], modulus: int) -> int:
    return sum(exponent * weight for exponent, weight in zip(exponents, weights, strict=True)) % modulus


def normalized_torsion_character(
    smith_lift: tuple[int, ...], free_lift: tuple[int, ...], modulus: int
) -> tuple[tuple[int, ...], dict[str, int]]:
    """Normalize a Smith torsion lift by weights(f3)=0 and weights(f4)=1."""

    if free_lift not in ((1,) * len(free_lift), (-1,) * len(free_lift)):
        raise AssertionError("the free Smith direction is not total degree")
    total_degree_sign = free_lift[0]
    shift = (-smith_lift[0] * total_degree_sign) % modulus
    shifted = tuple(
        (entry + shift * free_entry) % modulus
        for entry, free_entry in zip(smith_lift, free_lift, strict=True)
    )
    anchor = shifted[1]
    if math.gcd(anchor, modulus) != 1:
        raise AssertionError("the f4 anchor does not generate the torsion character")
    unit = pow(anchor, -1, modulus)
    normalized = tuple((unit * entry) % modulus for entry in shifted)
    return normalized, {
        "total_degree_shift_multiple_modulus": int(shift),
        "torsion_unit_multiplier_modulus": int(unit),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-secant-r10-z12-grading-exact.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()

    equations, variables, leading_form, open_factor = homogeneous_saturation_system()
    if len(equations) != len(RETAINED_NORMAL_INDICES):
        raise AssertionError("retained normal-index dictionary changed")
    if len(variables) != len(EXPECTED_CHARACTER_WEIGHTS):
        raise AssertionError("ambient variable count changed")

    exponent_terms: list[list[tuple[int, ...]]] = []
    term_counts: list[int] = []
    difference_rows: list[tuple[int, ...]] = []
    difference_row_counts: list[int] = []
    for normal_index, equation in zip(RETAINED_NORMAL_INDICES, equations, strict=True):
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        terms = [tuple(map(int, exponents)) for exponents, _ in polynomial.terms()]
        if not terms:
            raise AssertionError(f"normal equation {normal_index} is zero")
        if {sum(exponents) for exponents in terms} != {3}:
            raise AssertionError(f"normal equation {normal_index} is not a homogeneous cubic")
        baseline = terms[0]
        rows = [
            tuple(left - right for left, right in zip(exponents, baseline, strict=True))
            for exponents in terms[1:]
        ]
        exponent_terms.append(terms)
        term_counts.append(len(terms))
        difference_rows.extend(rows)
        difference_row_counts.append(len(rows))

    relation_matrix = matrix(ZZ, difference_rows)
    if relation_matrix.ncols() != len(variables):
        raise AssertionError("relation matrix has the wrong number of columns")
    smith_diagonal, left_transform, right_transform = relation_matrix.smith_form()
    smith_identity = left_transform * relation_matrix * right_transform == smith_diagonal
    if not smith_identity:
        raise AssertionError("Smith transformation identity failed")
    left_determinant = int(left_transform.det())
    right_determinant = int(right_transform.det())
    if abs(left_determinant) != 1 or abs(right_determinant) != 1:
        raise AssertionError("Smith transformations are not unimodular")

    diagonal = tuple(
        int(smith_diagonal[index, index])
        for index in range(min(smith_diagonal.nrows(), smith_diagonal.ncols()))
    )
    expected_diagonal = (1,) * 16 + (12, 0)
    if diagonal != expected_diagonal:
        raise AssertionError(f"unexpected Smith diagonal: {diagonal}")
    if relation_matrix.rank() != 17:
        raise AssertionError("relation lattice does not have rank 17")

    torsion_index = next(index for index, entry in enumerate(diagonal) if abs(entry) > 1)
    free_index = next(index for index, entry in enumerate(diagonal) if entry == 0)
    torsion_modulus = abs(diagonal[torsion_index])
    raw_torsion_lift = tuple(int(entry) for entry in right_transform.column(torsion_index))
    free_lift = tuple(int(entry) for entry in right_transform.column(free_index))
    character_weights, normalization = normalized_torsion_character(
        raw_torsion_lift, free_lift, torsion_modulus
    )
    if character_weights != EXPECTED_CHARACTER_WEIGHTS:
        raise AssertionError(
            f"derived character {character_weights} differs from the frozen character"
        )
    character_vector = vector(ZZ, character_weights)
    pairings = tuple(int(entry) for entry in relation_matrix * character_vector)
    if any(entry % torsion_modulus for entry in pairings):
        raise AssertionError("derived character does not annihilate the relation lattice")
    if math.gcd(torsion_modulus, *character_weights) != 1:
        raise AssertionError("derived character does not have exact order 12")

    generator_checks = []
    generator_weights: list[int] = []
    for normal_index, equation, terms in zip(
        RETAINED_NORMAL_INDICES, equations, exponent_terms, strict=True
    ):
        weights = sorted(
            {term_weight(exponents, character_weights, torsion_modulus) for exponents in terms}
        )
        if len(weights) != 1:
            raise AssertionError(f"normal equation {normal_index} is not character homogeneous")
        generator_weights.append(weights[0])
        generator_checks.append(
            {
                "normal_index": int(normal_index),
                "term_count": len(terms),
                "total_degree": 3,
                "character_weight_mod_12": weights[0],
                "expression_sha256": expression_sha256(equation),
            }
        )
    if tuple(generator_weights) != EXPECTED_GENERATOR_WEIGHTS:
        raise AssertionError("generator character weights changed")

    leading_terms = [
        tuple(map(int, exponents))
        for exponents, _ in sp.Poly(leading_form, *variables, domain=sp.QQ).terms()
    ]
    leading_weights = sorted(
        {term_weight(exponents, character_weights, torsion_modulus) for exponents in leading_terms}
    )
    if leading_weights != [0]:
        raise AssertionError("u=2*f9^2+5*f10*g0 does not have character zero")
    open_terms = [
        tuple(map(int, exponents))
        for exponents, _ in sp.Poly(open_factor, *variables, domain=sp.QQ).terms()
    ]
    open_weights = sorted(
        {term_weight(exponents, character_weights, torsion_modulus) for exponents in open_terms}
    )
    if open_weights != [1]:
        raise AssertionError("M=f9*f10*u does not have character one")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    result = {
        "schema": "hc4.decimic-j2-secant-r10-z12-grading-smith-audit.v1",
        "status": "PASS_EXACT_Z12_GRADING_SMITH_AUDIT",
        "assurance": "exact integer lattice and Smith-normal-form audit over ZZ",
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "branch": "degree_6",
        "sage_version": SAGE_VERSION,
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_generator_count": len(equations),
        "retained_affine_normal_indices": list(RETAINED_NORMAL_INDICES),
        "generator_term_counts": term_counts,
        "difference_rows_per_generator": difference_row_counts,
        "monomial_difference_lattice": {
            "construction": (
                "within each cubic, every nonbaseline exponent vector minus the first "
                "exponent vector returned by SymPy Poly.terms()"
            ),
            "row_count": int(relation_matrix.nrows()),
            "column_count": int(relation_matrix.ncols()),
            "rank_over_ZZ": int(relation_matrix.rank()),
            "row_stream_sha256": canonical_sha256(difference_rows),
        },
        "smith_normal_form": {
            "diagonal": list(diagonal),
            "nonzero_invariant_factors": [entry for entry in diagonal if entry],
            "identity_left_times_A_times_right_equals_diagonal": smith_identity,
            "left_transform_determinant": left_determinant,
            "right_transform_determinant": right_determinant,
            "right_transform_sha256": canonical_sha256(
                [[int(entry) for entry in row] for row in right_transform.rows()]
            ),
            "quotient_of_exponent_lattice_by_term_differences": "Z direct_sum Z/12Z",
            "free_rank": 1,
            "torsion_invariant_factors": [12],
        },
        "derived_grading": {
            "raw_torsion_smith_lift": list(raw_torsion_lift),
            "free_smith_lift": list(free_lift),
            "free_lift_is_total_degree": free_lift == (1,) * len(free_lift),
            "normalization": {
                "conditions": "weight(f3)=0 and weight(f4)=1",
                **normalization,
            },
            "character_modulus": torsion_modulus,
            "variable_character_weights": list(character_weights),
            "character_has_exact_order_12": True,
            "all_difference_pairings_divisible_by_12": True,
            "difference_pairing_quotients_sha256": canonical_sha256(
                [entry // torsion_modulus for entry in pairings]
            ),
        },
        "generator_checks": generator_checks,
        "generator_character_weights": generator_weights,
        "all_generators_total_degree_three": True,
        "all_generators_character_homogeneous": True,
        "leading_form_u": str(leading_form),
        "leading_form_character_weight_mod_12": leading_weights[0],
        "open_factor_M": str(open_factor),
        "open_factor_total_degree": int(
            sp.Poly(open_factor, *variables, domain=sp.QQ).total_degree()
        ),
        "open_factor_character_weight_mod_12": open_weights[0],
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": expression_sha256(open_factor),
        "source_sha256": {
            "scripts/audit_j2_secant_r10_z12_grading.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_j2_secant_r10_homogeneous_saturation.py": hashlib.sha256(
                (script_path.parent / "scout_j2_secant_r10_homogeneous_saturation.py").read_bytes()
            ).hexdigest(),
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "This exact ZZ receipt proves that the universal abelian grading quotient of "
            "the displayed 17 cubic monomial supports is Z direct_sum Z/12Z, derives the "
            "stated character, and verifies that u has character 0 and M has character 1. "
            "It justifies the character-block decomposition only. It does not prove "
            "M lies in radical(I), I:M^infinity=(1), secant nullcone containment, "
            "polynomial-open closure, or HC4."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "relation_matrix_shape": [
                    int(relation_matrix.nrows()),
                    int(relation_matrix.ncols()),
                ],
                "smith_diagonal": list(diagonal),
                "variable_character_weights": list(character_weights),
                "generator_character_weights": generator_weights,
                "open_factor_character_weight_mod_12": open_weights[0],
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
