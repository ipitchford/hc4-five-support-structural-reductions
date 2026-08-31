#!/usr/bin/env python3
"""Direct r=10 convolution branches for tangent quartic target families."""

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
from scout_nullcone_quartic_tangent_top_stratum import FAMILIES, stratum, top_inverse


BASE_INDICES = (36,) + tuple(range(45, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))
t = sp.Symbol("t")
lead_inverse = sp.Symbol("leadinv")
target_inverse = sp.Symbol("quarticinv")
BRANCHES = tuple(f"degree_{degree}" for degree in range(6, -1, -1)) + ("A_zero",)


def branch_system(family: str, name: str, torus_gauge: str = "target"):
    if torus_gauge not in {"target", "top"}:
        raise ValueError(f"unknown torus gauge: {torus_gauge}")
    top = stratum(family, 10)
    normal_equations = top["equations"]
    auxiliary = list(top["auxiliary"])
    variables_source = top["variables"]
    target = top["target"]
    if torus_gauge == "top":
        top_substitution = {f_coefficients[10]: sp.Integer(1)}
        normal_equations = [
            sp.expand(equation.subs(top_substitution)) for equation in normal_equations
        ]
        target = sp.expand(target.subs(top_substitution))
        auxiliary = [sp.expand(target_inverse * target - 1)]
        variables_source = tuple(
            variable
            for variable in variables_source
            if variable not in {f_coefficients[10], top_inverse}
        ) + (target_inverse,)
    _, A, C = convolution_data(normal_equations)
    A_poly = sp.Poly(A, t)
    a_coefficients = [
        sp.expand(A_poly.coeff_monomial(t**degree)) for degree in range(7)
    ]
    degree = None if name == "A_zero" else int(name.rsplit("_", 1)[1])
    branch_equations: list[sp.Expr] = []
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
        for variable in variables_source
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
        "branch_equations": [item for item in branch_equations if item != 0],
        "direct_convolution": direct_convolution,
        "top": {**top, "target": target},
        "torus_gauge": torus_gauge,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--branch", choices=BRANCHES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--torus-gauge", choices=("target", "top"), default="target")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    data = branch_system(arguments.family, arguments.branch, arguments.torus_gauge)
    source = singular_source(
        data["equations"],
        data["auxiliary"],
        data["variables"],
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        status = "PASS_EXACT_QUARTIC_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["is_unit"]:
        status = "PASS_MODULAR_QUARTIC_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4.decimic-nullcone-quartic-tangent-r10-convolution-branch.v1",
        "status": status,
        "orbit": "tangent",
        "family": arguments.family,
        "family_order": data["top"]["profile"]["order"],
        "top_index": 10,
        "branch": arguments.branch,
        "A_degree": data["degree"],
        "leading_coefficient": (
            str(data["leading_coefficient"])
            if data["leading_coefficient"] is not None
            else None
        ),
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "unipotent_used": False,
        "torus_gauge": arguments.torus_gauge,
        "target_normalized": arguments.torus_gauge == "target",
        "target_localized": arguments.torus_gauge == "top",
        "top_coefficient_normalized": arguments.torus_gauge == "top",
        "top_coefficient_torus_weight": -16,
        "tangent_torus_weight": data["top"]["target_weight"],
        "presentation": "direct original convolution equations",
        "base_equation_indices": list(BASE_INDICES),
        "convolution_equation_indices": list(CONVOLUTION_INDICES),
        "convolution_identity_verified": True,
        "A_sha256": digest((data["A"],)),
        "C_sha256": digest((data["C"],)),
        "target_sha256": digest((data["top"]["target"],)),
        "branch_equation_count": len(data["branch_equations"]),
        "direct_convolution_equation_count": len(data["direct_convolution"]),
        "auxiliary_equation_count": len(data["auxiliary"]),
        "equation_count": len(data["equations"]) + len(data["auxiliary"]),
        "variable_names": [str(variable) for variable in data["variables"]],
        "variable_count": len(data["variables"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *data["variables"]).total_degree()
            for expression in data["equations"] + data["auxiliary"]
        ),
        "equation_stream_sha256": digest(tuple(data["equations"])),
        "auxiliary_stream_sha256": digest(tuple(data["auxiliary"])),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_nullcone_quartic_tangent_r10_convolution_branch.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_nullcone_quartic_tangent_top_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_quartic_tangent_top_stratum.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing exact receipt closes one necessary A-degree branch for one "
            "quartic highest coordinate; all eight branches, five lower top-index "
            "cells, stabilizer propagation, and remaining families are separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/nullcone-{arguments.family.lower()}-tangent-r10-{arguments.branch}-"
            f"{field}-{arguments.algorithm}-direct-{arguments.torus_gauge}-gauge.json"
        )
    elif not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
