#!/usr/bin/env python3
"""Exact leading-degree branch certificate for the tangent r=10 convolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_coefficient_slice import coefficient_slice
from scout_decimic_nullcone_hsop import digest, f_coefficients, run_source
from scout_j2_normalized_chart import singular_source


BASE_INDICES = (36,) + tuple(range(45, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))
branch_inverse = sp.Symbol("leadinv")
t = sp.Symbol("t")


def convolution_data(normal_equations: list[sp.Expr]):
    f3 = f_coefficients[3]
    f4 = f_coefficients[4]
    rows = []
    for index in CONVOLUTION_INDICES:
        equation = normal_equations[index]
        a = sp.diff(equation, f3)
        b = sp.diff(equation, f4)
        c = sp.expand(equation - a * f3 - b * f4)
        if c.has(f3, f4):
            raise AssertionError(f"equation {index} is not linear in f3,f4")
        rows.append((a, b, c))
    if rows[0][1] != 0 or rows[-1][0] != 0:
        raise AssertionError("the convolution endpoints changed")
    for index in range(1, len(rows)):
        if sp.expand(rows[index][1] - rows[index - 1][0]) != 0:
            raise AssertionError("the convolution shift identity failed")
    A = sp.expand(sum(rows[index][0] * t**index for index in range(8)))
    C = sp.expand(sum(rows[index][2] * t**index for index in range(8)))
    return rows, A, C


def branch_systems(normal_equations: list[sp.Expr], full_variables):
    _, A, C = convolution_data(normal_equations)
    base = [normal_equations[index] for index in BASE_INDICES]
    g0, g1, g2, g3 = sp.symbols("g0 g1 g2 g3")
    specifications = (
        ("degree_6", {}, g0, 6),
        ("degree_5", {g0: 0}, g1, 5),
        ("degree_4", {g0: 0, g1: 0}, g2, 4),
        ("degree_3", {g0: 0, g1: 0, g2: 0}, g3, 3),
        ("A_zero", {g0: 0, g1: 0, g2: 0, g3: 0}, None, None),
    )
    result = {}
    for name, zero_substitutions, leading_variable, expected_degree in specifications:
        A_specialized = sp.Poly(sp.expand(A.subs(zero_substitutions)), t)
        C_specialized = sp.Poly(sp.expand(C.subs(zero_substitutions)), t)
        base_specialized = [
            sp.expand(equation.subs(zero_substitutions)) for equation in base
        ]
        compatibility: list[sp.Expr] = []
        auxiliary: list[sp.Expr] = []
        if leading_variable is None:
            if A_specialized.as_expr() != 0:
                raise AssertionError("A does not vanish on the terminal branch")
            compatibility = [
                sp.expand(C_specialized.coeff_monomial(t**degree))
                for degree in range(8)
            ]
        else:
            if A_specialized.degree() != expected_degree:
                raise AssertionError(f"unexpected A degree on {name}")
            leading_coefficient = sp.expand(A_specialized.LC())
            scalar = sp.cancel(leading_coefficient / leading_variable)
            if scalar.free_symbols or scalar == 0:
                raise AssertionError(f"the leading coefficient on {name} is not a scalar multiple")
            compatibility.extend(
                sp.expand(C_specialized.coeff_monomial(t**degree))
                for degree in range(expected_degree + 2, 8)
            )
            pseudo_remainder = sp.Poly(sp.prem(C_specialized, A_specialized), t)
            compatibility.extend(
                sp.expand(pseudo_remainder.coeff_monomial(t**degree))
                for degree in range(expected_degree)
            )
            auxiliary = [sp.expand(branch_inverse * leading_variable - 1)]
        equations = [
            equation
            for equation in base_specialized + compatibility + auxiliary
            if equation != 0
        ]
        excluded = {f_coefficients[3], f_coefficients[4], *zero_substitutions.keys()}
        variables = tuple(
            variable
            for variable in full_variables
            if variable not in excluded and any(equation.has(variable) for equation in equations)
        )
        if any(equation.has(branch_inverse) for equation in equations):
            variables += (branch_inverse,)
        result[name] = {
            "zero_substitutions": zero_substitutions,
            "leading_variable": leading_variable,
            "A": A_specialized.as_expr(),
            "C": C_specialized.as_expr(),
            "expected_degree": expected_degree,
            "base": base_specialized,
            "compatibility": [equation for equation in compatibility if equation != 0],
            "auxiliary": auxiliary,
            "equations": equations,
            "variables": variables,
        }
    return A, C, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="qstd"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r10-degree-branches-exact.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    normal_equations, _, full_variables, substitutions, j2 = coefficient_slice(10)
    A, C, branches = branch_systems(normal_equations, full_variables)

    branch_results = {}
    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    for name, branch in branches.items():
        source = singular_source(
            branch["equations"], [], branch["variables"], 0, source_algorithm
        )
        source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
        calculation = run_source(source, arguments.timeout)
        branch_results[name] = {
            "zero_substitutions": {
                str(symbol): int(value)
                for symbol, value in branch["zero_substitutions"].items()
            },
            "leading_variable": (
                str(branch["leading_variable"])
                if branch["leading_variable"] is not None
                else None
            ),
            "A_degree": branch["expected_degree"],
            "base_equation_count": len(branch["base"]),
            "compatibility_equation_count": len(branch["compatibility"]),
            "auxiliary_equation_count": len(branch["auxiliary"]),
            "equation_count": len(branch["equations"]),
            "variable_names": [str(variable) for variable in branch["variables"]],
            "variable_count": len(branch["variables"]),
            "maximum_total_degree": max(
                sp.Poly(expression, *branch["variables"]).total_degree()
                for expression in branch["equations"]
            ),
            "equation_stream_sha256": digest(tuple(branch["equations"])),
            "compatibility_stream_sha256": digest(tuple(branch["compatibility"])),
            "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
            "calculation": calculation,
            "exact_unit": bool(calculation["is_unit"]),
        }

    all_unit = all(branch["exact_unit"] for branch in branch_results.values())
    status = (
        "PASS_EXACT_TANGENT_R10_EMPTY"
        if all_unit
        else "INCOMPLETE_EXACT_TANGENT_R10_DEGREE_BRANCHES"
    )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt_path = campaign / "receipts/residual-orbit-torus.json"
    torus_receipt = json.loads(torus_receipt_path.read_text(encoding="utf-8"))
    if torus_receipt.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    if torus_receipt["tangent"]["coefficient_weights"][10] != -16:
        raise AssertionError("the f10 coefficient-normalization weight changed")

    result = {
        "schema": "hc4-decimic-j2-tangent-r10-degree-branch-certificate-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 10,
        "coefficient_normalization": "f10=1",
        "unipotent_normalization": "f9=0",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "base_equation_indices": list(BASE_INDICES),
        "convolution_equation_indices": list(CONVOLUTION_INDICES),
        "convolution_identity_verified": True,
        "A_sha256": digest((A,)),
        "C_sha256": digest((C,)),
        "degree_branch_cover": ["g0!=0", "g0=0,g1!=0", "g0=g1=0,g2!=0", "g0=g1=g2=0,g3!=0", "g0=g1=g2=g3=0"],
        "algorithm": "Singular " + arguments.algorithm,
        "characteristic": 0,
        "branch_results": branch_results,
        "torus_normalization_preconditions_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r10_degree_branches.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_coefficient_slice.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                torus_receipt_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact characteristic-zero emptiness of the "
            "tangent top_index=10 stratum through necessary convolution-compatibility "
            "conditions; the five other tangent strata are separate dependencies"
        ),
    }
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all_unit else 1


if __name__ == "__main__":
    raise SystemExit(main())
