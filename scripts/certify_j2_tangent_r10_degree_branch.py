#!/usr/bin/env python3
"""Exact single-branch replay for the tangent r=10 degree decomposition."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_coefficient_slice import coefficient_slice
from certify_j2_tangent_r10_degree_branches import branch_systems
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source


BRANCH_NAMES = ("degree_6", "degree_5", "degree_4", "degree_3", "A_zero")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    normal_equations, _, full_variables, substitutions, j2 = coefficient_slice(10)
    A, C, branches = branch_systems(normal_equations, full_variables)
    branch = branches[arguments.branch]

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt_path = campaign / "receipts/residual-orbit-torus.json"
    torus_receipt = json.loads(torus_receipt_path.read_text(encoding="utf-8"))
    if torus_receipt.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    if torus_receipt["tangent"]["coefficient_weights"][10] != -16:
        raise AssertionError("the f10 coefficient-normalization weight changed")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(
        branch["equations"], [], branch["variables"], 0, source_algorithm
    )
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_TANGENT_R10_DEGREE_BRANCH_UNIT"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_TANGENT_R10_DEGREE_BRANCH"
    )
    result = {
        "schema": "hc4-decimic-j2-tangent-r10-single-degree-branch-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 10,
        "branch": arguments.branch,
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
        "coefficient_normalization": "f10=1",
        "unipotent_normalization": "f9=0",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "A_sha256": digest((A,)),
        "C_sha256": digest((C,)),
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
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r10_degree_branch.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_r10_degree_branches.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_r10_degree_branches.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                torus_receipt_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact emptiness of this single necessary "
            "degree branch; all five branch receipts are required for r=10"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-tangent-r10-{arguments.branch}-{arguments.algorithm}-exact.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
