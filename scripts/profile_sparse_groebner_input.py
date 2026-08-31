#!/usr/bin/env python3
"""Profile an exported sparse rational system and apply safe linear eliminations.

Only equations of the form ``c*x + r`` with nonzero rational constant ``c``
are used for elimination.  Consequently every recorded substitution is an
identity over Q and requires no extra open chart.  Linear equations whose
coefficient depends on other variables are reported separately as possible
future chart splits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(expression: sp.Expr) -> str:
    return str(sp.factor(expression)).replace("**", "^")


def decode_equation(
    encoded: list[dict[str, object]], variables: tuple[sp.Symbol, ...]
) -> sp.Expr:
    expression = sp.Integer(0)
    for term in encoded:
        numerator = sp.Integer(str(term["numerator"]))
        denominator = sp.Integer(str(term["denominator"]))
        exponents = tuple(int(value) for value in term["exponents"])
        if len(exponents) != len(variables):
            raise AssertionError("term exponent vector has the wrong length")
        monomial = sp.prod(
            variable**exponent
            for variable, exponent in zip(variables, exponents)
        )
        expression += numerator * monomial / denominator
    return sp.expand(expression)


def total_degree(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> int:
    if expression == 0:
        return -1
    return int(sp.Poly(expression, *variables, domain=sp.QQ).total_degree())


def term_count(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> int:
    if expression == 0:
        return 0
    return len(sp.Poly(expression, *variables, domain=sp.QQ).terms())


def constant_linear_candidates(
    equations: list[sp.Expr], variables: tuple[sp.Symbol, ...]
) -> list[tuple[int, sp.Symbol, sp.Rational, sp.Expr]]:
    candidates = []
    variable_set = set(variables)
    for equation_index, equation in enumerate(equations):
        for variable in variables:
            polynomial = sp.Poly(equation, variable)
            if polynomial.degree() != 1:
                continue
            coefficient = sp.expand(polynomial.coeff_monomial(variable))
            if coefficient.free_symbols & variable_set:
                continue
            coefficient = sp.Rational(coefficient)
            if coefficient == 0:
                continue
            remainder = sp.expand(polynomial.coeff_monomial(1))
            candidates.append((equation_index, variable, coefficient, remainder))
    return candidates


def chart_linear_candidates(
    equations: list[sp.Expr], variables: tuple[sp.Symbol, ...]
) -> list[dict[str, object]]:
    rows = []
    variable_set = set(variables)
    for equation_index, equation in enumerate(equations):
        for variable in variables:
            polynomial = sp.Poly(equation, variable)
            if polynomial.degree() != 1:
                continue
            coefficient = sp.expand(polynomial.coeff_monomial(variable))
            if not (coefficient.free_symbols & variable_set):
                continue
            remainder = sp.expand(polynomial.coeff_monomial(1))
            rows.append(
                {
                    "equation_index": equation_index,
                    "variable": str(variable),
                    "coefficient": render(coefficient),
                    "coefficient_total_degree": total_degree(coefficient, variables),
                    "remainder_total_degree": total_degree(remainder, variables),
                    "coefficient_term_count": term_count(coefficient, variables),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["coefficient_total_degree"],
            row["coefficient_term_count"],
            row["remainder_total_degree"],
            row["equation_index"],
            row["variable"],
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    input_path = arguments.input.resolve()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    variable_names = tuple(str(name) for name in data["variable_names"])
    variables = tuple(sp.symbols(" ".join(variable_names), seq=True))
    equations = [decode_equation(row, variables) for row in data["equations"]]
    original_equations = list(equations)
    active_variables = list(variables)
    eliminations: list[dict[str, object]] = []

    while True:
        candidates = constant_linear_candidates(equations, tuple(active_variables))
        if not candidates:
            break
        equation_index, variable, coefficient, remainder = min(
            candidates,
            key=lambda row: (
                term_count(row[3], tuple(active_variables)),
                total_degree(row[3], tuple(active_variables)),
                row[0],
                str(row[1]),
            ),
        )
        replacement = sp.expand(-remainder / coefficient)
        eliminations.append(
            {
                "step": len(eliminations) + 1,
                "equation_index_at_step": equation_index,
                "variable": str(variable),
                "constant_coefficient": str(coefficient),
                "replacement": render(replacement),
                "replacement_total_degree": total_degree(
                    replacement, tuple(active_variables)
                ),
                "replacement_term_count": term_count(
                    replacement, tuple(active_variables)
                ),
            }
        )
        equations = [sp.expand(equation.subs(variable, replacement)) for equation in equations]
        equations = [equation for equation in equations if equation != 0]
        active_variables.remove(variable)

    active_tuple = tuple(active_variables)
    reduced_profile = [
        {
            "equation_index": index,
            "total_degree": total_degree(equation, active_tuple),
            "term_count": term_count(equation, active_tuple),
            "support": sorted(str(symbol) for symbol in equation.free_symbols),
            "factorization": render(equation),
        }
        for index, equation in enumerate(equations)
    ]
    occurrence_counts = {
        str(variable): sum(bool(equation.has(variable)) for equation in equations)
        for variable in active_tuple
    }
    result = {
        "schema": "sparse-groebner-structural-profile-v1",
        "status": "PASS_EXACT_STRUCTURAL_PROFILE",
        "input": str(input_path),
        "input_sha256": sha256(input_path),
        "original_variable_count": len(variables),
        "original_equation_count": len(original_equations),
        "original_maximum_total_degree": max(
            total_degree(equation, variables) for equation in original_equations
        ),
        "safe_constant_linear_eliminations": eliminations,
        "safe_elimination_count": len(eliminations),
        "remaining_variable_count": len(active_tuple),
        "remaining_variables": [str(variable) for variable in active_tuple],
        "remaining_equation_count": len(equations),
        "remaining_maximum_total_degree": max(
            (total_degree(equation, active_tuple) for equation in equations),
            default=-1,
        ),
        "remaining_occurrence_counts": occurrence_counts,
        "remaining_equation_profile": reduced_profile,
        "nonconstant_linear_chart_candidates": chart_linear_candidates(
            equations, active_tuple
        ),
        "checks": {
            "only_nonzero_rational_linear_coefficients_eliminated": True,
            "no_localization_assumption_added": True,
            "all_reduced_equations_exact_over_Q": True,
        },
        "claim_boundary": (
            "this is an exact presentation reduction and chart-scouting receipt; "
            "it is not a unit-ideal certificate and does not prove emptiness"
        ),
    }

    output_path = arguments.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
