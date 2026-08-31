#!/usr/bin/env python3
"""Exact coefficient-normalized secant j2 certificate for one top stratum."""

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
top_inverse = sp.Symbol("topinv")


def coefficient_slice(top_index: int):
    equations, _ = normal_equations("secant")
    substitutions = {
        f_coefficients[index]: 0 for index in range(top_index + 1, 11)
    }
    if top_index >= 6:
        substitutions[f_coefficients[top_index]] = 1
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    j2 = sp.expand(primitive_j2().subs(substitutions))
    if top_index == 5:
        if j2 != -5 * f_coefficients[5] ** 2:
            raise AssertionError("the central secant j2 identity changed")
        auxiliary = [sp.expand(top_inverse * f_coefficients[5] - 1)]
    else:
        auxiliary = [sp.expand(j2_inverse * j2 - 1)]
    remaining_f = tuple(
        coefficient for coefficient in f_coefficients if coefficient not in substitutions
    )
    inverse_variables = (top_inverse,) if top_index == 5 else (j2_inverse,)
    variables = remaining_f + g_coefficients + inverse_variables
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + auxiliary):
        raise AssertionError("an eliminated coefficient survived the secant slice")
    return (
        reduced,
        auxiliary,
        variables,
        {str(symbol): int(value) for symbol, value in substitutions.items()},
        j2,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(5, 11), required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    equations, auxiliary, variables, substitutions, j2 = coefficient_slice(
        arguments.top_index
    )

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    cover_path = campaign / "receipts/secant-first-jet-cover.json"
    cover = json.loads(cover_path.read_text(encoding="utf-8"))
    if cover.get("status") != "PASS":
        raise AssertionError("the secant first-jet cover is not passing")
    if arguments.top_index not in cover["first_nonzero_jet_indices"]:
        raise AssertionError("the selected top index is absent from the exact cover")
    if arguments.top_index >= 6 and cover["strata"][str(arguments.top_index)]["top_weight"] == 0:
        raise AssertionError("the selected top coefficient cannot be normalized")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(equations, auxiliary, variables, 0, source_algorithm)
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_SECANT_STRATUM_EMPTY"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_SECANT_STRATUM"
    )
    result = {
        "schema": "hc4-decimic-j2-secant-coefficient-slice-v1",
        "status": status,
        "orbit": "secant",
        "top_index": arguments.top_index,
        "coefficient_normalization": (
            f"f{arguments.top_index}=1"
            if arguments.top_index >= 6
            else "f5!=0 with explicit inverse"
        ),
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_equation_count": len(equations),
        "auxiliary_equation_count": len(auxiliary),
        "generator_count": len(equations) + len(auxiliary),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + auxiliary
        ),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "cover_preconditions_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_coefficient_slice.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_secant_first_jet_cover.py": hashlib.sha256(
                (script_path.parent / "certify_secant_first_jet_cover.py").read_bytes()
            ).hexdigest(),
            "receipts/secant-first-jet-cover.json": hashlib.sha256(
                cover_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact characteristic-zero emptiness of this "
            "single secant first-nonzero-jet stratum; all six secant strata are required"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-secant-r{arguments.top_index}-coefficient-slice-exact.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
