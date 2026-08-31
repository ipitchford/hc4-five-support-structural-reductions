#!/usr/bin/env python3
"""Laurent-reduced convolution branches on the secant ``f9=1`` chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_degree_branches import BASE_INDICES, CONVOLUTION_INDICES, clear_denominators
from certify_j2_secant_r10_f9_chart import f10_inverse, f9_normalized_chart
from certify_j2_tangent_r10_degree_branches import convolution_data
from scout_decimic_nullcone_hsop import digest, f_coefficients, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import singular_source


BRANCH_NAMES = ("degree_6", "degree_5", "degree_4", "degree_3", "A_zero")
lead_inverse = sp.Symbol("leadinv")
t = sp.Symbol("t")


def laurent_reduce(expression: sp.Expr, variable: sp.Symbol, inverse: sp.Symbol) -> sp.Expr:
    """Reduce monomials modulo ``variable*inverse-1`` without division."""
    result = sp.Integer(0)
    for term in sp.Add.make_args(sp.expand(expression)):
        powers = term.as_powers_dict()
        variable_power = int(powers.get(variable, 0))
        inverse_power = int(powers.get(inverse, 0))
        cancellation = min(variable_power, inverse_power)
        result += sp.expand(term / (variable * inverse) ** cancellation)
    return sp.expand(result)


def laurent_branches():
    normal_equations, localizers, full_variables, j2 = f9_normalized_chart()
    _, A, C = convolution_data(normal_equations)
    h = f_coefficients[10]
    z = f10_inverse
    g0, g1, g2, g3 = g_coefficients[:4]
    specifications = (
        ("degree_6", {}, 5 * h * g0 + 2, 6),
        ("degree_5", {g0: -sp.Rational(2, 5) * z}, 25 * h**2 * g1 + 2, 5),
        (
            "degree_4",
            {g0: -sp.Rational(2, 5) * z, g1: -sp.Rational(2, 25) * z**2},
            125 * h**3 * g2 + 1,
            4,
        ),
        (
            "degree_3",
            {
                g0: -sp.Rational(2, 5) * z,
                g1: -sp.Rational(2, 25) * z**2,
                g2: -sp.Rational(1, 125) * z**3,
            },
            3125 * h**4 * g3 + 1,
            3,
        ),
        (
            "A_zero",
            {
                g0: -sp.Rational(2, 5) * z,
                g1: -sp.Rational(2, 25) * z**2,
                g2: -sp.Rational(1, 125) * z**3,
                g3: -sp.Rational(1, 3125) * z**4,
            },
            None,
            None,
        ),
    )
    inverse_relation = localizers[1]
    if sp.expand(inverse_relation - (z * h - 1)) != 0:
        raise AssertionError("the f10 inverse relation changed")
    tail_indices = BASE_INDICES + CONVOLUTION_INDICES
    branches = {}
    for name, substitutions, leading_form, expected_degree in specifications:
        specialized_A = laurent_reduce(A.subs(substitutions), h, z)
        A_polynomial = sp.Poly(specialized_A, t)
        if leading_form is None:
            if specialized_A != 0:
                raise AssertionError("A does not Laurent-reduce to zero on the terminal branch")
        else:
            if A_polynomial.degree() != expected_degree:
                raise AssertionError(f"unexpected Laurent A degree on {name}")
        tail = [
            clear_denominators(
                laurent_reduce(normal_equations[index].subs(substitutions), h, z)
            )
            for index in tail_indices
        ]
        j2_localizer = clear_denominators(
            laurent_reduce(localizers[0].subs(substitutions), h, z)
        )
        auxiliary = []
        if leading_form is not None:
            auxiliary = [sp.expand(lead_inverse * leading_form - 1)]
        equations = [
            equation
            for equation in tail + [j2_localizer, inverse_relation] + auxiliary
            if equation != 0
        ]
        excluded = set(substitutions)
        variables = tuple(
            variable
            for variable in full_variables
            if variable not in excluded
            and any(equation.has(variable) for equation in equations)
        )
        if auxiliary:
            variables += (lead_inverse,)
        missing = set().union(*(equation.free_symbols for equation in equations)) - set(variables)
        if missing:
            raise AssertionError(f"unlisted variables on {name}: {sorted(map(str, missing))}")
        branches[name] = {
            "substitutions": substitutions,
            "leading_form": leading_form,
            "expected_degree": expected_degree,
            "specialized_A": specialized_A,
            "equations": equations,
            "variables": variables,
            "auxiliary": auxiliary,
        }
    return A, C, tail_indices, j2, branches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="modstd"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    A, C, tail_indices, j2, branches = laurent_branches()
    branch = branches[arguments.branch]
    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(
        branch["equations"], [], branch["variables"], arguments.characteristic, source_algorithm
    )
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    exact = arguments.characteristic == 0
    if calculation["is_unit"]:
        status = (
            "PASS_EXACT_SECANT_R10_F9_LAURENT_BRANCH_UNIT"
            if exact
            else "PASS_MODULAR_SECANT_R10_F9_LAURENT_BRANCH_UNIT"
        )
    else:
        status = (
            "INCOMPLETE_EXACT_SECANT_R10_F9_LAURENT_BRANCH"
            if exact
            else "INCOMPLETE_MODULAR_SECANT_R10_F9_LAURENT_BRANCH"
        )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-laurent-branch-v1",
        "status": status,
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "branch": arguments.branch,
        "A_degree": branch["expected_degree"],
        "substitutions": {str(key): str(value) for key, value in branch["substitutions"].items()},
        "leading_form": str(branch["leading_form"]) if branch["leading_form"] is not None else None,
        "laurent_relation": "f10*f10inv=1",
        "A_sha256": digest((A,)),
        "C_sha256": digest((C,)),
        "specialized_A_sha256": digest((branch["specialized_A"],)),
        "retained_normal_equation_indices": list(tail_indices),
        "j2_after_substitution": str(j2),
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "variable_names": [str(variable) for variable in branch["variables"]],
        "variable_count": len(branch["variables"]),
        "equation_count": len(branch["equations"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *branch["variables"]).total_degree()
            for expression in branch["equations"]
        ),
        "equation_stream_sha256": digest(tuple(branch["equations"])),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_chart.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_chart.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a characteristic-zero passing receipt proves emptiness of this single "
            "Laurent-reduced degree branch on the secant f9*f10*j2 open; all five "
            "exact branches are required to close that open locus"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-laurent-{arguments.branch}-{arguments.algorithm}-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
