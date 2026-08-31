#!/usr/bin/env python3
"""Audit the exact homogeneous reduction of the last secant ``j2`` chart.

This script proves only a reduction theorem.  It does not decide whether the
resulting homogeneous saturation is the unit ideal over characteristic zero.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest
from scout_five_support import g_coefficients
from scout_j2_secant_r10_homogeneous_saturation import (
    RETAINED_NORMAL_INDICES,
    homogeneous_saturation_system,
)


PIVOT_DATA = (
    (10, g_coefficients[4], -16),
    (9, g_coefficients[5], -16),
    (8, g_coefficients[7], 16),
    (7, g_coefficients[8], 16),
)


def expression_sha256(expression: sp.Expr) -> str:
    return hashlib.sha256(sp.srepr(sp.expand(expression)).encode("utf-8")).hexdigest()


def main() -> int:
    started = time.perf_counter()
    equations, variables, leading_form, open_factor = homogeneous_saturation_system()
    indexed_equations = dict(zip(RETAINED_NORMAL_INDICES, equations, strict=True))

    f9 = sp.Symbol("f9")
    f10 = sp.Symbol("f10")
    if sp.expand(open_factor - f9 * f10 * leading_form) != 0:
        raise AssertionError("the open factor does not split as f9*f10*u")

    equation_checks = []
    for index, equation in zip(RETAINED_NORMAL_INDICES, equations, strict=True):
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        monomial_degrees = sorted({sum(monomial) for monomial, _ in polynomial.terms()})
        if monomial_degrees != [3]:
            raise AssertionError(f"normal equation {index} is not homogeneous cubic")
        equation_checks.append(
            {
                "normal_index": index,
                "term_count": len(polynomial.terms()),
                "monomial_total_degrees": monomial_degrees,
                "sha256": expression_sha256(equation),
            }
        )

    pivots = [variable for _, variable, _ in PIVOT_DATA]
    pivot_checks = []
    for position, (index, pivot, scalar) in enumerate(PIVOT_DATA):
        equation = indexed_equations[index]
        polynomial = sp.Poly(equation, pivot, domain="EX")
        if polynomial.degree() != 1:
            raise AssertionError(f"normal equation {index} is not linear in {pivot}")
        coefficient = sp.expand(polynomial.coeff_monomial(pivot))
        remainder = sp.expand(polynomial.coeff_monomial(1))
        if sp.expand(coefficient - scalar * leading_form) != 0:
            raise AssertionError(f"unexpected pivot coefficient at normal equation {index}")
        forbidden = [str(variable) for variable in pivots[position:] if remainder.has(variable)]
        if forbidden:
            raise AssertionError(
                f"normal equation {index} has a forward pivot dependency: {forbidden}"
            )
        if sp.expand(equation - (coefficient * pivot + remainder)) != 0:
            raise AssertionError(f"linear reconstruction failed at normal equation {index}")
        pivot_checks.append(
            {
                "order": position + 1,
                "normal_index": index,
                "pivot_variable": str(pivot),
                "coefficient": str(sp.factor(coefficient)),
                "coefficient_scalar_times_u": scalar,
                "solution_in_localization": f"{pivot} = -R_{index}/({scalar}*u)",
                "remainder_term_count": len(sp.Poly(remainder, *variables).terms()),
                "remainder_sha256": expression_sha256(remainder),
                "depends_on_earlier_pivots": [
                    str(variable) for variable in pivots[:position] if remainder.has(variable)
                ],
                "depends_on_current_or_later_pivots": forbidden,
                "linear_reconstruction_exact": True,
            }
        )

    remaining_variables = [str(variable) for variable in variables if variable not in pivots]
    remaining_normal_indices = [
        index for index in RETAINED_NORMAL_INDICES if index not in {row[0] for row in PIVOT_DATA}
    ]
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4.decimic-j2-secant-r10-degree6-homogeneous-reduction.v1",
        "status": "PASS_EXACT_SECANT_DEGREE6_HOMOGENEOUS_REDUCTION",
        "assurance": "exact symbolic identity audit over QQ",
        "orbit": "secant",
        "chart": "r=10 and f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "branch": "degree_6",
        "ambient_ring": "QQ[f3,f4,f5,f6,f7,f8,f10,g0,...,g9,f9]",
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_generator_count": len(equations),
        "normal_generator_degree": 3,
        "retained_affine_normal_indices": list(RETAINED_NORMAL_INDICES),
        "equation_checks": equation_checks,
        "u": str(leading_form),
        "open_factor_M": str(open_factor),
        "open_factor_factorization": "M=f9*f10*u",
        "projective_open_statement": "Proj(V(I)) intersect D(M) is empty",
        "equivalent_remaining_test": "I:M^infinity=(1), equivalently M lies in radical(I)",
        "dehomogenization": "f9=1 recovers the 17 retained affine normal equations",
        "pivot_order": [str(variable) for variable in pivots],
        "pivot_checks": pivot_checks,
        "localized_triangular_reduction": {
            "eliminated_variable_count": len(pivots),
            "remaining_variable_count": len(remaining_variables),
            "remaining_variables": remaining_variables,
            "remaining_generator_count_after_using_pivots": len(remaining_normal_indices),
            "remaining_normal_indices": remaining_normal_indices,
            "statement": (
                "Because u is a unit on D(M), the four displayed equations eliminate "
                "g4,g5,g7,g8 successively without adding a branch."
            ),
        },
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": expression_sha256(open_factor),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/audit_j2_secant_r10_degree6_homogeneous_reduction.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_j2_secant_r10_homogeneous_saturation.py": hashlib.sha256(
                (script_path.parent / "scout_j2_secant_r10_homogeneous_saturation.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "This receipt proves the homogeneous/localized equivalence and four exact "
            "unit-linear eliminations. It does not prove I:M^infinity=(1), secant j2 "
            "containment, polynomial-open closure, or HC4."
        ),
    }
    output = campaign / "receipts/hsop-j2-secant-r10-degree6-homogeneous-reduction.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "normal_generator_count": len(equations),
                "pivot_order": result["pivot_order"],
                "remaining_variable_count": len(remaining_variables),
                "remaining_generator_count": len(remaining_normal_indices),
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
