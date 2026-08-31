#!/usr/bin/env python3
"""Exact 16-variable convolution certificate for tangent top index ten."""

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


SELECTED_INDICES = tuple(range(36, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r10-convolution-exact.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    normal_equations, _, full_variables, substitutions, j2 = coefficient_slice(10)
    selected = [normal_equations[index] for index in SELECTED_INDICES]
    variables = tuple(
        variable
        for variable in full_variables
        if any(equation.has(variable) for equation in selected)
    )
    omitted = tuple(variable for variable in full_variables if variable not in variables)
    if tuple(map(str, omitted)) != ("f0", "f1", "f2", "j2inv"):
        raise AssertionError("the frozen 16-variable support changed")

    f3 = f_coefficients[3]
    f4 = f_coefficients[4]
    convolution_rows: list[dict[str, sp.Expr]] = []
    for index in CONVOLUTION_INDICES:
        equation = normal_equations[index]
        coefficient_f3 = sp.diff(equation, f3)
        coefficient_f4 = sp.diff(equation, f4)
        constant = sp.expand(equation - coefficient_f3 * f3 - coefficient_f4 * f4)
        if constant.has(f3, f4):
            raise AssertionError(f"equation {index} is not linear in f3,f4")
        convolution_rows.append(
            {"a": coefficient_f3, "b": coefficient_f4, "c": constant}
        )
    if convolution_rows[0]["b"] != 0 or convolution_rows[-1]["a"] != 0:
        raise AssertionError("the convolution endpoints changed")
    for row in range(1, len(convolution_rows)):
        if sp.expand(convolution_rows[row]["b"] - convolution_rows[row - 1]["a"]) != 0:
            raise AssertionError("the convolution shift identity failed")
    base_indices = (36,) + tuple(range(45, 55))
    if any(normal_equations[index].has(f3, f4) for index in base_indices):
        raise AssertionError("a base equation contains a fibre variable")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt_path = campaign / "receipts/residual-orbit-torus.json"
    torus_receipt = json.loads(torus_receipt_path.read_text(encoding="utf-8"))
    if torus_receipt.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    if torus_receipt["tangent"]["coefficient_weights"][10] != -16:
        raise AssertionError("the f10 coefficient-normalization weight changed")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(selected, [], variables, 0, source_algorithm)
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_TANGENT_R10_CONVOLUTION_UNIT"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_TANGENT_R10_CONVOLUTION"
    )
    coefficient_stream = tuple(
        entry[key]
        for entry in convolution_rows
        for key in ("a", "b", "c")
    )
    result = {
        "schema": "hc4-decimic-j2-tangent-r10-convolution-certificate-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 10,
        "coefficient_normalization": "f10=1",
        "coefficient_torus_weight": -16,
        "unipotent_normalization": "f9=0",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "selected_normal_equation_indices": list(SELECTED_INDICES),
        "selected_normal_equation_count": len(selected),
        "base_equation_indices": list(base_indices),
        "convolution_equation_indices": list(CONVOLUTION_INDICES),
        "convolution_identity_verified": True,
        "convolution_coefficient_stream_sha256": digest(coefficient_stream),
        "omitted_unused_variables": [str(variable) for variable in omitted],
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree() for expression in selected
        ),
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "selected_equation_stream_sha256": digest(tuple(selected)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "torus_normalization_preconditions_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r10_convolution.py": hashlib.sha256(
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
            "tangent top_index=10 coefficient slice from equations 36 through 54; "
            "tangent j2 containment additionally requires the other five strata"
        ),
    }
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
