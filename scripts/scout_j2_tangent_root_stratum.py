#!/usr/bin/env python3
"""Bounded scouts for tangent first-nonzero-jet strata under ``j2=1``."""

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


root_inverse = sp.Symbol("rinv")


def stratum_system(
    top_index: int,
) -> tuple[list[sp.Expr], list[sp.Expr], tuple[sp.Symbol, ...], dict[str, str]]:
    equations, _ = normal_equations("tangent")
    substitutions: dict[sp.Symbol, sp.Expr] = {
        f_coefficients[index]: sp.Integer(0)
        for index in range(top_index + 1, 11)
    }
    substitutions[f_coefficients[top_index - 1]] = sp.Integer(0)
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    gauge = sp.expand((primitive_j2() - 1).subs(substitutions))
    localizer = sp.expand(root_inverse * f_coefficients[top_index] - 1)
    auxiliary = [gauge, localizer]
    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    variables = remaining_f + g_coefficients + (root_inverse,)
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + auxiliary):
        raise AssertionError("an eliminated jet coefficient survived")
    return reduced, auxiliary, variables, {
        str(symbol): str(value) for symbol, value in substitutions.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(5, 11), required=True)
    parser.add_argument("--characteristic", type=int, default=32003)
    parser.add_argument("--algorithm", choices=("std", "slimgb", "msolve"), default="std")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic != 0 and (
        arguments.characteristic <= 7 or not sp.isprime(arguments.characteristic)
    ):
        parser.error("characteristic must be zero or a prime greater than 7")
    if arguments.threads < 1:
        parser.error("threads must be positive")
    if arguments.algorithm == "msolve" and shutil.which("msolve") is None:
        raise SystemExit("msolve is required")
    if arguments.algorithm != "msolve" and shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    build_started = time.perf_counter()
    equations, auxiliary, variables, substitutions = stratum_system(arguments.top_index)
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
        if arguments.characteristic == 0 and arguments.algorithm == "msolve":
            disposition = "PROBABILISTIC_CHARACTERISTIC_ZERO_UNIT_SIGNAL"
        elif arguments.characteristic == 0:
            disposition = "EXACT_CHARACTERISTIC_ZERO_STRATUM_UNIT"
        else:
            disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-tangent-root-stratum-scout-v1",
        "orbit": "tangent",
        "gauge": "primitive_j2=1",
        "top_index": arguments.top_index,
        "root_multiplicity_at_tangent_point": 10 - arguments.top_index,
        "unipotent_normalization": f"f{arguments.top_index - 1}=0",
        "substitutions": substitutions,
        "characteristic": arguments.characteristic,
        "algorithm": arguments.algorithm,
        "arithmetic_assurance": (
            "probabilistic modular reconstruction over characteristic zero"
            if arguments.characteristic == 0 and arguments.algorithm == "msolve"
            else "deterministic exact arithmetic in the stated characteristic"
        ),
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
            "scripts/scout_j2_tangent_root_stratum.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "all six top-index strata are needed for the tangent orbit; modular "
            "units are route evidence; characteristic-zero msolve output is a "
            "probabilistic signal; a deterministic characteristic-zero Singular "
            "unit or independently verified rational certificate is exact for "
            "this normalized stratum"
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
