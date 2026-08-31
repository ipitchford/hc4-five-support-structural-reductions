#!/usr/bin/env python3
"""Certify the nested endpoint cover for the (4,2,2,1,1) stratum."""

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


PARTITION = (4, 2, 2, 1, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients
la, mu = lambda_parameter, mu_parameter
L = la * mu


def digest(expression: sp.Expr) -> str:
    return hashlib.sha256(str(sp.expand(expression)).encode("ascii")).hexdigest()


def check(actual: sp.Expr, expected: sp.Expr, label: str) -> None:
    difference = sp.cancel(actual - expected)
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

    check(equations[51], 32 * g0**3, "E51")
    check(equations[40].subs({g0: 0}), 12 * g1**3, "E40")
    common = {g0: 0, g1: 0}
    e30 = sp.expand(equations[30].subs(common))
    e24 = sp.expand(equations[24].subs(common))
    check(e30, 288 * g2 * (g4 + L) ** 2, "first cover E30")
    check(e24, -48 * (g2 - g4) * (g4 + L) ** 2, "first cover E24")

    # First-cover branch A: g4=-L.
    branch_a0 = {g0: 0, g1: 0, g4: -L}
    e37_a = sp.expand(equations[37].subs(branch_a0))
    check(e37_a, 16 * (g2 + L) ** 3, "branch A E37")
    branch_a = {**branch_a0, g2: -L}
    H = g5 - 2 * L - la - mu
    e44_a = sp.expand(equations[44].subs(branch_a))
    check(e44_a, -32 * L**2 * H, "branch A E44")
    lines_a = {name: sp.factor(value.subs(branch_a)) for name, value in lines.items()}
    check(lines_a["line_x"], 16 * H**2 * (g7 + L + 2 * la + 2 * mu + 1), "branch A line_x")
    check(lines_a["line_y"], 16 * H**3, "branch A line_y")
    check(lines_a["line_z"], 0, "branch A line_z")

    # First-cover branch B: g2=g4=0.  On L!=0, E29 and E23 give g3=g5=0.
    branch_b0 = {g0: 0, g1: 0, g2: 0, g4: 0}
    e29_b = sp.expand(equations[29].subs(branch_b0))
    e23_b = sp.expand(equations[23].subs(branch_b0))
    check(e29_b, 480 * L**2 * g3, "branch B E29")
    check(e23_b, -144 * L**2 * (g3 - g5), "branch B E23")
    branch_b = {**branch_b0, g3: 0, g5: 0}

    # The opposite endpoint yields a second cover.
    e0_b = sp.expand(equations[0].subs(branch_b))
    e1_b = sp.expand(equations[1].subs(branch_b))
    check(e0_b, 32 * g9 * (g9 + 1) ** 2, "tail cover E0")
    check(e1_b, 96 * g8 * (g9 + 1) ** 2, "tail cover E1")

    # Tail D: g9=g8=0.  It can occur only at lambda=mu=-1.
    tail_d0 = {**branch_b, g9: 0, g8: 0}
    e3_d = sp.expand(equations[3].subs(tail_d0))
    check(e3_d, 192 * g6, "tail D E3")
    tail_d1 = {**tail_d0, g6: 0}
    S = la + mu + 2
    e2_d = sp.expand(equations[2].subs(tail_d1))
    check(e2_d, 4 * (8 * g7 + 3 * S**2), "tail D E2")
    g7_d = -sp.Rational(3, 8) * S**2
    tail_d2 = {**tail_d1, g7: g7_d}
    e4_d = sp.expand(equations[4].subs(tail_d2))
    check(e4_d, -6 * S**3, "tail D E4")
    tail_d3 = {**tail_d1, g7: 0, mu: -la - 2}
    e21_d = sp.expand(equations[21].subs(tail_d3))
    check(e21_d, 512 * (la + 1) ** 6, "tail D collision E21")

    # Tail C: g9=-1.  E3 solves g7 exactly.
    tail_c0 = {**branch_b, g9: -1}
    g7_c = (
        g8**2
        - 2 * g8 * (la + mu + 2)
        + la**2
        - 2 * L
        - 4 * la
        + mu**2
        - 4 * mu
    ) / 4
    e3_c = sp.expand(equations[3].subs(tail_c0))
    check(e3_c.subs({g7: g7_c}), 0, "tail C E3 solution")
    tail_c = {**tail_c0, g7: g7_c}
    P = 2 * L + la + mu
    e25_c = sp.factor(equations[25].subs(tail_c))
    check(e25_c, 32 * g6**2 * P, "tail C cover E25")

    # Tail C2: g6=0.  The line coordinates are normal equations.
    tail_c2 = {**tail_c, g6: 0}
    check(lines["line_x"].subs(tail_c2), -equations[20].subs(tail_c2) / 6, "tail C2 line_x")
    check(lines["line_y"].subs(tail_c2), -equations[27].subs(tail_c2) / 6, "tail C2 line_y")
    check(lines["line_z"].subs(tail_c2), -equations[43].subs(tail_c2), "tail C2 line_z")

    # Tail C1: P=0.  Parametrize mu=-la/(2*la+1), whose denominator cannot
    # vanish on P=0.  The remaining equations give an explicit contradiction.
    D = 2 * la + 1
    mu_on_p = -la / D
    tail_c1 = {**tail_c, mu: mu_on_p}
    e21_c1 = sp.cancel(equations[21].subs(tail_c1))
    check(e21_c1, 576 * g8 * la**4 / D**2, "tail C1 E21")
    tail_c1_g8 = {**tail_c1, g8: 0}
    K = la**2 - 2 * la - 1
    e22_c1 = sp.cancel(equations[22].subs(tail_c1_g8))
    e43_c1 = sp.cancel(equations[43].subs(tail_c1_g8))
    check(
        e22_c1,
        96 * la**4 * (g6 * D**2 + 2 * la**2 * K) / D**4,
        "tail C1 E22",
    )
    check(
        e43_c1,
        48 * la**4 * (g6 * D**2 - la**2 * K) / D**4,
        "tail C1 E43",
    )
    tail_c1_zero = {**tail_c1_g8, g6: 0}
    e8_c1 = sp.cancel(equations[8].subs(tail_c1_zero))
    check(e8_c1, -288 * la**2 * (la + 1) ** 2 / D**2, "tail C1 E8")
    check(K - (la + 1) * (la - 3), 2, "tail C1 parameter Bezout identity")

    result = {
        "schema": "hc4-five-support-nested-endpoint-cover-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_ring": "Q[lambda,mu,g0,...,g9,1/(lambda*mu)]",
        "first_cover": {
            "equations": [
                "E30=288*g2*(g4+lambda*mu)^2",
                "E24=-48*(g2-g4)*(g4+lambda*mu)^2",
            ],
            "branches": ["A: g4=-lambda*mu", "B: g2=g4=0"],
        },
        "branch_a": {
            "steps": [
                "E37=16*(g2+lambda*mu)^3",
                "E44=-32*(lambda*mu)^2*(g5-2*lambda*mu-lambda-mu)",
            ],
            "line_reductions": {name: str(value) for name, value in lines_a.items()},
            "conclusion": "line vanishes",
        },
        "branch_b_tail_cover": {
            "equations": [
                "E0=32*g9*(g9+1)^2",
                "E1=96*g8*(g9+1)^2",
            ],
            "branches": ["C: g9=-1", "D: g9=g8=0"],
        },
        "tail_d": {
            "steps": [
                "E3=192*g6",
                "E2=4*(8*g7+3*(lambda+mu+2)^2)",
                "E4=-6*(lambda+mu+2)^3",
                "E21 at mu=-lambda-2 is 512*(lambda+1)^6",
            ],
            "conclusion": "only lambda=mu=-1, a support collision",
        },
        "tail_c": {
            "g7_solution": str(g7_c),
            "cover_equation": "E25=32*g6^2*(2*lambda*mu+lambda+mu)",
            "g6_zero_branch": [
                "line_x=-E20/6",
                "line_y=-E27/6",
                "line_z=-E43",
            ],
            "parameter_branch": {
                "divisor": "P=2*lambda*mu+lambda+mu=0",
                "parametrization": "mu=-lambda/(2*lambda+1)",
                "steps": [
                    "E21=576*g8*lambda^4/(2*lambda+1)^2",
                    "E22 and E43 imply K=lambda^2-2*lambda-1=0 and g6=0",
                    "E8=-288*lambda^2*(lambda+1)^2/(2*lambda+1)^2",
                    "2=K-(lambda+1)*(lambda-3)",
                ],
                "conclusion": "empty on the lambda*mu-nonzero locus",
            },
        },
        "boundary": (
            "the only globally inverted factor is lambda*mu; its zero locus "
            "is a collision with the normalized root 0"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "selected_identity_sha256": {
            "first_cover_E30": digest(e30),
            "first_cover_E24": digest(e24),
            "branch_A_E44": digest(e44_a),
            "tail_D_E21": digest(e21_d),
            "tail_C_E25": digest(e25_c),
            "tail_C1_E8_numerator": digest(sp.numer(e8_c1)),
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "conclusion": (
            "the residual-line ideal is radical-zero on the lambda*mu-nonzero "
            "locus; all exceptional branches are either empty or root collisions"
        ),
        "claim_boundary": (
            "exact open-locus closure for this partition; the lambda*mu=0 "
            "boundary invokes the separately pinned support-at-most-four theorem"
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
