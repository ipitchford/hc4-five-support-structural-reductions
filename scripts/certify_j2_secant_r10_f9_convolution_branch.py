#!/usr/bin/env python3
"""Low-degree convolution branches on the secant ``f9=1,f10!=0`` chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_degree_branches import BASE_INDICES, CONVOLUTION_INDICES
from certify_j2_secant_r10_f9_chart import f9_normalized_chart
from certify_j2_tangent_r10_degree_branches import convolution_data
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source


BRANCH_NAMES = ("degree_6", "degree_5", "degree_4", "degree_3", "A_zero")
lead_inverse = sp.Symbol("leadinv")
t = sp.Symbol("t")


def convolution_branches():
    normal_equations, localizers, full_variables, j2 = f9_normalized_chart()
    _, A, C = convolution_data(normal_equations)
    A_polynomial = sp.Poly(A, t)
    if A_polynomial.degree() != 6 or sp.Poly(C, t).degree() != 7:
        raise AssertionError("the alternative-chart convolution degrees changed")
    coefficients = {
        degree: sp.expand(A_polynomial.coeff_monomial(t**degree))
        for degree in range(7)
    }
    specifications = (
        ("degree_6", (), coefficients[6], 6),
        ("degree_5", (coefficients[6],), coefficients[5], 5),
        ("degree_4", (coefficients[6], coefficients[5]), coefficients[4], 4),
        (
            "degree_3",
            (coefficients[6], coefficients[5], coefficients[4]),
            coefficients[3],
            3,
        ),
        ("A_zero", tuple(coefficients[degree] for degree in range(7)), None, None),
    )
    tail_indices = BASE_INDICES + CONVOLUTION_INDICES
    tail = [normal_equations[index] for index in tail_indices]
    branches = {}
    for name, vanishing, leading_form, expected_degree in specifications:
        auxiliary = []
        if leading_form is not None:
            auxiliary = [sp.expand(lead_inverse * leading_form - 1)]
        equations = [
            equation
            for equation in tail + list(vanishing) + localizers + auxiliary
            if equation != 0
        ]
        variables = tuple(
            variable
            for variable in full_variables
            if any(equation.has(variable) for equation in equations)
        )
        if auxiliary:
            variables += (lead_inverse,)
        missing = set().union(*(equation.free_symbols for equation in equations)) - set(variables)
        if missing:
            raise AssertionError(f"unlisted variables on {name}: {sorted(map(str, missing))}")
        branches[name] = {
            "vanishing_leading_coefficients": vanishing,
            "leading_form": leading_form,
            "expected_degree": expected_degree,
            "auxiliary": auxiliary,
            "equations": equations,
            "variables": variables,
        }
    return A, C, coefficients, tail_indices, j2, branches


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
    A, C, coefficients, tail_indices, j2, branches = convolution_branches()
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
            "PASS_EXACT_SECANT_R10_F9_CONVOLUTION_BRANCH_UNIT"
            if exact
            else "PASS_MODULAR_SECANT_R10_F9_CONVOLUTION_BRANCH_UNIT"
        )
    else:
        status = (
            "INCOMPLETE_EXACT_SECANT_R10_F9_CONVOLUTION_BRANCH"
            if exact
            else "INCOMPLETE_MODULAR_SECANT_R10_F9_CONVOLUTION_BRANCH"
        )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-convolution-branch-v1",
        "status": status,
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "branch": arguments.branch,
        "A_degree": branch["expected_degree"],
        "leading_form": str(branch["leading_form"]) if branch["leading_form"] is not None else None,
        "vanishing_leading_coefficient_count": len(branch["vanishing_leading_coefficients"]),
        "vanishing_leading_coefficient_stream_sha256": digest(
            tuple(branch["vanishing_leading_coefficients"])
        ),
        "A_sha256": digest((A,)),
        "C_sha256": digest((C,)),
        "A_coefficient_stream_sha256": digest(tuple(coefficients[degree] for degree in range(7))),
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
            "scripts/certify_j2_secant_r10_f9_convolution_branch.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_chart.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_chart.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a characteristic-zero passing receipt proves emptiness of this single "
            "necessary degree branch on the secant f9*f10*j2 open; all five exact "
            "branches are required to close that open locus"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-{arguments.branch}-{arguments.algorithm}-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
