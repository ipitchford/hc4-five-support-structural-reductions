#!/usr/bin/env python3
"""Bounded scout for the global tangent-orbit gauge ``j2 = 1``."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import (
    digest,
    f_coefficients,
    normal_equations,
    render,
    run_source,
)
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import (
    msolve_source,
    primitive_j2,
    run_msolve,
    singular_source,
)


def main() -> int:
    parser = argparse.ArgumentParser()
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
    equations, build_seconds = normal_equations("tangent")
    gauge = sp.expand(primitive_j2() - 1)
    variables = f_coefficients + g_coefficients
    generators = equations + [gauge]
    if arguments.algorithm == "msolve":
        source = msolve_source(equations, [gauge], variables, arguments.characteristic)
        calculation = run_msolve(source, arguments.timeout, arguments.threads)
    else:
        source = singular_source(
            equations,
            [gauge],
            variables,
            arguments.characteristic,
            arguments.algorithm,
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
        "schema": "hc4-decimic-j2-tangent-global-gauge-scout-v1",
        "orbit": "tangent",
        "gauge": "primitive_j2=1",
        "gauge_justification": (
            "the residual-preserving tangent torus gives primitive_j2 weight -2"
        ),
        "characteristic": arguments.characteristic,
        "algorithm": arguments.algorithm,
        "threads": arguments.threads,
        "variable_count": len(variables),
        "normal_equation_count": len(equations),
        "generator_count": len(generators),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree() for expression in generators
        ),
        "equation_build_seconds": build_seconds,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "gauge_sha256": digest((gauge,)),
        "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_tangent_gauge.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/scout_j2_normalized_chart.py": hashlib.sha256(
                (script_path.parent / "scout_j2_normalized_chart.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a modular unit is route evidence only; an exact characteristic-zero "
            "certificate is required for tangent j2 radical containment"
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
