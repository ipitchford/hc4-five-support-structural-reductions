#!/usr/bin/env python3
"""Bounded scouts for one torus-normalized ``j2 != 0`` chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from certify_j2_open_cover import EXPECTED_MONOMIALS
from msolve_process import run_msolve_process
from scout_decimic_nullcone_hsop import (
    digest,
    f_coefficients,
    generic_decimic,
    normal_equations,
    render,
    run_source,
    selected_hsop,
)
from scout_five_support import g_coefficients


j2_inverse = sp.Symbol("jinv")
pair_inverse = sp.Symbol("pinv")


def primitive_j2() -> sp.Expr:
    raw = sp.Poly(selected_hsop(generic_decimic(), "j2"), *f_coefficients, domain=sp.ZZ)
    content = sp.gcd_list([coefficient for _, coefficient in raw.terms()])
    primitive = sp.expand(raw.as_expr() / content)
    if sp.Poly(primitive, *f_coefficients).LC() < 0:
        primitive = -primitive
    return primitive


def normalized_case(
    equations: list[sp.Expr], orbit: str, pair_index: int
) -> tuple[list[sp.Expr], sp.Expr, list[sp.Expr], tuple[sp.Symbol, ...], dict[str, object]]:
    left, right = EXPECTED_MONOMIALS[pair_index]
    substitutions: dict[sp.Symbol, sp.Expr] = {}
    if orbit == "tangent" or pair_index < 5:
        substitutions[f_coefficients[left]] = sp.Integer(1)

    reduced_equations = [sp.expand(equation.subs(substitutions)) for equation in equations]
    reduced_j2 = sp.expand(primitive_j2().subs(substitutions))

    localizers = [sp.expand(j2_inverse * reduced_j2 - 1)]
    if f_coefficients[left] in substitutions:
        pair_factor = f_coefficients[right]
    else:
        # The only unnormalized case is the secant central chart.  D(f5^2)
        # equals D(f5), and the linear localizer is smaller.
        pair_factor = f_coefficients[left]
    if pair_factor != 1:
        localizers.append(sp.expand(pair_inverse * pair_factor - 1))

    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    inverse_variables = (j2_inverse,) + ((pair_inverse,) if len(localizers) == 2 else ())
    variables = remaining_f + g_coefficients + inverse_variables
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced_equations + localizers):
        raise AssertionError("an eliminated coefficient survived normalization")
    metadata = {
        "pair_index": pair_index,
        "pair": [left, right],
        "pair_monomial": f"f{left}*f{right}" if left != right else f"f{left}^2",
        "substitutions": {str(key): render(value) for key, value in substitutions.items()},
        "pair_open_after_normalization": render(pair_factor),
        "variable_count": len(variables),
        "normal_equation_count": len(reduced_equations),
        "localizer_count": len(localizers),
    }
    return reduced_equations, reduced_j2, localizers, variables, metadata


def singular_source(
    equations: list[sp.Expr],
    localizers: list[sp.Expr],
    variables: tuple[sp.Symbol, ...],
    characteristic: int,
    algorithm: str,
) -> str:
    variable_source = ",".join(map(str, variables))
    header: list[str] = []
    if characteristic == 0:
        if algorithm == "std":
            header.extend(['LIB "modstd.lib";', f"ring r=0,({variable_source}),dp;"])
            basis_command = "ideal J=modStd(I);"
        elif algorithm == "qstd":
            header.append(f"ring r=0,({variable_source}),dp;")
            basis_command = "ideal J=std(I);"
        else:
            header.append(f"ring r=0,({variable_source}),dp;")
            basis_command = "ideal J=slimgb(I);"
    else:
        header.append(f"ring r={characteristic},({variable_source}),dp;")
        basis_command = "ideal J=std(I);" if algorithm == "std" else "ideal J=slimgb(I);"
    generators = ",".join(render(expression) for expression in equations + localizers)
    return "\n".join(
        header
        + [
            "option(redSB);",
            "ideal I=" + generators + ";",
            basis_command,
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )


def msolve_source(
    equations: list[sp.Expr],
    localizers: list[sp.Expr],
    variables: tuple[sp.Symbol, ...],
    characteristic: int,
) -> str:
    if characteristic < 0:
        raise ValueError("msolve characteristic must be zero or positive")
    generators = equations + localizers
    rows = [",".join(map(str, variables)), str(characteristic)]
    for index, expression in enumerate(generators):
        suffix = "," if index + 1 < len(generators) else ""
        rows.append(render(expression) + suffix)
    return "\n".join(rows) + "\n"


def run_msolve(source: str, timeout: int, threads: int) -> dict[str, object]:
    raw = run_msolve_process(source, timeout, threads)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    solver_output = str(raw.pop("solver_output"))
    clean_exit = not raw["timed_out"] and raw["return_code"] == 0
    no_solution = solver_output.strip().rstrip(":") == "[-1]"
    diagnostic_error = clean_exit and not solver_output.strip()
    return {
        **raw,
        "diagnostic_error": diagnostic_error,
        "is_unit": clean_exit and not diagnostic_error and no_solution,
        "unit_remainder": "0" if clean_exit and no_solution else None,
        "basis_size": None,
        "solver_output_tail": solver_output[-2000:],
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orbit", choices=("tangent", "secant"), required=True)
    parser.add_argument("--pair-index", type=int, choices=range(6), required=True)
    parser.add_argument("--characteristic", type=int, default=32003)
    parser.add_argument("--algorithm", choices=("std", "slimgb", "msolve"), default="std")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be zero or a positive prime")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")
    if arguments.algorithm == "msolve" and shutil.which("msolve") is None:
        raise SystemExit("msolve is required for the selected algorithm")
    if arguments.threads < 1:
        parser.error("threads must be positive")

    started = time.perf_counter()
    equations, build_seconds = normal_equations(arguments.orbit)
    reduced, j2, localizers, variables, metadata = normalized_case(
        equations, arguments.orbit, arguments.pair_index
    )
    if arguments.algorithm == "msolve":
        source = msolve_source(
            reduced, localizers, variables, arguments.characteristic
        )
        calculation = run_msolve(source, arguments.timeout, arguments.threads)
    else:
        source = singular_source(
            reduced,
            localizers,
            variables,
            arguments.characteristic,
            arguments.algorithm,
        )
        calculation = run_source(source, arguments.timeout)
    if calculation["diagnostic_error"]:
        disposition = "DIAGNOSTIC_ERROR"
    elif (
        arguments.characteristic == 0
        and arguments.algorithm == "msolve"
        and calculation["is_unit"]
    ):
        disposition = "PROBABILISTIC_CHARACTERISTIC_ZERO_UNIT_SIGNAL"
    elif arguments.characteristic == 0 and calculation["is_unit"]:
        disposition = "EXACT_NORMALIZED_CHART_UNIT"
    elif arguments.characteristic > 0 and calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    all_generators = reduced + localizers
    result = {
        "schema": "hc4-decimic-j2-normalized-chart-scout-v1",
        "orbit": arguments.orbit,
        "characteristic": arguments.characteristic,
        "algorithm": arguments.algorithm,
        "arithmetic_assurance": (
            "probabilistic modular reconstruction over characteristic zero"
            if arguments.characteristic == 0 and arguments.algorithm == "msolve"
            else "deterministic exact arithmetic in the stated characteristic"
        ),
        "threads": arguments.threads,
        **metadata,
        "equation_build_seconds": build_seconds,
        "generator_count": len(all_generators),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree() for expression in all_generators
        ),
        "j2_after_normalization": render(j2),
        "normal_equation_stream_sha256": digest(tuple(reduced)),
        "localizer_stream_sha256": digest(tuple(localizers)),
        "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_normalized_chart.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/msolve_process.py": hashlib.sha256(
                (script_path.parent / "msolve_process.py").read_bytes()
            ).hexdigest(),
            "scripts/scout_decimic_nullcone_hsop.py": hashlib.sha256(
                (script_path.parent / "scout_decimic_nullcone_hsop.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a finite-characteristic unit is route evidence only; a timeout "
            "or nonunit is not a mathematical survivor; characteristic-zero "
            "msolve output in characteristic zero is probabilistic route evidence; "
            "deterministic characteristic-zero certificates are required on every "
            "cover case"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        output = arguments.output
        if not output.is_absolute():
            output = campaign / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
