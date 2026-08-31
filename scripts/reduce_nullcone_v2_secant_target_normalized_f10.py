#!/usr/bin/env python3
"""Eliminate f10 on one exact coefficient chart of V2_highest = 1.

The primitive cubic V2 highest coordinate is linear in f10.  This script
splits on the primitive coefficient P of f10.  On D(P), f10 is eliminated and
all 55 normal equations are exported as cleared numerators in 20 variables.
The complementary branch P=0 is retained explicitly with the residual target
equation B-1=0.  No Groebner calculation is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, render
from scout_five_support import g_coefficients
from scout_nullcone_cubic_families import raw_coefficient_family


PRIME = 101


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modular_expression(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> sp.Expr:
    return sp.expand(sp.Poly(expression, *variables, modulus=PRIME).as_expr())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v2-secant-target-normalized-f10-reduction.json"),
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/nullcone-v2-secant-target-normalized-f10-reduction.json"),
    )
    parser.add_argument("--symbolic-cap-seconds", type=float, default=60.0)
    arguments = parser.parse_args()
    if arguments.symbolic_cap_seconds != 60.0:
        parser.error("the frozen symbolic cap is exactly 60 seconds")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    artifact = arguments.artifact if arguments.artifact.is_absolute() else campaign / arguments.artifact

    normalization_path = campaign / "receipts/nullcone-v2-secant-torus-normalization.json"
    normalization = json.loads(normalization_path.read_text(encoding="utf-8"))
    if normalization.get("status") != "PASS_EXACT_SECANT_V2_HIGHEST_TORUS_NORMALIZATION":
        raise AssertionError("the V2 secant normalization receipt is not passing")

    equations, equation_build_seconds = normal_equations("secant")
    variables = f_coefficients + g_coefficients
    pivot = f_coefficients[10]
    remaining_variables = tuple(variable for variable in variables if variable != pivot)
    target = sp.expand(raw_coefficient_family("V2"))
    if digest(tuple(equations)) != normalization.get("normal_equation_stream_sha256"):
        raise AssertionError("the normal-equation stream drifted")
    if digest((target,)) != normalization.get("target_sha256"):
        raise AssertionError("the V2 target drifted")
    if sp.Poly(target, *variables).degree(pivot) != 1:
        raise AssertionError("V2 highest is no longer linear in f10")

    pivot_coefficient = sp.expand(sp.diff(target, pivot))
    coefficient_content = math.gcd(
        *(abs(int(value)) for value in sp.Poly(pivot_coefficient, *f_coefficients).coeffs())
    )
    primitive_pivot = sp.expand(pivot_coefficient / coefficient_content)
    residual_target = sp.expand(target - pivot_coefficient * pivot)
    if pivot in primitive_pivot.free_symbols or pivot in residual_target.free_symbols:
        raise AssertionError("the f10 coefficient split is not pivot-free")
    if sp.expand(
        target - coefficient_content * primitive_pivot * pivot - residual_target
    ) != 0:
        raise AssertionError("the target coefficient split failed")
    if coefficient_content % PRIME == 0:
        raise AssertionError("the coefficient content is not a unit modulo 101")

    pivot_solution = sp.cancel(
        (1 - residual_target) / (coefficient_content * primitive_pivot)
    )
    if sp.cancel((target - 1).subs(pivot, pivot_solution)) != 0:
        raise AssertionError("the f10 recovery formula does not solve V2_highest=1")

    reduced_numerators: list[sp.Expr] = []
    denominators: list[sp.Expr] = []
    denominator_rows: list[dict[str, object]] = []
    original_pivot_degrees: list[int] = []
    for index, equation in enumerate(equations):
        pivot_degree = sp.Poly(equation, *variables).degree(pivot)
        if pivot_degree not in (0, 1):
            raise AssertionError(f"normal equation {index} has f10 degree {pivot_degree}")
        substituted = sp.cancel(equation.subs(pivot, pivot_solution))
        numerator, denominator = map(sp.expand, sp.fraction(substituted))
        if pivot in numerator.free_symbols or pivot in denominator.free_symbols:
            raise AssertionError(f"f10 survived reduced equation {index}")
        if sp.cancel(substituted - numerator / denominator) != 0:
            raise AssertionError(f"fraction replay failed at equation {index}")
        quotient = sp.cancel(
            denominator
            / (coefficient_content * primitive_pivot) ** pivot_degree
        )
        if not quotient.is_Rational:
            raise AssertionError(
                f"equation {index} acquired a denominator outside the P-open: {quotient}"
            )
        quotient_numerator, quotient_denominator = sp.fraction(quotient)
        if int(quotient_numerator) % PRIME == 0 or int(quotient_denominator) % PRIME == 0:
            raise AssertionError(
                f"equation {index} clears by a scalar nonunit modulo 101"
            )
        reduced_numerators.append(numerator)
        denominators.append(denominator)
        original_pivot_degrees.append(pivot_degree)
        denominator_rows.append(
            {
                "equation_index": index,
                "f10_degree": pivot_degree,
                "denominator": render(denominator),
                "denominator_over_336P_to_degree": str(quotient),
            }
        )
        if time.perf_counter() - started > arguments.symbolic_cap_seconds:
            raise TimeoutError("the exact symbolic reduction exceeded its 60-second cap")

    # The complementary branch is retained, not inferred away:
    # H-1 = 336*P*f10 + (B-1), so on P=0 it is exactly B-1=0.
    boundary_identity = sp.expand(
        target
        - 1
        - coefficient_content * primitive_pivot * pivot
        - (residual_target - 1)
    )
    if boundary_identity != 0:
        raise AssertionError("the P=0 boundary target identity failed")

    modular_reduced = [
        modular_expression(expression, remaining_variables)
        for expression in reduced_numerators
    ]
    rational_term_counts = [
        len(sp.Poly(expression, *remaining_variables).terms())
        for expression in reduced_numerators
    ]
    modular_term_counts = [
        len(sp.Poly(expression, *remaining_variables, modulus=PRIME).terms())
        for expression in reduced_numerators
    ]
    symbolic_wall_seconds = time.perf_counter() - started
    if symbolic_wall_seconds > arguments.symbolic_cap_seconds:
        raise TimeoutError("the exact symbolic reduction exceeded its 60-second cap")

    artifact_payload = {
        "schema": "hc4.decimic-nullcone-v2-secant-f10-open-reduction-artifact.v1",
        "field": "QQ with an audited reduction modulo GF(101)",
        "pivot_variable": str(pivot),
        "coefficient_content": coefficient_content,
        "open_polynomial": render(primitive_pivot),
        "residual_target": render(residual_target),
        "pivot_solution_on_open": render(pivot_solution),
        "remaining_variables": [str(variable) for variable in remaining_variables],
        "reduced_normal_equation_numerators": [
            render(expression) for expression in reduced_numerators
        ],
        "denominator_rows": denominator_rows,
        "boundary_branch_generators": [
            render(primitive_pivot),
            render(residual_target - 1),
        ],
        "branch_cover": [
            "D(P): eliminate f10=(1-B)/(336*P)",
            "V(P): retain the 55 original equations together with P=0 and B-1=0",
        ],
    }
    artifact_rendered = json.dumps(artifact_payload, indent=2, sort_keys=True) + "\n"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(artifact_rendered, encoding="utf-8")

    result = {
        "schema": "hc4.decimic-nullcone-v2-secant-f10-open-reduction.v1",
        "status": "PASS_EXACT_SECANT_V2_F10_OPEN_ELIMINATION_WITH_BOUNDARY_RETAINED",
        "orbit": "secant",
        "family": "V2",
        "coordinate": "highest",
        "input_statement": "55 secant normal equations plus V2_highest-1",
        "field_scope": ["QQ", "GF(101)"],
        "pivot": {
            "variable": str(pivot),
            "coefficient_content": coefficient_content,
            "coefficient_content_mod_101": coefficient_content % PRIME,
            "primitive_open_polynomial": render(primitive_pivot),
            "primitive_open_polynomial_sha256": digest((primitive_pivot,)),
            "residual_target": render(residual_target),
            "residual_target_sha256": digest((residual_target,)),
            "recovery_formula": render(pivot_solution),
        },
        "open_branch": {
            "condition": "P!=0",
            "variable_count_before": len(variables),
            "variable_count_after": len(remaining_variables),
            "eliminated_variable": str(pivot),
            "normal_equation_count": len(reduced_numerators),
            "reduced_numerator_stream_sha256_qq": digest(tuple(reduced_numerators)),
            "reduced_numerator_stream_sha256_gf101": digest(tuple(modular_reduced)),
            "rational_term_counts": rational_term_counts,
            "modular_term_counts": modular_term_counts,
            "rational_total_terms": sum(rational_term_counts),
            "modular_total_terms": sum(modular_term_counts),
            "maximum_rational_terms_in_one_equation": max(rational_term_counts),
            "all_denominators_supported_on_P": True,
            "all_denominator_scalars_units_mod_101": True,
        },
        "boundary_branch": {
            "condition": "P=0",
            "retained_generators": "the 55 original normal equations, P, and B-1",
            "variable_count": len(variables),
            "generator_count": len(equations) + 2,
            "target_reduction_identity": "V2_highest-1 = 336*P*f10 + (B-1)",
            "discarded": False,
        },
        "exact_branch_cover": "D(P) union V(P) is the full normalized target hypersurface",
        "artifact": {
            "path": str(artifact),
            "sha256": sha256(artifact),
            "byte_count": artifact.stat().st_size,
        },
        "hashes": {
            "normal_equation_stream_sha256": digest(tuple(equations)),
            "target_sha256": digest((target,)),
            "normalization_receipt_sha256": sha256(normalization_path),
        },
        "timings": {
            "symbolic_cap_seconds": arguments.symbolic_cap_seconds,
            "equation_build_seconds": equation_build_seconds,
            "symbolic_wall_seconds": symbolic_wall_seconds,
        },
        "checks": {
            "target_linear_in_f10": True,
            "primitive_open_polynomial": True,
            "content_unit_mod_101": True,
            "recovery_formula_exact": True,
            "all_55_substitutions_replayed": True,
            "all_denominators_are_P_powers_times_units": True,
            "boundary_branch_retained": True,
            "variable_count_lowered_on_open": True,
            "no_groebner_solver_run": True,
        },
        "source_sha256": {
            "scripts/reduce_nullcone_v2_secant_target_normalized_f10.py": sha256(script_path),
            "scripts/certify_nullcone_v2_secant_torus_normalization.py": sha256(
                script_path.parent / "certify_nullcone_v2_secant_torus_normalization.py"
            ),
            "scripts/scout_nullcone_cubic_families.py": sha256(
                script_path.parent / "scout_nullcone_cubic_families.py"
            ),
            "scripts/scout_decimic_nullcone_hsop.py": sha256(
                script_path.parent / "scout_decimic_nullcone_hsop.py"
            ),
        },
        "claim_boundary": (
            "This receipt proves only an exact two-branch algebraic reduction of "
            "the normalized V2-highest chart. It does not prove either branch empty, "
            "produce a modular survivor, prove the other V2 coordinates, establish "
            "secant nullcone containment, lift to the polynomial problem, or prove HC4."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
