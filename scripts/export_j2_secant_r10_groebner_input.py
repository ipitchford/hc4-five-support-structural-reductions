#!/usr/bin/env python3
"""Export one secant ``r=10`` branch as exact sparse rational polynomials.

The JSON format deliberately contains integer numerators, integer
denominators, and exponent vectors.  This avoids making either Julia or an
independent verifier trust a textual polynomial parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from certify_j2_secant_r10_tail_branch import f9_inverse, tail_branches
from scout_decimic_nullcone_hsop import digest, f_coefficients


CHARTS = ("f9_laurent", "f10_f9_zero", "f10_f9_open")


def sparse_terms(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> list[dict[str, object]]:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    terms = []
    for exponents, coefficient in polynomial.terms():
        terms.append(
            {
                "numerator": str(coefficient.p),
                "denominator": str(coefficient.q),
                "exponents": list(exponents),
            }
        )
    return terms


def selected_branch(
    chart: str, branch_name: str, extra_indices: tuple[int, ...]
) -> tuple[list[sp.Expr], tuple[sp.Symbol, ...], dict[str, object]]:
    if chart == "f9_laurent":
        if extra_indices:
            raise ValueError("extra indices are only supported on the f10_f9_zero chart")
        _, _, retained_indices, _, branches = laurent_branches()
        branch = branches[branch_name]
        return (
            list(branch["equations"]),
            tuple(branch["variables"]),
            {
                "normalization": "f9=1; f10*f10inv=1",
                "retained_normal_equation_indices": list(retained_indices),
                "substitutions": {
                    str(key): str(value) for key, value in branch["substitutions"].items()
                },
                "leading_form": (
                    str(branch["leading_form"])
                    if branch["leading_form"] is not None
                    else None
                ),
            },
        )

    if chart == "f10_f9_zero":
        _, _, retained_indices, branches = tail_branches("tail", extra_indices)
        branch = branches[branch_name]
        f9 = f_coefficients[9]
        equations = [sp.expand(expression.subs(f9, 0)) for expression in branch["equations"]]
        equations = [expression for expression in equations if expression != 0]
        variables = tuple(
            variable
            for variable in branch["variables"]
            if variable != f9 and any(expression.has(variable) for expression in equations)
        )

    if chart == "f10_f9_open":
        _, _, retained_indices, branches = tail_branches("tail", extra_indices)
        branch = branches[branch_name]
        f9 = f_coefficients[9]
        open_equation = sp.expand(f9_inverse * f9 - 1)
        equations = list(branch["equations"]) + [open_equation]
        variables = tuple(branch["variables"]) + (f9_inverse,)
        return (
            equations,
            variables,
            {
                "normalization": "f10=1; f9*f9inv=1",
                "retained_normal_equation_indices": list(retained_indices),
                "substitutions": {
                    **{
                        str(key): str(value)
                        for key, value in branch["zero_substitutions"].items()
                    },
                    "f10": "1",
                },
                "leading_form": (
                    str(branch["leading_form"])
                    if branch["leading_form"] is not None
                    else None
                ),
            },
        )
        missing = set().union(*(expression.free_symbols for expression in equations)) - set(variables)
        if missing:
            raise AssertionError(f"unlisted variables: {sorted(map(str, missing))}")
        return (
            equations,
            variables,
            {
                "normalization": "f10=1; f9=0",
                "retained_normal_equation_indices": list(retained_indices),
                "substitutions": {
                    **{
                        str(key): str(value)
                        for key, value in branch["zero_substitutions"].items()
                    },
                    "f9": "0",
                },
                "leading_form": (
                    str(sp.expand(branch["leading_form"].subs(f9, 0)))
                    if branch["leading_form"] is not None
                    else None
                ),
            },
        )

    raise ValueError(f"unknown chart: {chart}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", choices=CHARTS, required=True)
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--extra-index", type=int, action="append", default=[])
    parser.add_argument("--generator-index", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    extra_indices = tuple(dict.fromkeys(arguments.extra_index))
    if any(index < 0 or index >= 55 for index in extra_indices):
        parser.error("every extra index must lie in 0..54")

    equations, variables, metadata = selected_branch(
        arguments.chart, arguments.branch, extra_indices
    )
    original_generator_count = len(equations)
    original_variable_count = len(variables)
    if arguments.generator_index:
        generator_indices = tuple(dict.fromkeys(arguments.generator_index))
        if any(index < 0 or index >= original_generator_count for index in generator_indices):
            parser.error(
                f"every generator index must lie in 0..{original_generator_count - 1}"
            )
        equations = [equations[index] for index in generator_indices]
    else:
        generator_indices = tuple(range(original_generator_count))
    variables = tuple(
        variable
        for variable in variables
        if any(expression.has(variable) for expression in equations)
    )
    missing = set().union(*(expression.free_symbols for expression in equations)) - set(variables)
    if missing:
        raise AssertionError(f"unlisted variables after generator selection: {sorted(map(str, missing))}")
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    result = {
        "schema": "hc4-decimic-j2-secant-r10-sparse-rational-input-v1",
        "chart": arguments.chart,
        "branch": arguments.branch,
        "variable_names": [str(variable) for variable in variables],
        "equations": [sparse_terms(expression, variables) for expression in equations],
        "equation_count": len(equations),
        "original_generator_count": original_generator_count,
        "retained_generator_indices": list(generator_indices),
        "variable_count": len(variables),
        "original_variable_count": original_variable_count,
        "maximum_total_degree": max(
            sp.Poly(expression, *variables, domain=sp.QQ).total_degree()
            for expression in equations
        ),
        "equation_stream_sha256": digest(tuple(equations)),
        "metadata": metadata,
        "source_sha256": {
            "scripts/export_j2_secant_r10_groebner_input.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_tail_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_tail_branch.py").read_bytes()
            ).hexdigest(),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "chart": arguments.chart,
                "branch": arguments.branch,
                "variable_count": len(variables),
                "equation_count": len(equations),
                "retained_generator_indices": list(generator_indices),
                "maximum_total_degree": result["maximum_total_degree"],
                "equation_stream_sha256": result["equation_stream_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
