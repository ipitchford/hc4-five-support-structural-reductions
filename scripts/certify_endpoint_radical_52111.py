#!/usr/bin/env python3
"""Certify the endpoint radical chain for the (5,2,1,1,1) stratum."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from prove_generic_five_support import lambda_parameter, mu_parameter
from prove_polynomial_open_eliminated import eliminated_system, stream_digest
from scout_five_support import g_coefficients


PARTITION = (5, 2, 1, 1, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients


def digest(expression: sp.Expr) -> str:
    return hashlib.sha256(str(sp.expand(expression)).encode("ascii")).hexdigest()


def check(actual: sp.Expr, expected: sp.Expr, label: str) -> None:
    difference = sp.expand(actual - expected)
    if difference != 0:
        raise AssertionError(f"{label} failed: {sp.factor(difference)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    started = time.perf_counter()
    equations, lines, build_seconds = eliminated_system(PARTITION)
    if len(equations) != 52:
        raise AssertionError(f"expected 52 equations, got {len(equations)}")

    records: list[dict[str, object]] = []
    checks = (
        (51, {}, 32 * g0**3, "g0"),
        (40, {g0: 0}, 12 * g1**3, "g1"),
    )
    for number, substitutions, expected, radical_variable in checks:
        reduced = sp.expand(equations[number].subs(substitutions))
        check(reduced, expected, f"E{number}")
        records.append(
            {
                "equation_indices": [number],
                "reduced_identity": str(sp.factor(reduced)),
                "deduction": f"{radical_variable} belongs to radical(I)",
                "identity_sha256": digest(reduced),
            }
        )

    quotient01 = {g0: 0, g1: 0}
    e30 = sp.expand(equations[30].subs(quotient01))
    e24 = sp.expand(equations[24].subs(quotient01))
    check(e30, 288 * g2 * g4**2, "E30")
    check(e24, -48 * g4**2 * (g2 - g4), "E24")
    pure_g4 = sp.expand(e30 / 288 + e24 / 48)
    check(pure_g4, g4**3, "g4 combination")
    records.append(
        {
            "equation_indices": [30, 24],
            "reduced_identity": "E30/288 + E24/48 = g4^3",
            "deduction": "g4 belongs to radical(I)",
            "identity_sha256": digest(pure_g4),
        }
    )

    e37 = sp.expand(equations[37].subs({g0: 0, g1: 0, g4: 0}))
    check(e37, 16 * g2**3, "E37")
    records.append(
        {
            "equation_indices": [37],
            "reduced_identity": "E37 mod (g0,g1,g4) = 16*g2^3",
            "deduction": "g2 belongs to radical(I)",
            "identity_sha256": digest(e37),
        }
    )

    quotient0124 = {g0: 0, g1: 0, g2: 0, g4: 0}
    e21 = sp.expand(equations[21].subs(quotient0124))
    e27 = sp.expand(equations[27].subs(quotient0124))
    e34 = sp.expand(equations[34].subs(quotient0124))
    parameter_product = lambda_parameter * mu_parameter
    shifted_g5 = g5 - parameter_product
    shifted_g3 = g3 - parameter_product
    f = shifted_g5**2 * (shifted_g3 - 5 * shifted_g5)
    q = shifted_g5 * (
        shifted_g3**2
        + 18 * shifted_g3 * shifted_g5
        + 20 * parameter_product * shifted_g5
        - 7 * shifted_g5**2
    )
    r = (
        13 * shifted_g5**3
        - 40 * shifted_g5**2 * parameter_product
        - 31 * shifted_g5**2 * shifted_g3
        + 40 * shifted_g5 * parameter_product * shifted_g3
        + 31 * shifted_g5 * shifted_g3**2
        + 3 * shifted_g3**3
    )
    check(e21, -16 * f, "translated E21")
    check(e27, 12 * q, "translated E27")
    check(e34, 4 * r, "translated E34")

    bezout_left = sp.expand(
        -3
        * (16 * shifted_g3 - 36 * shifted_g5 + 20 * parameter_product)
        * e21
        + 4 * (-3 * shifted_g3 + 7 * shifted_g5) * e27
        + 12 * shifted_g5 * e34
    )
    check(bezout_left, 6912 * shifted_g5**4, "fixed-content Bezout identity")
    records.append(
        {
            "equation_indices": [21, 27, 34],
            "translation": {
                "H": "g5-la*mu",
                "U": "g3-la*mu",
            },
            "reduced_identity": (
                "-3*(16*U-36*H+20*la*mu)*E21 "
                "+4*(-3*U+7*H)*E27 +12*H*E34 = 6912*H^4"
            ),
            "deduction": "g5-la*mu belongs to radical(I)",
            "identity_sha256": digest(bezout_left),
        }
    )

    reduced_lines = {
        name: sp.factor(expression.subs(quotient0124))
        for name, expression in lines.items()
    }
    expected_lines = {
        "line_x": 16
        * shifted_g5**2
        * (g7 + parameter_product + lambda_parameter + mu_parameter),
        "line_y": 16 * shifted_g5**3,
        "line_z": sp.Integer(0),
    }
    for name, expected in expected_lines.items():
        check(reduced_lines[name], expected, f"line coordinate {name}")

    result = {
        "schema": "hc4-five-support-endpoint-radical-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_field": "Q(lambda,mu)",
        "parameter_scope": (
            "identities are polynomial in lambda and mu and include every finite fibre"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "radical_steps": records,
        "line_reductions": {
            name: str(value) for name, value in reduced_lines.items()
        },
        "conclusion": (
            "the residual-line ideal is contained in radical(I_nor) for "
            "partition (5,2,1,1,1)"
        ),
        "claim_boundary": (
            "exact closure of one clean normal-layer partition; the other five "
            "unclosed rows and the full HC4 theorem remain open"
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
