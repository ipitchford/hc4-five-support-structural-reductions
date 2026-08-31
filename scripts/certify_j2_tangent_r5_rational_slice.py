#!/usr/bin/env python3
"""Deterministic characteristic-zero certificate for the rational r=5 slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import singular_source


SELECTED_INDICES = (33, 35, 36, 37, 38, 45, 46, 47, 48, 49, 50, 51, 52)


def rational_slice() -> tuple[list[sp.Expr], tuple[sp.Symbol, ...], dict[str, int]]:
    equations, _ = normal_equations("tangent")
    substitutions = {
        f_coefficients[4]: 0,
        f_coefficients[5]: 1,
        f_coefficients[6]: 0,
        f_coefficients[7]: 0,
        f_coefficients[8]: 0,
        f_coefficients[9]: 0,
        f_coefficients[10]: 0,
    }
    selected = [sp.expand(equations[index].subs(substitutions)) for index in SELECTED_INDICES]
    variables = tuple(
        symbol for symbol in f_coefficients if symbol not in substitutions
    ) + g_coefficients
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in selected):
        raise AssertionError("an eliminated coefficient survived the rational slice")
    return selected, variables, {str(key): value for key, value in substitutions.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithm", choices=("qstd", "slimgb"), default="qstd")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-rational-slice-char0.json"),
    )
    arguments = parser.parse_args()

    started = time.perf_counter()
    equations, variables, substitutions = rational_slice()
    source = singular_source(equations, [], variables, 0, arguments.algorithm)
    calculation = run_source(source, arguments.timeout)
    if calculation["diagnostic_error"]:
        status = "DIAGNOSTIC_ERROR"
    elif calculation["is_unit"]:
        status = "PASS_EXACT_CHARACTERISTIC_ZERO_UNIT"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-tangent-r5-rational-slice-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 5,
        "gauge": "primitive_j2=-5",
        "sign_normalization": "f5=1 via the residual-preserving sigma=-1 action",
        "substitutions": substitutions,
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "selected_normal_equation_indices": list(SELECTED_INDICES),
        "generator_count": len(equations),
        "variable_count": len(variables),
        "equation_stream_sha256": digest(tuple(equations)),
        "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r5_rational_slice.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing deterministic Singular receipt closes only the tangent "
            "top_index=5 stratum; higher tangent strata and the secant orbit remain"
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status == "PASS_EXACT_CHARACTERISTIC_ZERO_UNIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
