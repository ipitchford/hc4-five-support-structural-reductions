#!/usr/bin/env python3
"""Exact tail-ideal certificate for the tangent top-index-ten slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_coefficient_slice import coefficient_slice
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source


TAIL_INDICES = tuple(range(33, 55))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r10-tail-exact.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    normal_equations, _, full_variables, substitutions, j2 = coefficient_slice(10)
    tail = [normal_equations[index] for index in TAIL_INDICES]
    variables = tuple(
        variable for variable in full_variables if any(equation.has(variable) for equation in tail)
    )
    omitted = tuple(variable for variable in full_variables if variable not in variables)
    if tuple(map(str, omitted)) != ("f0", "j2inv"):
        raise AssertionError("the frozen tail support changed")
    if any(equation.has(*omitted) for equation in tail):
        raise AssertionError("an omitted variable occurs in the tail")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt_path = campaign / "receipts/residual-orbit-torus.json"
    torus_receipt = json.loads(torus_receipt_path.read_text(encoding="utf-8"))
    if torus_receipt.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    if torus_receipt["tangent"]["coefficient_weights"][10] != -16:
        raise AssertionError("the f10 coefficient-normalization weight changed")
    if 10 not in torus_receipt["tangent_unipotent"][
        "exhaustive_first_nonzero_indices_under_j2_nonzero"
    ]:
        raise AssertionError("top index ten is absent from the exhaustive cover")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(tail, [], variables, 0, source_algorithm)
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_TANGENT_R10_TAIL_UNIT"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_TANGENT_R10_TAIL"
    )
    result = {
        "schema": "hc4-decimic-j2-tangent-r10-tail-certificate-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 10,
        "coefficient_normalization": "f10=1",
        "coefficient_torus_weight": -16,
        "unipotent_normalization": "f9=0",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "selected_normal_equation_indices": list(TAIL_INDICES),
        "selected_normal_equation_count": len(tail),
        "localizer_count": 0,
        "omitted_unused_variables": [str(variable) for variable in omitted],
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree() for expression in tail
        ),
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "selected_equation_stream_sha256": digest(tuple(tail)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "torus_normalization_preconditions_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r10_tail.py": hashlib.sha256(
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
            "tangent top_index=10 coefficient slice from normal equations alone; "
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
