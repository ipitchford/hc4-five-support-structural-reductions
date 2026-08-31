#!/usr/bin/env python3
"""F4 route scout for one Laurent-reduced secant ``r=10`` branch."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from scout_decimic_nullcone_hsop import digest
from scout_j2_normalized_chart import msolve_source
from msolve_process import run_msolve_process


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--verbose", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")
    if arguments.threads < 1:
        parser.error("threads must be positive")

    started = time.perf_counter()
    A, C, tail_indices, j2, branches = laurent_branches()
    branch = branches[arguments.branch]
    source = msolve_source(
        branch["equations"], [], branch["variables"], arguments.characteristic
    )
    raw = run_msolve_process(
        source, arguments.timeout, arguments.threads, verbose=arguments.verbose
    )
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    solver_output = str(raw.pop("solver_output"))
    clean_exit = not raw["timed_out"] and raw["return_code"] == 0
    no_solution = solver_output.strip().rstrip(":") == "[-1]"
    diagnostic_error = clean_exit and not solver_output.strip()
    calculation = {
        **raw,
        "diagnostic_error": diagnostic_error,
        "is_unit": clean_exit and not diagnostic_error and no_solution,
        "unit_remainder": "0" if clean_exit and no_solution else None,
        "basis_size": None,
        "solver_output_tail": solver_output[-2000:],
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-12000:] if arguments.verbose == 2 else stderr[-2000:],
    }
    if calculation["is_unit"]:
        status = (
            "PASS_MODULAR_NO_SOLUTION_SIGNAL"
            if arguments.characteristic > 0
            else "PASS_PROBABILISTIC_QQ_NO_SOLUTION_SIGNAL"
        )
    else:
        status = "INCOMPLETE_MSOLVE_ROUTE_SCOUT"
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-laurent-msolve-scout-v1",
        "status": status,
        "assurance": "modular route signal" if arguments.characteristic > 0 else "probabilistic characteristic-zero route signal",
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "threads": arguments.threads,
        "verbose": arguments.verbose,
        "variable_count": len(branch["variables"]),
        "equation_count": len(branch["equations"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *branch["variables"]).total_degree()
            for expression in branch["equations"]
        ),
        "equation_stream_sha256": digest(tuple(branch["equations"])),
        "msolve_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_secant_r10_f9_laurent_msolve.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this scout selects or falsifies a route only; it is not an exact "
            "characteristic-zero certificate and cannot close the branch"
        ),
    }
    if arguments.output is None:
        field = f"p{arguments.characteristic}" if arguments.characteristic > 0 else "qq"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-laurent-{arguments.branch}-msolve-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
