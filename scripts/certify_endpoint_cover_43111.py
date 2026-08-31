#!/usr/bin/env python3
"""Certify a two-branch endpoint cover for the (4,3,1,1,1) stratum."""

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


PARTITION = (4, 3, 1, 1, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients
L = lambda_parameter * mu_parameter
R = lambda_parameter + mu_parameter + 1
T = L + lambda_parameter + mu_parameter


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

    # Common endpoint reductions.
    check(equations[51], 32 * g0**3, "E51")
    check(equations[40].subs({g0: 0}), 12 * g1**3, "E40 mod g0")
    common = {g0: 0, g1: 0}
    e30 = sp.expand(equations[30].subs(common))
    e24 = sp.expand(equations[24].subs(common))
    check(e30, 288 * g2 * (g4 - L) ** 2, "cover E30")
    check(e24, -48 * (g2 - g4) * (g4 - L) ** 2, "cover E24")

    # Branch A: g4=L.  E37 forces g2=L; E44 then forces the common
    # line-coordinate factor H=g5+L+lambda+mu when L is invertible.
    branch_a0 = {g0: 0, g1: 0, g4: L}
    e37_a = sp.expand(equations[37].subs(branch_a0))
    check(e37_a, 16 * (g2 - L) ** 3, "branch A E37")
    branch_a = {**branch_a0, g2: L}
    H = g5 + T
    e44_a = sp.expand(equations[44].subs(branch_a))
    check(e44_a, -32 * L**2 * H, "branch A E44")
    lines_a = {name: sp.factor(value.subs(branch_a)) for name, value in lines.items()}
    check(lines_a["line_x"], 16 * H**2 * (g7 - R), "branch A line_x")
    check(lines_a["line_y"], 16 * H**3, "branch A line_y")
    check(lines_a["line_z"], 0, "branch A line_z")

    # Branch B: g2=g4=0.  All deductions below take place in Q[...][1/L].
    branch_b0 = {g0: 0, g1: 0, g2: 0, g4: 0}
    e29_b = sp.expand(equations[29].subs(branch_b0))
    e23_b = sp.expand(equations[23].subs(branch_b0))
    check(e29_b, 480 * g3 * L**2, "branch B E29")
    check(e23_b, -144 * L**2 * (g3 - g5), "branch B E23")

    branch_b1 = {**branch_b0, g3: 0, g5: 0}
    check(equations[0].subs(branch_b1), 32 * g9**3, "branch B E0")
    branch_b2 = {**branch_b1, g9: 0}
    e4_b = sp.expand(equations[4].subs(branch_b2))
    check(e4_b, 12 * (g8 + 1) ** 3, "branch B E4")
    branch_b3 = {**branch_b2, g8: -1}
    e10_b = sp.expand(equations[10].subs(branch_b3))
    check(e10_b, -48 * (g7 - R), "branch B E10")

    lines_b = {name: sp.expand(value.subs(branch_b3)) for name, value in lines.items()}
    e27_b = sp.expand(equations[27].subs(branch_b3))
    e43_b = sp.expand(equations[43].subs(branch_b3))
    check(lines_b["line_y"], -e27_b / 6, "branch B line_y relation")
    check(lines_b["line_z"], -e43_b, "branch B line_z relation")
    check(lines_b["line_x"].subs({g7: R}), 0, "branch B line_x factor")
    line_x_quotient = sp.cancel(lines_b["line_x"] / (g7 - R))
    if sp.denom(line_x_quotient) != 1:
        raise AssertionError("branch B line_x quotient is not polynomial")

    result = {
        "schema": "hc4-five-support-endpoint-cover-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_ring": "Q[lambda,mu,g0,...,g9,1/(lambda*mu)]",
        "common_radical_steps": [
            "E51=32*g0^3",
            "E40 mod (g0)=12*g1^3",
        ],
        "cover": {
            "equations": [
                "E30=288*g2*(g4-lambda*mu)^2",
                "E24=-48*(g2-g4)*(g4-lambda*mu)^2",
            ],
            "branches": [
                "A: g4=lambda*mu",
                "B: g2=g4=0",
            ],
            "justification": (
                "if g4-lambda*mu is nonzero, E30 and E24 force "
                "g2=0 and g4=0"
            ),
        },
        "branch_a": {
            "steps": [
                "E37=16*(g2-lambda*mu)^3",
                "E44=-32*(lambda*mu)^2*(g5+lambda*mu+lambda+mu)",
            ],
            "line_reductions": {name: str(value) for name, value in lines_a.items()},
            "conclusion": "all three line coordinates vanish",
        },
        "branch_b": {
            "steps": [
                "E29=480*g3*(lambda*mu)^2",
                "E23=-144*(lambda*mu)^2*(g3-g5)",
                "E0=32*g9^3",
                "E4=12*(g8+1)^3",
                "E10=-48*(g7-lambda-mu-1)",
            ],
            "line_relations": [
                "line_x is divisible by g7-lambda-mu-1",
                "line_y=-E27/6",
                "line_z=-E43",
            ],
            "line_x_quotient_sha256": digest(line_x_quotient),
            "conclusion": "all three line coordinates vanish",
        },
        "boundary": (
            "the only inverted factor is lambda*mu; its zero locus is a "
            "collision with the normalized root 0 and hence has support at most four"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "identity_sha256": {
            "cover_E30": digest(e30),
            "cover_E24": digest(e24),
            "branch_A_E37": digest(e37_a),
            "branch_A_E44": digest(e44_a),
            "branch_B_E29": digest(e29_b),
            "branch_B_E23": digest(e23_b),
            "branch_B_E4": digest(e4_b),
            "branch_B_E10": digest(e10_b),
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "conclusion": (
            "the residual-line ideal is contained in the radical of the "
            "normal ideal on the lambda*mu-nonzero locus"
        ),
        "claim_boundary": (
            "exact open-locus closure for one partition plus an identified "
            "support-collision boundary; use of the support-at-most-four theorem "
            "must be recorded separately"
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
