#!/usr/bin/env python3
"""Exact alternative-torus chart for secant ``f9*f10*j2 != 0``."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import primitive_j2, singular_source


j2_inverse = sp.Symbol("j2inv")
f10_inverse = sp.Symbol("f10inv")


def f9_normalized_chart():
    equations, _ = normal_equations("secant")
    substitution = {f_coefficients[9]: sp.Integer(1)}
    reduced = [sp.expand(equation.subs(substitution)) for equation in equations]
    j2 = sp.expand(primitive_j2().subs(substitution))
    localizers = [
        sp.expand(j2_inverse * j2 - 1),
        sp.expand(f10_inverse * f_coefficients[10] - 1),
    ]
    variables = (
        tuple(coefficient for coefficient in f_coefficients if coefficient != f_coefficients[9])
        + g_coefficients
        + (j2_inverse, f10_inverse)
    )
    if any(expression.has(f_coefficients[9]) for expression in reduced + localizers):
        raise AssertionError("f9 survived the alternative torus normalization")
    return reduced, localizers, variables, j2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="modstd"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    equations, localizers, variables, j2 = f9_normalized_chart()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_path = campaign / "receipts/residual-orbit-torus.json"
    torus = json.loads(torus_path.read_text(encoding="utf-8"))
    if torus.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    weights = torus["secant"]["coefficient_weights"]
    if weights[9] != -4 or weights[10] != -5 or torus["secant"]["j2_weight"] != 0:
        raise AssertionError("the alternative secant-chart weights changed")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(
        equations, localizers, variables, arguments.characteristic, source_algorithm
    )
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    exact = arguments.characteristic == 0
    if calculation["is_unit"]:
        status = (
            "PASS_EXACT_SECANT_R10_F9_OPEN_EMPTY"
            if exact
            else "PASS_MODULAR_SECANT_R10_F9_OPEN_EMPTY"
        )
    else:
        status = (
            "INCOMPLETE_EXACT_SECANT_R10_F9_OPEN"
            if exact
            else "INCOMPLETE_MODULAR_SECANT_R10_F9_OPEN"
        )
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-alternative-chart-v1",
        "status": status,
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "cover_source_locus": "D(f9*f10*j2)",
        "torus_weights": {"f9": -4, "f10": -5, "j2": 0},
        "normalization_over_algebraic_closure": "choose tau with tau^-4*f9=1",
        "j2_after_substitution": str(j2),
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_equation_count": len(equations),
        "localizer_equation_count": len(localizers),
        "generator_count": len(equations) + len(localizers),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + localizers
        ),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "localizer_stream_sha256": digest(tuple(localizers)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_f9_chart.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": torus["source_sha256"]["scripts/certify_residual_orbit_torus.py"],
            "receipts/residual-orbit-torus.json": hashlib.sha256(torus_path.read_bytes()).hexdigest(),
        },
        "claim_boundary": (
            "a characteristic-zero passing receipt proves emptiness only on the "
            "secant locus f9*f10*j2!=0; the complementary f9=0 top chart and the "
            "five lower first-jet strata are separate dependencies"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / f"receipts/hsop-j2-secant-r10-f9-chart-{arguments.algorithm}-{field}.json"
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
