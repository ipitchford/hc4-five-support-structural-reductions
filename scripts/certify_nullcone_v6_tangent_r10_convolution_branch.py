#!/usr/bin/env python3
"""Convolution-degree branches for the tangent V6 top-index-ten cell.

No tangent unipotent normalization is used.  The eight normal equations at
indices 37..44 have the exact form

    C(t) + (f3 + f4*t) A(t) = 0.

The branch ``degree_d`` sets the coefficients of A above d to zero and
localizes its degree-d coefficient.  Three fibre modes expose the same branch
to the solver: ``eliminate`` removes f3 and f4 using pseudo-remainders,
``keep`` retains them alongside the compatibility equations, and ``direct``
uses the eight original convolution equations.  ``A_zero`` handles the
terminal branch.
"""

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
from scout_nullcone_v6_tangent_top_stratum import stratum


BASE_INDICES = (36,) + tuple(range(45, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))
t = sp.Symbol("t")
lead_inverse = sp.Symbol("leadinv")
BRANCHES = tuple(f"degree_{degree}" for degree in range(6, -1, -1)) + ("A_zero",)


def branch_system(name: str, fibre_mode: str = "eliminate"):
    if fibre_mode not in {"eliminate", "keep", "direct"}:
        raise ValueError(f"unknown fibre mode: {fibre_mode}")
    normal_equations, top_auxiliary, full_variables, substitutions, target, build_seconds = stratum(10)
    _, A, C = convolution_data(normal_equations)
    A_poly = sp.Poly(A, t)
    C_poly = sp.Poly(C, t)
    a_coefficients = [sp.expand(A_poly.coeff_monomial(t**degree)) for degree in range(7)]
    c_coefficients = [sp.expand(C_poly.coeff_monomial(t**degree)) for degree in range(8)]
    base = [normal_equations[index] for index in BASE_INDICES]

    degree = None if name == "A_zero" else int(name.rsplit("_", 1)[1])
    branch_equations: list[sp.Expr] = []
    compatibility: list[sp.Expr] = []
    if degree is None:
        branch_equations.extend(a_coefficients)
        compatibility.extend(c_coefficients)
        leading_coefficient = None
        auxiliary = list(top_auxiliary)
        eliminated_fibre = False
        fibre_substitutions: dict[sp.Symbol, sp.Expr] = {}
    else:
        branch_equations.extend(a_coefficients[index] for index in range(degree + 1, 7))
        leading_coefficient = a_coefficients[degree]
        A_specialized = sp.Poly(
            sum(a_coefficients[index] * t**index for index in range(degree + 1)), t
        )
        if A_specialized.degree() != degree:
            raise AssertionError("the formal branch degree changed")
        if fibre_mode == "direct":
            compatibility.extend(normal_equations[index] for index in CONVOLUTION_INDICES)
        else:
            compatibility.extend(c_coefficients[index] for index in range(degree + 2, 8))
            pseudo_remainder = sp.Poly(sp.prem(C_poly, A_specialized), t)
            compatibility.extend(
                sp.expand(pseudo_remainder.coeff_monomial(t**index))
                for index in range(degree)
            )
        previous_coefficient = a_coefficients[degree - 1] if degree > 0 else sp.Integer(0)
        f4_replacement = sp.expand(-c_coefficients[degree + 1] * lead_inverse)
        f3_replacement = sp.expand(
            (-c_coefficients[degree] * leading_coefficient
             + c_coefficients[degree + 1] * previous_coefficient)
            * lead_inverse**2
        )
        if fibre_mode == "eliminate":
            fibre_substitutions = {
                f_coefficients[3]: f3_replacement,
                f_coefficients[4]: f4_replacement,
            }
            normalized_target = sp.expand(top_auxiliary[0].subs(fibre_substitutions))
            auxiliary = [
                normalized_target,
                top_auxiliary[1],
                sp.expand(lead_inverse * leading_coefficient - 1),
            ]
            eliminated_fibre = True
        else:
            fibre_substitutions = {}
            auxiliary = list(top_auxiliary) + [
                sp.expand(lead_inverse * leading_coefficient - 1)
            ]
            eliminated_fibre = False

    equations = [
        expression
        for expression in base + branch_equations + compatibility
        if expression != 0
    ]
    excluded = {f_coefficients[3], f_coefficients[4]} if eliminated_fibre else set()
    variables = tuple(
        variable
        for variable in full_variables
        if variable not in excluded
        and any(expression.has(variable) for expression in equations + auxiliary)
    )
    if any(expression.has(lead_inverse) for expression in auxiliary):
        variables += (lead_inverse,)
    missing = set().union(*(expression.free_symbols for expression in equations + auxiliary)) - set(variables)
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
        "C_coefficients": c_coefficients,
        "base": base,
        "branch_equations": [item for item in branch_equations if item != 0],
        "compatibility": [item for item in compatibility if item != 0],
        "eliminated_fibre": eliminated_fibre,
        "fibre_substitutions": fibre_substitutions,
        "target": target,
        "substitutions": substitutions,
        "build_seconds": build_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCHES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument(
        "--fibre-mode", choices=("eliminate", "keep", "direct"), default="eliminate"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    branch = branch_system(arguments.branch, arguments.fibre_mode)
    equations = branch["equations"]
    auxiliary = branch["auxiliary"]
    variables = branch["variables"]
    source = singular_source(
        equations,
        auxiliary,
        variables,
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        status = "PASS_EXACT_V6_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["is_unit"]:
        status = "PASS_MODULAR_V6_TANGENT_R10_CONVOLUTION_BRANCH"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-r10-convolution-branch.v1",
        "status": status,
        "orbit": "tangent",
        "family": "V6",
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
        "base_equation_indices": list(BASE_INDICES),
        "convolution_equation_indices": list(CONVOLUTION_INDICES),
        "convolution_identity_verified": True,
        "fibre_variables_eliminated": branch["eliminated_fibre"],
        "fibre_mode": arguments.fibre_mode,
        "fibre_substitutions": {
            str(symbol): str(expression)
            for symbol, expression in branch["fibre_substitutions"].items()
        },
        "A_sha256": digest((branch["A"],)),
        "C_sha256": digest((branch["C"],)),
        "branch_equation_count": len(branch["branch_equations"]),
        "compatibility_equation_count": len(branch["compatibility"]),
        "auxiliary_equation_count": len(auxiliary),
        "equation_count": len(equations) + len(auxiliary),
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + auxiliary
        ),
        "equation_stream_sha256": digest(tuple(equations)),
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "compatibility_stream_sha256": digest(tuple(branch["compatibility"])),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_nullcone_v6_tangent_r10_convolution_branch.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_nullcone_v6_tangent_top_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_v6_tangent_top_stratum.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing exact receipt closes only one necessary convolution-degree "
            "branch of the r=10 highest-coefficient cell; all eight branches are "
            "required, and full V6-family containment remains separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = script_path.parent.parent / (
            f"receipts/nullcone-v6-tangent-r10-{arguments.branch}-{field}-{arguments.algorithm}-"
            f"{arguments.fibre_mode}.json"
        )
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
