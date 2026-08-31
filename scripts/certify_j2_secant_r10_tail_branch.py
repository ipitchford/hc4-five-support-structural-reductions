#!/usr/bin/env python3
"""Replay one low-degree leading-coefficient branch of secant ``r=10``.

Unlike the pseudo-remainder scout, this certificate retains the eight original
convolution rows.  The five branches are still cut out by the successive
leading coefficients of ``A(t)``, but generator degrees remain close to those
of the source system.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_coefficient_slice import coefficient_slice
from certify_j2_secant_r10_degree_branches import (
    BASE_INDICES,
    CONVOLUTION_INDICES,
    branch_inverse,
    clear_denominators,
)
from scout_decimic_nullcone_hsop import digest, f_coefficients, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import singular_source


BRANCH_NAMES = ("degree_6", "degree_5", "degree_4", "degree_3", "A_zero")
f9_inverse = sp.Symbol("f9inv")


def tail_branches(equation_scope: str = "tail", extra_indices: tuple[int, ...] = ()):
    normal_equations, localization, full_variables, substitutions, j2 = (
        coefficient_slice(10)
    )
    f9 = f_coefficients[9]
    g0, g1, g2, g3 = g_coefficients[:4]
    specifications = (
        ("degree_6", {}, 2 * f9**2 + 5 * g0, 6),
        ("degree_5", {g0: -sp.Rational(2, 5) * f9**2}, 2 * f9**3 + 25 * g1, 5),
        (
            "degree_4",
            {g0: -sp.Rational(2, 5) * f9**2, g1: -sp.Rational(2, 25) * f9**3},
            f9**4 + 125 * g2,
            4,
        ),
        (
            "degree_3",
            {
                g0: -sp.Rational(2, 5) * f9**2,
                g1: -sp.Rational(2, 25) * f9**3,
                g2: -sp.Rational(1, 125) * f9**4,
            },
            f9**5 + 3125 * g3,
            3,
        ),
        (
            "A_zero",
            {
                g0: -sp.Rational(2, 5) * f9**2,
                g1: -sp.Rational(2, 25) * f9**3,
                g2: -sp.Rational(1, 125) * f9**4,
                g3: -sp.Rational(1, 3125) * f9**5,
            },
            None,
            None,
        ),
    )
    branches = {}
    if equation_scope == "tail":
        retained_indices = BASE_INDICES + CONVOLUTION_INDICES + extra_indices
    elif equation_scope == "all":
        retained_indices = tuple(range(len(normal_equations)))
    else:
        raise ValueError(f"unknown equation scope: {equation_scope}")
    for name, zero_substitutions, leading_form, expected_degree in specifications:
        equations = [
            clear_denominators(normal_equations[index].subs(zero_substitutions))
            for index in retained_indices
        ]
        equations.extend(
            clear_denominators(equation.subs(zero_substitutions))
            for equation in localization
        )
        auxiliary = []
        if leading_form is not None:
            auxiliary = [sp.expand(branch_inverse * leading_form - 1)]
            equations.extend(auxiliary)
        equations = [equation for equation in equations if equation != 0]
        excluded = set(zero_substitutions)
        variables = tuple(
            variable
            for variable in full_variables
            if variable not in excluded
            and any(equation.has(variable) for equation in equations)
        )
        if auxiliary:
            variables += (branch_inverse,)
        missing = set().union(*(equation.free_symbols for equation in equations)) - set(variables)
        if missing:
            raise AssertionError(f"unlisted variables on {name}: {sorted(map(str, missing))}")
        branches[name] = {
            "zero_substitutions": zero_substitutions,
            "leading_form": leading_form,
            "expected_degree": expected_degree,
            "equations": equations,
            "variables": variables,
            "auxiliary": auxiliary,
        }
    return substitutions, j2, retained_indices, branches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--equation-scope", choices=("tail", "all"), default="tail")
    parser.add_argument("--extra-index", type=int, action="append", default=[])
    parser.add_argument(
        "--f9-case", choices=("unrestricted", "zero", "open"), default="unrestricted"
    )
    parser.add_argument(
        "--variable-order", choices=("forward", "reverse"), default="forward"
    )
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    extra_indices = tuple(dict.fromkeys(arguments.extra_index))
    if any(index < 0 or index >= 55 for index in extra_indices):
        parser.error("every extra index must lie in 0..54")
    if arguments.equation_scope == "all" and extra_indices:
        parser.error("extra indices are only meaningful with --equation-scope tail")
    substitutions, j2, retained_indices, branches = tail_branches(
        arguments.equation_scope, extra_indices
    )
    branch = dict(branches[arguments.branch])
    branch["equations"] = list(branch["equations"])
    branch["variables"] = tuple(branch["variables"])
    branch["zero_substitutions"] = dict(branch["zero_substitutions"])
    branch["auxiliary"] = list(branch["auxiliary"])
    if arguments.f9_case != "unrestricted" and arguments.branch != "degree_4":
        parser.error("the f9 refinement is currently certified only for degree_4")
    if arguments.f9_case == "zero":
        f9 = f_coefficients[9]
        branch["equations"] = [
            clear_denominators(equation.subs(f9, 0))
            for equation in branch["equations"]
            if equation.subs(f9, 0) != 0
        ]
        branch["variables"] = tuple(
            variable for variable in branch["variables"] if variable != f9
        )
        branch["zero_substitutions"][f9] = sp.Integer(0)
    elif arguments.f9_case == "open":
        open_equation = sp.expand(f9_inverse * f_coefficients[9] - 1)
        branch["equations"].append(open_equation)
        branch["variables"] += (f9_inverse,)
        branch["auxiliary"].append(open_equation)
    if arguments.variable_order == "reverse":
        branch["variables"] = tuple(reversed(branch["variables"]))
    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(
        branch["equations"], [], branch["variables"], arguments.characteristic, source_algorithm
    )
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    exact = arguments.characteristic == 0
    if calculation["is_unit"]:
        status = (
            "PASS_EXACT_SECANT_R10_TAIL_BRANCH_UNIT"
            if exact
            else "PASS_MODULAR_SECANT_R10_TAIL_BRANCH_UNIT"
        )
    else:
        status = (
            "INCOMPLETE_EXACT_SECANT_R10_TAIL_BRANCH"
            if exact
            else "INCOMPLETE_MODULAR_SECANT_R10_TAIL_BRANCH"
        )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-tail-branch-v1",
        "status": status,
        "orbit": "secant",
        "top_index": 10,
        "branch": arguments.branch,
        "equation_scope": arguments.equation_scope,
        "extra_normal_equation_indices": list(extra_indices),
        "f9_case": arguments.f9_case,
        "variable_order": arguments.variable_order,
        "zero_substitutions": {
            str(symbol): str(value) for symbol, value in branch["zero_substitutions"].items()
        },
        "leading_form": str(branch["leading_form"]) if branch["leading_form"] is not None else None,
        "A_degree": branch["expected_degree"],
        "coefficient_normalization": "f10=1",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "retained_normal_equation_indices": list(retained_indices),
        "retained_normal_equation_count": len(retained_indices),
        "localizer_equation_count": 1,
        "auxiliary_equation_count": len(branch["auxiliary"]),
        "equation_count": len(branch["equations"]),
        "variable_names": [str(variable) for variable in branch["variables"]],
        "variable_count": len(branch["variables"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *branch["variables"]).total_degree()
            for expression in branch["equations"]
        ),
        "equation_stream_sha256": digest(tuple(branch["equations"])),
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_tail_branch.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_degree_branches.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_degree_branches.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_coefficient_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a characteristic-zero passing receipt proves emptiness of this single "
            "necessary low-degree secant r=10 tail branch on j2!=0; all five exact "
            "tail-branch receipts are required for the r=10 stratum"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        extra_suffix = (
            "-x" + "_".join(map(str, extra_indices)) if extra_indices else ""
        )
        f9_suffix = "" if arguments.f9_case == "unrestricted" else f"-f9_{arguments.f9_case}"
        order_suffix = "" if arguments.variable_order == "forward" else "-reverse"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-{arguments.branch}-{arguments.equation_scope}-"
            f"{arguments.algorithm}-{field}{extra_suffix}{f9_suffix}{order_suffix}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
