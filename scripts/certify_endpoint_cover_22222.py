#!/usr/bin/env python3
"""Certify the nested endpoint cover for the (2,2,2,2,2) stratum.

The proof is deliberately split at every factor that is divided by.  Thus the
certificate covers the internal W=0 and R=0 fibres rather than treating them
as exceptional parameter divisors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from prove_generic_five_support import (
    lambda_parameter,
    mu_parameter,
    render_expression,
)
from prove_polynomial_open_eliminated import eliminated_system, stream_digest
from scout_five_support import g_coefficients
from singular_process import run_singular_process


PARTITION = (2, 2, 2, 2, 2)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients
la, mu = lambda_parameter, mu_parameter
w, u, inverse = sp.symbols("w u inv")
DELTA = la * mu * (la - 1) * (mu - 1) * (la - mu)
T = la + mu + 1
A = la**2 * mu**2
R = la**2 - 2 * la * mu - 2 * la + mu**2 - 2 * mu + u + 1


def digest(expression: sp.Expr) -> str:
    return hashlib.sha256(str(sp.expand(expression)).encode("ascii")).hexdigest()


def check(actual: sp.Expr, expected: sp.Expr, label: str) -> None:
    difference = sp.cancel(actual - expected)
    if difference != 0:
        raise AssertionError(f"{label} failed: {sp.factor(difference)}")


def solve_linear(expression: sp.Expr, variable: sp.Symbol, label: str) -> sp.Expr:
    polynomial = sp.Poly(sp.together(expression), variable)
    if polynomial.degree() != 1:
        raise AssertionError(f"{label} is not linear in {variable}")
    return sp.cancel(-polynomial.nth(0) / polynomial.nth(1))


def primitive_numerator(
    expression: sp.Expr, variables: tuple[sp.Symbol, ...]
) -> sp.Expr:
    numerator, _ = sp.together(expression).as_numer_denom()
    if numerator == 0:
        return sp.Integer(0)
    polynomial = sp.Poly(sp.expand(numerator), *variables)
    return polynomial.primitive()[1].as_expr()


def reduced_numerators(
    expressions: list[sp.Expr],
    substitutions: dict[sp.Symbol, sp.Expr | int],
    variables: tuple[sp.Symbol, ...],
) -> list[sp.Expr]:
    result: list[sp.Expr] = []
    seen: set[str] = set()
    for expression in expressions:
        numerator = primitive_numerator(expression.subs(substitutions), variables)
        key = str(numerator)
        if numerator != 0 and key not in seen:
            seen.add(key)
            result.append(numerator)
    return result


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def unit_tests(
    *,
    label: str,
    variables: tuple[sp.Symbol, ...],
    equations: list[sp.Expr],
    line_numerators: dict[str, sp.Expr],
    open_factor: sp.Expr,
    algorithm: str,
    timeout: int,
) -> dict[str, object]:
    if algorithm not in {"std", "modStd"}:
        raise ValueError(f"unsupported standard-basis algorithm: {algorithm}")
    variable_source = ",".join(map(str, variables + (inverse,)))
    equation_source = ",".join(render_expression(item) for item in equations)
    runs: list[dict[str, object]] = []
    for name, line_numerator in line_numerators.items():
        localization = sp.expand(inverse * open_factor * line_numerator - 1)
        source_lines = []
        if algorithm == "modStd":
            source_lines.append('LIB "modstd.lib";')
        source_lines.extend(
            [
                f"ring r=0,({variable_source}),dp;",
                "option(redSB);",
                "ideal I="
                + equation_source
                + ","
                + render_expression(localization)
                + ";",
                f"ideal J={algorithm}(I);",
                "poly remainder=reduce(1,J);",
                'print("UNIT_REMAINDER");',
                "remainder;",
                'print("BASIS_SIZE");',
                "size(J);",
                "exit;",
            ]
        )
        source = "\n".join(source_lines)
        raw = run_singular_process(source, timeout)
        stdout = str(raw.pop("stdout"))
        stderr = str(raw.pop("stderr"))
        unit_remainder = marker(stdout, "UNIT_REMAINDER")
        basis_size = marker(stdout, "BASIS_SIZE")
        diagnostic_error = "error occurred" in stdout or "error occurred" in stderr
        if (
            raw["timed_out"]
            or raw["return_code"] != 0
            or diagnostic_error
            or unit_remainder != "0"
        ):
            raise AssertionError(
                f"{label} {name} failed: raw={raw}, remainder={unit_remainder}, "
                f"stderr={stderr[-500:]}"
            )
        runs.append(
            {
                "line": name,
                "algorithm": algorithm,
                "unit_remainder": unit_remainder,
                "basis_size": basis_size,
                "singular_source_sha256": hashlib.sha256(
                    source.encode("ascii")
                ).hexdigest(),
                **raw,
            }
        )
    return {
        "label": label,
        "variables": [str(item) for item in variables],
        "reduced_equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_numerator_sha256": {
            name: digest(expression) for name, expression in line_numerators.items()
        },
        "open_factor": str(sp.factor(open_factor)),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    arguments = parser.parse_args()

    started = time.perf_counter()
    equations, lines, build_seconds = eliminated_system(PARTITION)
    if len(equations) != 52:
        raise AssertionError(f"expected 52 equations, got {len(equations)}")

    # The first and last two equations give a four-cell radical cover.
    check(equations[51], 32 * g0 * (g0 + A) ** 2, "head cover E51")
    check(equations[50], 96 * g1 * (g0 + A) ** 2, "head cover E50")
    check(equations[0], 32 * g9 * (g9 + 1) ** 2, "tail cover E0")
    check(equations[1], 96 * g8 * (g9 + 1) ** 2, "tail cover E1")

    # H0 T0: both endpoint pairs are zero.  A constant-coefficient staircase
    # leaves direct line identities.
    h0t0: dict[sp.Symbol, sp.Expr | int] = {
        g0: 0,
        g1: 0,
        g9: 0,
        g8: 0,
    }
    check(equations[3].subs(h0t0), 192 * g6, "H0T0 E3")
    h0t0[g6] = 0
    check(equations[49].subs(h0t0), 192 * g2 * la**4 * mu**4, "H0T0 E49")
    h0t0[g2] = 0
    check(equations[6].subs(h0t0), 320 * g3, "H0T0 E6")
    h0t0[g3] = 0
    h0t0[g7] = solve_linear(equations[2].subs(h0t0), g7, "H0T0 E2")
    h0t0[g5] = solve_linear(equations[4].subs(h0t0), g5, "H0T0 E4")
    h0t0[g4] = solve_linear(equations[5].subs(h0t0), g4, "H0T0 E5")
    check(lines["line_x"].subs(h0t0), -equations[33].subs(h0t0), "H0T0 line_x")
    check(lines["line_y"].subs(h0t0), -equations[42].subs(h0t0), "H0T0 line_y")
    check(lines["line_z"].subs(h0t0), -equations[43].subs(h0t0), "H0T0 line_z")

    # H0 T1: the tail equation solves g7, while three high equations solve
    # g2, g3, and g4.  The remaining factor W is covered on both fibres.
    h0t1_base: dict[sp.Symbol, sp.Expr | int] = {g0: 0, g1: 0, g9: -1}
    h0t1_g7 = solve_linear(equations[3].subs(h0t1_base), g7, "H0T1 E3")
    h0t1_base[g7] = h0t1_g7
    h0t1_g2 = solve_linear(equations[49].subs(h0t1_base), g2, "H0T1 E49")
    check(h0t1_g2, 0, "H0T1 g2")
    h0t1_base[g2] = 0
    h0t1_g3 = solve_linear(equations[48].subs(h0t1_base), g3, "H0T1 E48")
    check(h0t1_g3, 0, "H0T1 g3")
    h0t1_base[g3] = 0
    h0t1_g4 = solve_linear(equations[41].subs(h0t1_base), g4, "H0T1 E41")
    check(h0t1_g4, -sp.Rational(3, 2) * (la * mu + la + mu) ** 2, "H0T1 g4")
    h0t1_base[g4] = h0t1_g4

    h0t1_w0: dict[sp.Symbol, sp.Expr | int] = {
        g0: 0,
        g1: 0,
        g9: -1,
        g8: 2 * T,
        g7: sp.cancel(h0t1_g7.subs(g8, 2 * T)),
        g2: 0,
        g3: 0,
        g4: h0t1_g4,
    }
    h0t1_w0[g5] = solve_linear(equations[6].subs(h0t1_w0), g5, "H0T1 W0 E6")
    p = (
        la**2 * mu**2
        - 2 * la**2 * mu
        + la**2
        - 2 * la * mu**2
        - 2 * la * mu
        + mu**2
    )
    check(equations[7].subs(h0t1_w0), 72 * p, "H0T1 W0 E7")
    h0t1_w0_quotients: dict[str, sp.Expr] = {}
    for name, line in lines.items():
        quotient = sp.cancel(line.subs(h0t1_w0) / p)
        if sp.denom(quotient).free_symbols:
            raise AssertionError(f"H0T1 W0 {name} is not a polynomial multiple of P")
        check(line.subs(h0t1_w0), p * quotient, f"H0T1 W0 {name}")
        h0t1_w0_quotients[name] = quotient

    h0t1_w1: dict[sp.Symbol, sp.Expr | int] = {
        g0: 0,
        g1: 0,
        g9: -1,
        g8: w + 2 * T,
        g7: sp.cancel(h0t1_g7.subs(g8, w + 2 * T)),
        g2: 0,
        g3: 0,
        g4: h0t1_g4,
    }
    h0t1_a5 = sp.cancel(equations[8].subs(h0t1_w1) / (9 * w))
    h0t1_a6 = sp.cancel(equations[7].subs(h0t1_w1) / 9)
    h0t1_w1[g5] = solve_linear(h0t1_a5, g5, "H0T1 W1 E8/W")
    h0t1_w1[g6] = solve_linear(h0t1_a6, g6, "H0T1 W1 E7")
    h0t1_w1_equations = reduced_numerators(
        equations, h0t1_w1, (w, la, mu)
    )
    h0t1_w1_lines = {
        name: primitive_numerator(line.subs(h0t1_w1), (w, la, mu))
        for name, line in lines.items()
    }
    h0t1_w1_units = unit_tests(
        label="H0T1 W!=0",
        variables=(w, la, mu),
        equations=h0t1_w1_equations,
        line_numerators=h0t1_w1_lines,
        open_factor=DELTA * w,
        algorithm="std",
        timeout=arguments.timeout,
    )

    # H1 T0: the reflected endpoint staircase again ends in direct line
    # identities.  Only lambda and mu, already in Delta, occur in denominators.
    h1t0: dict[sp.Symbol, sp.Expr | int] = {g0: -A, g9: 0, g8: 0}
    h1t0[g6] = solve_linear(equations[3].subs(h1t0), g6, "H1T0 E3")
    h1t0[g3] = solve_linear(equations[6].subs(h1t0), g3, "H1T0 E6")
    h1t0[g7] = solve_linear(equations[2].subs(h1t0), g7, "H1T0 E2")
    h1t0[g5] = solve_linear(equations[4].subs(h1t0), g5, "H1T0 E4")
    h1t0_g4 = solve_linear(equations[49].subs(h1t0), g4, "H1T0 E49")
    h1t0[g4] = h1t0_g4
    h1t0_g2 = solve_linear(equations[5].subs(h1t0), g2, "H1T0 E5")
    h1t0[g2] = h1t0_g2
    h1t0_g1 = solve_linear(equations[8].subs(h1t0), g1, "H1T0 E8")
    check(h1t0_g1, la * mu * T**2 / 2, "H1T0 g1")
    h1t0[g1] = h1t0_g1
    h1t0[g4] = sp.cancel(h1t0_g4.subs(g1, h1t0_g1))
    h1t0[g2] = sp.cancel(h1t0_g2.subs(g1, h1t0_g1))
    check(lines["line_x"].subs(h1t0), -equations[33].subs(h1t0), "H1T0 line_x")
    check(lines["line_y"].subs(h1t0), -equations[42].subs(h1t0), "H1T0 line_y")
    check(lines["line_z"].subs(h1t0), -equations[43].subs(h1t0), "H1T0 line_z")

    # H1 T1: use reversal-adapted deviation coordinates U and W.  E6 always
    # solves g5.  W=0 is closed directly; on W!=0, E7 solves g6 and the
    # residual head factor R is covered on both fibres.
    central_g7 = solve_linear(equations[3].subs({g0: -A, g9: -1}), g7, "H1T1 E3")
    central_g4 = solve_linear(
        equations[49].subs({g0: -A, g9: -1, g7: central_g7}),
        g4,
        "H1T1 E49",
    )
    central: dict[sp.Symbol, sp.Expr | int] = {
        g0: -A,
        g9: -1,
        g8: w + 2 * T,
        g7: sp.cancel(central_g7.subs(g8, w + 2 * T)),
        g1: la * mu * (u + T**2) / 2,
        g4: sp.cancel(central_g4.subs(g1, la * mu * (u + T**2) / 2)),
    }
    central_g5 = solve_linear(equations[6].subs(central), g5, "H1T1 E6")
    central[g5] = central_g5

    central_w0 = {
        key: sp.cancel(value.subs(w, 0)) if isinstance(value, sp.Expr) else value
        for key, value in central.items()
    }
    central_w0_equations = reduced_numerators(
        equations, central_w0, (g2, g3, g6, u, la, mu)
    )
    central_w0_lines = {
        name: primitive_numerator(
            line.subs(central_w0), (g2, g3, g6, u, la, mu)
        )
        for name, line in lines.items()
    }
    central_w0_units = unit_tests(
        label="H1T1 W=0",
        variables=(g2, g3, g6, u, la, mu),
        equations=central_w0_equations,
        line_numerators=central_w0_lines,
        open_factor=DELTA,
        algorithm="std",
        timeout=arguments.timeout,
    )

    central_w1 = dict(central)
    central_g6 = solve_linear(equations[7].subs(central_w1), g6, "H1T1 W1 E7")
    central_w1[g6] = central_g6
    central_w1[g5] = sp.cancel(central_g5.subs(g6, central_g6))

    r0_u = -la**2 + 2 * la * mu + 2 * la - mu**2 + 2 * mu - 1
    central_r0 = {
        key: sp.cancel(value.subs(u, r0_u)) if isinstance(value, sp.Expr) else value
        for key, value in central_w1.items()
    }
    central_r0[u] = r0_u
    central_r0[g3] = solve_linear(
        equations[10].subs(central_r0), g3, "H1T1 W1 R0 E10"
    )
    central_r0_equations = reduced_numerators(
        equations, central_r0, (g2, w, la, mu)
    )
    central_r0_lines = {
        name: primitive_numerator(line.subs(central_r0), (g2, w, la, mu))
        for name, line in lines.items()
    }
    central_r0_units = unit_tests(
        label="H1T1 W!=0 R=0",
        variables=(g2, w, la, mu),
        equations=central_r0_equations,
        line_numerators=central_r0_lines,
        open_factor=DELTA * w,
        algorithm="std",
        timeout=arguments.timeout,
    )

    central_r1 = dict(central_w1)
    central_g2 = solve_linear(equations[48].subs(central_r1), g2, "H1T1 W1 R1 E48")
    central_r1[g2] = central_g2
    central_g3 = solve_linear(equations[10].subs(central_r1), g3, "H1T1 W1 R1 E10")
    central_r1[g3] = central_g3
    selected_indices = [31, 39, 11, 12]
    central_r1_equations = reduced_numerators(
        [equations[index] for index in selected_indices],
        central_r1,
        (u, w, la, mu),
    )
    if len(central_r1_equations) != 4:
        raise AssertionError(
            f"expected four compact R!=0 equations, got {len(central_r1_equations)}"
        )
    central_r1_lines = {
        name: primitive_numerator(line.subs(central_r1), (u, w, la, mu))
        for name, line in lines.items()
    }
    central_r1_units = unit_tests(
        label="H1T1 W!=0 R!=0",
        variables=(u, w, la, mu),
        equations=central_r1_equations,
        line_numerators=central_r1_lines,
        open_factor=DELTA * w * R,
        algorithm="modStd",
        timeout=arguments.timeout,
    )

    result = {
        "schema": "hc4-five-support-nested-endpoint-cover-22222-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_ring": "Q[lambda,mu,g0,...,g9,1/Delta]",
        "radical_cover": {
            "head": [
                "E51=32*g0*(g0+lambda^2*mu^2)^2",
                "on g0=0, E50=96*g1*lambda^4*mu^4",
                "branches H0: g0=g1=0 and H1: g0=-lambda^2*mu^2",
            ],
            "tail": [
                "E0=32*g9*(g9+1)^2",
                "on g9=0, E1=96*g8",
                "branches T0: g9=g8=0 and T1: g9=-1",
            ],
        },
        "cells": {
            "H0T0": {
                "steps": [
                    "E3 solves g6; E49 solves g2; E6 solves g3",
                    "E2, E4, E5 solve g7, g5, g4 with constant leading coefficients",
                ],
                "line_relations": ["line_x=-E33", "line_y=-E42", "line_z=-E43"],
                "substitution_sha256": {
                    str(key): digest(sp.sympify(value)) for key, value in h0t0.items()
                },
            },
            "H0T1_W0": {
                "factor": str(p),
                "equation": "E7=72*P",
                "line_quotient_sha256": {
                    name: digest(value) for name, value in h0t1_w0_quotients.items()
                },
            },
            "H0T1_W1": h0t1_w1_units,
            "H1T0": {
                "steps": [
                    "E3, E6, E2, E4 solve g6, g3, g7, g5",
                    "E49 and E5 solve g4 and g2 over Delta",
                    "E8 solves g1 with constant leading coefficient",
                ],
                "line_relations": ["line_x=-E33", "line_y=-E42", "line_z=-E43"],
                "substitution_sha256": {
                    str(key): digest(sp.sympify(value)) for key, value in h1t0.items()
                },
            },
            "H1T1_W0": central_w0_units,
            "H1T1_W1_R0": central_r0_units,
            "H1T1_W1_R1": {
                "selected_original_equation_indices": selected_indices,
                "pivots": ["E3", "E49", "E6", "E7", "E48", "E10"],
                **central_r1_units,
            },
        },
        "boundary": (
            "W=0 and R=0 are proved cells of the nested cover; the only "
            "unproved divisor is Delta=0, exactly the normalized support-collision divisor"
        ),
        "discarded_route_observation": {
            "scope": "central H1T1 W!=0 unsplit line_x",
            "status": "TIMEOUT_ROUTE_EVIDENCE_ONLY",
            "timeout_seconds": 600,
            "observed_wall_seconds": 600.0553434169851,
            "observed_child_user_seconds": 591.159777,
            "observed_maximum_rss_native_bytes": 2018557952,
            "replacement": "split R=0/R!=0 and use the four-equation compact R!=0 certificate",
        },
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "wall_seconds": time.perf_counter() - started,
        "conclusion": (
            "the residual-line ideal is radical-zero on the normalized "
            "distinct-five-root locus for partition (2,2,2,2,2)"
        ),
        "claim_boundary": (
            "exact open-locus closure for this partition; Delta=0 invokes the "
            "separately pinned support-at-most-four theorem"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
