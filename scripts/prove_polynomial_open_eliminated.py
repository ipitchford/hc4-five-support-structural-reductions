#!/usr/bin/env python3
"""Polynomial-open five-support proof with the residual line eliminated.

For D = det Hess(h5), the three coefficients at x^5*z^4, x^4*y*z^4,
and x^4*z^5 are exactly the prospective residual-line coordinates A, B,
and C.  Extracting them before the standard-basis calculation removes the
three line variables and their defining pivot equations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from prove_generic_five_support import (
    lambda_parameter,
    mu_parameter,
    parse_partition,
    render_expression,
    symbolic_binary_form,
)
from reconstruct_normal_layers import canonical_lift, q, x, y, z
from scout_five_support import CHARTS, general_cubic
from singular_process import run_singular_process


inverse = sp.Symbol("inv")


def eliminated_system(
    partition: tuple[int, ...],
) -> tuple[list[sp.Expr], dict[str, sp.Expr], float]:
    started = time.perf_counter()
    h5 = canonical_lift(symbolic_binary_form(partition), 5) + q * general_cubic
    determinant = sp.expand(sp.hessian(h5, (x, y, z)).det())
    polynomial = sp.Poly(determinant, x, y, z)
    lines = {
        "line_x": polynomial.coeff_monomial(x**5 * z**4),
        "line_y": polynomial.coeff_monomial(x**4 * y * z**4),
        "line_z": polynomial.coeff_monomial(x**4 * z**5),
    }
    residual = sp.Poly(
        sp.expand(
            determinant
            - q**4
            * (lines["line_x"] * x + lines["line_y"] * y + lines["line_z"] * z)
        ),
        x,
        y,
        z,
    )
    equations = [
        coefficient for _, coefficient in residual.terms() if coefficient != 0
    ]
    if any(
        residual.coeff_monomial(monomial) != 0
        for monomial in (x**5 * z**4, x**4 * y * z**4, x**4 * z**5)
    ):
        raise AssertionError("residual-line pivot extraction failed")
    return equations, lines, time.perf_counter() - started


def stream_digest(expressions: list[sp.Expr]) -> str:
    payload = "\n".join(render_expression(expression) for expression in expressions)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def source_for(
    equations: list[sp.Expr], chart_expression: sp.Expr, global_affine: bool
) -> str:
    root_open = (
        lambda_parameter
        * mu_parameter
        * (lambda_parameter - 1)
        * (mu_parameter - 1)
        * (lambda_parameter - mu_parameter)
    )
    cubic_symbols = tuple(
        sorted(general_cubic.free_symbols, key=lambda symbol: str(symbol))
    )
    variables = (lambda_parameter, mu_parameter) + cubic_symbols + (inverse,)
    variable_source = ",".join(map(str, variables))
    equation_source = ",".join(
        render_expression(equation) for equation in equations
    )
    open_factor = sp.Integer(1) if global_affine else root_open
    localization = render_expression(
        inverse * chart_expression * open_factor - 1
    )
    return "\n".join(
        [
            'LIB "modstd.lib";',
            f"ring r=0,({variable_source}),dp;",
            "option(redSB);",
            "ideal I=" + equation_source + "," + localization + ";",
            "ideal J=modStd(I);",
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def run_source(source: str, timeout: int) -> dict[str, object]:
    raw = run_singular_process(source, timeout)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    diagnostic_error = (
        "error occurred" in stdout
        or "error occurred" in stderr
        or "expected ideal-expression" in stdout
        or "expected ideal-expression" in stderr
    )
    remainder = marker(stdout, "UNIT_REMAINDER")
    return {
        **raw,
        "diagnostic_error": diagnostic_error,
        "unit_remainder": remainder,
        "basis_size": marker(stdout, "BASIS_SIZE"),
        "is_unit": (
            not raw["timed_out"]
            and raw["return_code"] == 0
            and not diagnostic_error
            and remainder == "0"
        ),
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", type=parse_partition, required=True)
    parser.add_argument("--chart", choices=CHARTS, required=True)
    parser.add_argument(
        "--global-affine",
        action="store_true",
        help="localize only by the residual-line chart, including collisions",
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    equations, lines, build_seconds = eliminated_system(arguments.partition)
    source = source_for(
        equations, lines[arguments.chart], arguments.global_affine
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"]:
        disposition = "EXACT_COMPLETE_FIVE_SUPPORT_CHART"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"
    result = {
        "schema": "hc4-five-support-polynomial-open-eliminated-v1",
        "partition": list(arguments.partition),
        "chart": arguments.chart,
        "mode": (
            "global-affine-eliminated-line"
            if arguments.global_affine
            else "polynomial-open-eliminated-line"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "equation_build_seconds": build_seconds,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "claim_boundary": (
            "a global-affine unit proves every finite parameter fiber in the "
            "chart; an open unit proves the normalized distinct-five-root "
            "chart and leaves the support-collision divisor Delta=0"
        ),
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
