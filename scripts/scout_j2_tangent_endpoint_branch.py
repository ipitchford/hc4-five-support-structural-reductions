#!/usr/bin/env python3
"""Bounded scouts for the two exact tangent endpoint branches."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import msolve_source, primitive_j2, run_msolve, singular_source


endpoint_inverse = sp.Symbol("einv")


def branch_system(
    branch: str,
) -> tuple[list[sp.Expr], list[sp.Expr], tuple[sp.Symbol, ...], dict[str, str]]:
    equations, _ = normal_equations("tangent")
    if branch == "endpoint_zero":
        substitutions = {f_coefficients[10]: sp.Integer(0)}
        localizers: list[sp.Expr] = []
    else:
        substitutions = {f_coefficients[9]: sp.Integer(0)}
        localizers = [sp.expand(endpoint_inverse * f_coefficients[10] - 1)]
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    gauge = sp.expand((primitive_j2() - 1).subs(substitutions))
    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    variables = remaining_f + g_coefficients + ((endpoint_inverse,) if localizers else ())
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + [gauge] + localizers):
        raise AssertionError("eliminated endpoint coefficient survived")
    return reduced, [gauge] + localizers, variables, {
        str(symbol): str(value) for symbol, value in substitutions.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=("endpoint_zero", "endpoint_nonzero"), required=True)
    parser.add_argument("--characteristic", type=int, default=32003)
    parser.add_argument("--algorithm", choices=("std", "slimgb", "msolve"), default="std")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 7 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than 7")
    if arguments.threads < 1:
        parser.error("threads must be positive")
    if arguments.algorithm == "msolve" and shutil.which("msolve") is None:
        raise SystemExit("msolve is required")
    if arguments.algorithm != "msolve" and shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    build_started = time.perf_counter()
    equations, auxiliary, variables, substitutions = branch_system(arguments.branch)
    build_seconds = time.perf_counter() - build_started
    generators = equations + auxiliary
    if arguments.algorithm == "msolve":
        source = msolve_source(equations, auxiliary, variables, arguments.characteristic)
        calculation = run_msolve(source, arguments.timeout, arguments.threads)
    else:
        source = singular_source(
            equations, auxiliary, variables, arguments.characteristic, arguments.algorithm
        )
        calculation = run_source(source, arguments.timeout)
    if calculation["diagnostic_error"]:
        disposition = "DIAGNOSTIC_ERROR"
    elif calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-tangent-endpoint-branch-scout-v1",
        "orbit": "tangent",
        "gauge": "primitive_j2=1",
        "branch": arguments.branch,
        "substitutions": substitutions,
        "characteristic": arguments.characteristic,
        "algorithm": arguments.algorithm,
        "threads": arguments.threads,
        "variable_count": len(variables),
        "normal_equation_count": len(equations),
        "auxiliary_equation_count": len(auxiliary),
        "generator_count": len(generators),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree() for expression in generators
        ),
        "equation_build_seconds": build_seconds,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_tangent_endpoint_branch.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "the two branches are exhaustive only together; a modular unit is "
            "route evidence and requires characteristic-zero lifting"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        output = arguments.output
        if not output.is_absolute():
            output = campaign / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
