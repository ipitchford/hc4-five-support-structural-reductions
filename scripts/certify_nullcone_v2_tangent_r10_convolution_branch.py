#!/usr/bin/env python3
"""Direct convolution-degree branches for the tangent V2 r=10 cell."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_r10_degree_branches import convolution_data
from scout_decimic_nullcone_hsop import digest, f_coefficients, run_source
from scout_j2_normalized_chart import singular_source
from scout_nullcone_v2_tangent_top_stratum import stratum, top_inverse


BASE_INDICES = (36,) + tuple(range(45, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))
t = sp.Symbol("t")
lead_inverse = sp.Symbol("leadinv")
BRANCHES = tuple(f"degree_{degree}" for degree in range(6, -1, -1)) + ("A_zero",)


def branch_system(name: str, top_mode: str = "inverse"):
    if top_mode not in {"inverse", "normalize"}:
        raise ValueError(f"unknown top mode: {top_mode}")
    (
        normal_equations,
        top_auxiliary,
        full_variables,
        substitutions,
        target,
        target_forces_top,
        build_seconds,
    ) = stratum(10)
    if top_mode == "normalize":
        top_substitution = {f_coefficients[10]: sp.Integer(1)}
        normal_equations = [
            sp.expand(equation.subs(top_substitution)) for equation in normal_equations
        ]
        top_auxiliary = [sp.expand(top_auxiliary[0].subs(top_substitution))]
        full_variables = tuple(
            variable
            for variable in full_variables
            if variable not in {f_coefficients[10], top_inverse}
        )
        target = sp.expand(target.subs(top_substitution))
        substitutions = {**substitutions, **top_substitution}
    _, A, C = convolution_data(normal_equations)
    A_poly = sp.Poly(A, t)
    a_coefficients = [
        sp.expand(A_poly.coeff_monomial(t**degree)) for degree in range(7)
    ]
    degree = None if name == "A_zero" else int(name.rsplit("_", 1)[1])
    branch_equations: list[sp.Expr] = []
    auxiliary = list(top_auxiliary)
    leading_coefficient = None
    if degree is None:
        branch_equations.extend(a_coefficients)
    else:
        branch_equations.extend(
            a_coefficients[index] for index in range(degree + 1, 7)
        )
        leading_coefficient = a_coefficients[degree]
        auxiliary.append(sp.expand(lead_inverse * leading_coefficient - 1))
    direct_convolution = [normal_equations[index] for index in CONVOLUTION_INDICES]
    base = [normal_equations[index] for index in BASE_INDICES]
    equations = [
        expression
        for expression in base + branch_equations + direct_convolution
        if expression != 0
    ]
    variables = tuple(
        variable
        for variable in full_variables
        if any(expression.has(variable) for expression in equations + auxiliary)
    )
    if any(expression.has(lead_inverse) for expression in auxiliary):
        variables += (lead_inverse,)
    missing = (
        set().union(*(expression.free_symbols for expression in equations + auxiliary))
        - set(variables)
    )
    if missing:
        raise AssertionError(f"unlisted branch variables: {sorted(map(str, missing))}")
    return {
        "equations": equations,
        "auxiliary": auxiliary,
        "variables": variables,
        "degree": degree,
        "leading_coefficient": leading_coefficient,
        "A": A,
        "C": C,
        "A_coefficients": a_coefficients,
        "base": base,
        "branch_equations": [item for item in branch_equations if item != 0],
        "direct_convolution": direct_convolution,
        "target": target,
        "target_forces_top": target_forces_top,
        "substitutions": substitutions,
        "build_seconds": build_seconds,
        "top_mode": top_mode,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCHES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--top-mode", choices=("inverse", "normalize"), default="inverse")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    branch = branch_system(arguments.branch, arguments.top_mode)
    source = singular_source(
        branch["equations"],
        branch["auxiliary"],
        branch["variables"],
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        status = "PASS_EXACT_V2_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["is_unit"]:
        status = "PASS_MODULAR_V2_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-nullcone-v2-tangent-r10-convolution-branch.v1",
        "status": status,
        "orbit": "tangent",
        "family": "V2",
        "top_index": 10,
        "branch": arguments.branch,
        "A_degree": branch["degree"],
        "leading_coefficient": (
            str(branch["leading_coefficient"])
            if branch["leading_coefficient"] is not None
            else None
        ),
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "unipotent_used": False,
        "top_mode": arguments.top_mode,
        "top_coefficient_normalized": arguments.top_mode == "normalize",
        "top_coefficient_torus_weight": -16,
        "target_normalized": False,
        "base_equation_indices": list(BASE_INDICES),
        "convolution_equation_indices": list(CONVOLUTION_INDICES),
        "convolution_identity_verified": True,
        "presentation": "direct original convolution equations",
        "A_sha256": digest((branch["A"],)),
        "C_sha256": digest((branch["C"],)),
        "target_sha256": digest((branch["target"],)),
        "branch_equation_count": len(branch["branch_equations"]),
        "direct_convolution_equation_count": len(branch["direct_convolution"]),
        "auxiliary_equation_count": len(branch["auxiliary"]),
        "equation_count": len(branch["equations"]) + len(branch["auxiliary"]),
        "variable_names": [str(variable) for variable in branch["variables"]],
        "variable_count": len(branch["variables"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *branch["variables"]).total_degree()
            for expression in branch["equations"] + branch["auxiliary"]
        ),
        "equation_stream_sha256": digest(tuple(branch["equations"])),
        "auxiliary_stream_sha256": digest(tuple(branch["auxiliary"])),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_nullcone_v2_tangent_r10_convolution_branch.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_nullcone_v2_tangent_top_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_v2_tangent_top_stratum.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing exact receipt closes one necessary A-degree branch of the "
            "r=10 V2-highest cell; all eight branches and an aggregate stabilizer "
            "audit are required for tangent V2-family containment"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = script_path.parent.parent / (
            f"receipts/nullcone-v2-tangent-r10-{arguments.branch}-{field}-{arguments.algorithm}-direct-{arguments.top_mode}.json"
        )
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
