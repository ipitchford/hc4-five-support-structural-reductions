#!/usr/bin/env python3
"""Replay one exact or modular branch of the secant ``r=10`` cover."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_degree_branches import secant_branch_systems
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source


BRANCH_NAMES = ("degree_6", "degree_5", "degree_4", "degree_3", "A_zero")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        raise ValueError("the characteristic must be nonnegative")

    started = time.perf_counter()
    A, C, substitutions, j2, branches = secant_branch_systems()
    branch = branches[arguments.branch]
    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(
        branch["equations"],
        [],
        branch["variables"],
        arguments.characteristic,
        source_algorithm,
    )
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    exact = arguments.characteristic == 0
    if calculation["is_unit"]:
        status = (
            "PASS_EXACT_SECANT_R10_DEGREE_BRANCH_UNIT"
            if exact
            else "PASS_MODULAR_SECANT_R10_DEGREE_BRANCH_UNIT"
        )
    else:
        status = (
            "INCOMPLETE_EXACT_SECANT_R10_DEGREE_BRANCH"
            if exact
            else "INCOMPLETE_MODULAR_SECANT_R10_DEGREE_BRANCH"
        )

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-single-degree-branch-v1",
        "status": status,
        "orbit": "secant",
        "top_index": 10,
        "branch": arguments.branch,
        "zero_substitutions": {
            str(symbol): str(value)
            for symbol, value in branch["zero_substitutions"].items()
        },
        "leading_form": (
            str(branch["leading_form"])
            if branch["leading_form"] is not None
            else None
        ),
        "A_degree": branch["expected_degree"],
        "coefficient_normalization": "f10=1",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "A_sha256": digest((A,)),
        "C_sha256": digest((C,)),
        "base_equation_count": len(branch["base"]),
        "compatibility_equation_count": len(branch["compatibility"]),
        "localizer_equation_count": len(branch["localizer"]),
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
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_degree_branch.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_degree_branches.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_degree_branches.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_coefficient_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a characteristic-zero passing receipt proves emptiness of this single "
            "necessary secant r=10 degree branch on j2!=0; all five exact branch "
            "receipts are required for the r=10 stratum"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-{arguments.branch}-{arguments.algorithm}-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
