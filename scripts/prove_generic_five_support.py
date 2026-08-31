#!/usr/bin/env python3
"""Characteristic-zero five-support double-conic chart calculations.

Two modes are available:

* ``function-field`` computes over QQ(lambda,mu), proving generic emptiness;
* ``polynomial-open`` computes over QQ[lambda,mu,...] localized away from the
  five-root discriminant product, proving the complete normalized open chart.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import canonical_lift, q, s, t, x, y, z
from scout_five_support import (
    CHARTS,
    PARTITIONS,
    chart_symbols,
    general_cubic,
    inverse,
    line_x,
    line_y,
    line_z,
    unknowns,
)
from singular_process import run_singular_process


lambda_parameter, mu_parameter = sp.symbols("la mu")


def parse_partition(text: str) -> tuple[int, ...]:
    partition = tuple(int(value) for value in text.split(","))
    if partition not in PARTITIONS:
        raise argparse.ArgumentTypeError(
            f"partition must be one of {PARTITIONS}"
        )
    return partition


def symbolic_binary_form(partition: tuple[int, ...]) -> sp.Expr:
    a, b, c, d, e = partition
    return sp.expand(
        s**a
        * t**b
        * (s - t) ** c
        * (s - lambda_parameter * t) ** d
        * (s - mu_parameter * t) ** e
    )


def equations_for(partition: tuple[int, ...]) -> tuple[list[sp.Expr], float]:
    started = time.perf_counter()
    h5 = canonical_lift(symbolic_binary_form(partition), 5) + q * general_cubic
    target = q**4 * (line_x * x + line_y * y + line_z * z)
    polynomial = sp.Poly(
        sp.expand(sp.hessian(h5, (x, y, z)).det() - target), x, y, z
    )
    equations = [coefficient for _, coefficient in polynomial.terms()]
    assert len(equations) == 55
    return equations, time.perf_counter() - started


def render_expression(expression: sp.Expr) -> str:
    return str(sp.expand(expression)).replace("**", "^")


def equation_hash(equations: list[sp.Expr]) -> str:
    return hashlib.sha256(
        "\n".join(render_expression(equation) for equation in equations).encode(
            "ascii"
        )
    ).hexdigest()


def source_for(
    equations: list[sp.Expr], chart: str, mode: str
) -> str:
    equation_source = ",".join(render_expression(eq) for eq in equations)
    variable_source = ",".join(map(str, unknowns))
    if mode == "function-field":
        localization = render_expression(inverse * chart_symbols[chart] - 1)
        header = [
            'LIB "ffmodstd.lib";',
            f"ring r=(0,{lambda_parameter},{mu_parameter}),"
            f"({variable_source}),dp;",
        ]
        standard_basis = "ideal J=ffmodStd(I);"
    else:
        root_open = (
            lambda_parameter
            * mu_parameter
            * (lambda_parameter - 1)
            * (mu_parameter - 1)
            * (lambda_parameter - mu_parameter)
        )
        localization = render_expression(
            inverse * chart_symbols[chart] * root_open - 1
        )
        all_variables = ",".join(
            map(str, (lambda_parameter, mu_parameter) + unknowns)
        )
        header = ['LIB "modstd.lib";', f"ring r=0,({all_variables}),dp;"]
        standard_basis = "ideal J=modStd(I);"
    return "\n".join(
        header
        + [
            "option(redSB);",
            "ideal I=" + equation_source + "," + localization + ";",
            standard_basis,
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )


def parse_marker(output: str, marker: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(marker)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def run_one(
    equations: list[sp.Expr], chart: str, mode: str, timeout: int
) -> dict[str, object]:
    source = source_for(equations, chart, mode)
    raw = run_singular_process(source, timeout)
    stdout_text = str(raw.pop("stdout"))
    stderr_text = str(raw.pop("stderr"))
    diagnostic_error = (
        "error occurred" in stdout_text
        or "expected ideal-expression" in stdout_text
        or "error occurred" in stderr_text
    )
    remainder = parse_marker(stdout_text, "UNIT_REMAINDER")
    basis_size = parse_marker(stdout_text, "BASIS_SIZE")
    return {
        "chart": chart,
        "mode": mode,
        **raw,
        "unit_remainder": remainder,
        "basis_size": basis_size,
        "diagnostic_error": diagnostic_error,
        "is_unit": (
            not raw["timed_out"]
            and raw["return_code"] == 0
            and not diagnostic_error
            and remainder == "0"
        ),
        "stdout_tail": stdout_text[-2000:],
        "stderr_tail": stderr_text[-2000:],
        "singular_source_sha256": hashlib.sha256(
            source.encode("ascii")
        ).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", type=parse_partition, required=True)
    parser.add_argument("--chart", choices=CHARTS, required=True)
    parser.add_argument(
        "--mode",
        choices=("function-field", "polynomial-open"),
        default="function-field",
    )
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    equations, build_seconds = equations_for(args.partition)
    calculation = run_one(equations, args.chart, args.mode, args.timeout)
    if args.mode == "function-field" and calculation["is_unit"]:
        disposition = "EXACT_GENERIC_UNIT_IDEAL"
    elif args.mode == "polynomial-open" and calculation["is_unit"]:
        disposition = "EXACT_COMPLETE_FIVE_SUPPORT_CHART"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"
    result = {
        "schema": "hc4-double-conic-five-support-characteristic-zero-v1",
        "partition": list(args.partition),
        "chart": args.chart,
        "mode": args.mode,
        "equation_count": len(equations),
        "equation_stream_sha256": equation_hash(equations),
        "equation_build_seconds": build_seconds,
        "calculation": calculation,
        "disposition": disposition,
        "claim_boundary": (
            "function-field units prove generic emptiness only; polynomial-open "
            "units prove the normalized five-support chart and leave only the "
            "support-collision divisor"
        ),
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
