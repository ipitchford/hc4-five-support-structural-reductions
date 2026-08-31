#!/usr/bin/env python3
"""Track a Singular ``liftstd`` certificate for secant ``r=10`` degree four."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from scout_decimic_nullcone_hsop import digest, render, run_source


def liftstd_source(equations, variables, characteristic: int, algorithm: str) -> str:
    variable_source = ",".join(map(str, variables))
    generators = ",".join(render(equation) for equation in equations)
    return "\n".join(
        [
            f"ring r={characteristic},({variable_source}),dp;",
            "option(redSB);",
            "ideal I=" + generators + ";",
            "matrix T;",
            f'ideal J=liftstd(I,T,"{algorithm}");',
            "matrix D=matrix(J)-matrix(I)*T;",
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            'print("BASIS_FIRST");',
            "J[1];",
            'print("TRANSFORMATION_ZERO");',
            "D==0;",
            'print("TRANSFORMATION_ROWS");',
            "nrows(T);",
            'print("TRANSFORMATION_COLUMNS");',
            "ncols(T);",
            "exit;",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, default="degree_4")
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--generator-index", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    _, _, _, _, branches = laurent_branches()
    branch = branches[arguments.branch]
    original_equations = list(branch["equations"])
    if arguments.generator_index:
        generator_indices = tuple(dict.fromkeys(arguments.generator_index))
        if any(index < 0 or index >= len(original_equations) for index in generator_indices):
            parser.error(
                f"every generator index must lie in 0..{len(original_equations) - 1}"
            )
        equations = [original_equations[index] for index in generator_indices]
    else:
        generator_indices = tuple(range(len(original_equations)))
        equations = original_equations
    variables = tuple(
        variable
        for variable in branch["variables"]
        if any(equation.has(variable) for equation in equations)
    )
    source = liftstd_source(
        equations, variables, arguments.characteristic, arguments.algorithm
    )
    calculation = run_source(source, arguments.timeout)
    stdout = str(calculation.get("stdout_tail", ""))
    transformation_zero = "TRANSFORMATION_ZERO\n1" in stdout
    exact = arguments.characteristic == 0
    passed = calculation["is_unit"] and transformation_zero
    if passed:
        status = (
            "PASS_EXACT_LIFTSTD_IDENTITY"
            if exact
            else "PASS_MODULAR_LIFTSTD_IDENTITY"
        )
    else:
        status = "INCOMPLETE_LIFTSTD_IDENTITY"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-liftstd-v1",
        "status": status,
        "assurance": "exact characteristic zero" if exact else "exact finite characteristic only",
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "algorithm": "Singular liftstd/" + arguments.algorithm,
        "variable_count": len(variables),
        "variable_names": [str(variable) for variable in variables],
        "original_equation_count": len(original_equations),
        "equation_count": len(equations),
        "retained_generator_indices": list(generator_indices),
        "equation_stream_sha256": digest(tuple(equations)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "transformation_identity_verified": transformation_zero,
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_f9_liftstd.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "only a characteristic-zero passing receipt proves this one branch "
            "empty; a modular transformation is a certificate-engine scout"
        ),
    }
    if arguments.output is None:
        field = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-{arguments.branch}-liftstd-"
            f"{arguments.algorithm}-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
