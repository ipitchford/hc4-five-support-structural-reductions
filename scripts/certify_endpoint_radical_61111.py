#!/usr/bin/env python3
"""Certify the endpoint radical chain for the (6,1,1,1,1) stratum.

This deliberately avoids a global Groebner-basis computation.  It reconstructs
the 52 eliminated normal equations, selects six sparse endpoint equations, and
checks a triangular sequence of exact identities.  The sequence proves that
the three residual-line coordinates vanish on every characteristic-zero
solution, including fibres on the root-collision divisor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from prove_polynomial_open_eliminated import eliminated_system, stream_digest
from scout_five_support import g_coefficients


PARTITION = (6, 1, 1, 1, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients


def expression_digest(expression: sp.Expr) -> str:
    rendered = str(sp.expand(expression)).encode("ascii")
    return hashlib.sha256(rendered).hexdigest()


def assert_identity(actual: sp.Expr, expected: sp.Expr, label: str) -> None:
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
        raise AssertionError(f"expected 52 eliminated equations, got {len(equations)}")

    stages: list[dict[str, object]] = []

    # Step 1: the last endpoint coefficient starts the radical chain.
    step1 = equations[51]
    assert_identity(step1, 32 * g0**3, "step 1")
    stages.append(
        {
            "step": 1,
            "equation_indices": [51],
            "prior_radical_variables": [],
            "identity": "E51 = 32*g0^3",
            "deduction": "g0 belongs to radical(I)",
            "identity_sha256": expression_digest(step1),
        }
    )

    # Step 2: pass to the quotient by the radical variable just obtained.
    step2 = equations[40].subs({g0: 0})
    assert_identity(step2, 12 * g1**3, "step 2")
    stages.append(
        {
            "step": 2,
            "equation_indices": [40],
            "prior_radical_variables": ["g0"],
            "identity": "E40 mod (g0) = 12*g1^3",
            "deduction": "g1 belongs to radical(I)",
            "identity_sha256": expression_digest(step2),
        }
    )

    # Step 3: two endpoint equations eliminate g2 without dividing by it.
    quotient01 = {g0: 0, g1: 0}
    e30 = equations[30].subs(quotient01)
    e24 = equations[24].subs(quotient01)
    assert_identity(e30, 288 * g2 * g4**2, "step 3, E30")
    assert_identity(e24, -48 * g4**2 * (g2 - g4), "step 3, E24")
    step3 = sp.expand(e30 / 288 + e24 / 48)
    assert_identity(step3, g4**3, "step 3 combination")
    stages.append(
        {
            "step": 3,
            "equation_indices": [30, 24],
            "prior_radical_variables": ["g0", "g1"],
            "identity": "E30/288 + E24/48 = g4^3",
            "deduction": "g4 belongs to radical(I)",
            "identity_sha256": expression_digest(step3),
        }
    )

    # Step 4: after g4 is radical-zero, a pure cube remains.
    step4 = equations[37].subs({g0: 0, g1: 0, g4: 0})
    assert_identity(step4, 16 * g2**3, "step 4")
    stages.append(
        {
            "step": 4,
            "equation_indices": [37],
            "prior_radical_variables": ["g0", "g1", "g4"],
            "identity": "E37 mod (g0,g1,g4) = 16*g2^3",
            "deduction": "g2 belongs to radical(I)",
            "identity_sha256": expression_digest(step4),
        }
    )

    # Step 5: a fixed-content Bezout combination yields a pure fourth power.
    quotient0124 = {g0: 0, g1: 0, g2: 0, g4: 0}
    e21 = equations[21].subs(quotient0124)
    e27 = equations[27].subs(quotient0124)
    assert_identity(e21, -16 * g5**2 * (g3 - 5 * g5), "step 5, E21")
    assert_identity(
        e27,
        12 * g5 * (g3**2 + 18 * g3 * g5 - 7 * g5**2),
        "step 5, E27",
    )
    step5 = sp.expand(e27 * g5 / 12 + e21 * (g3 + 23 * g5) / 16)
    assert_identity(step5, 108 * g5**4, "step 5 combination")
    stages.append(
        {
            "step": 5,
            "equation_indices": [21, 27],
            "prior_radical_variables": ["g0", "g1", "g4", "g2"],
            "identity": (
                "g5*E27/12 + (g3+23*g5)*E21/16 = 108*g5^4"
            ),
            "deduction": "g5 belongs to radical(I)",
            "identity_sha256": expression_digest(step5),
        }
    )

    # Step 6: every residual-line coordinate has now vanished in the radical.
    line_reductions = {
        name: sp.factor(expression.subs(quotient0124))
        for name, expression in lines.items()
    }
    expected_lines = {
        "line_x": 16 * g5**2 * (g7 - sp.Symbol("la") * sp.Symbol("mu")),
        "line_y": 16 * g5**3,
        "line_z": sp.Integer(0),
    }
    for name, expected in expected_lines.items():
        assert_identity(line_reductions[name], expected, f"line reduction {name}")
    stages.append(
        {
            "step": 6,
            "prior_radical_variables": ["g0", "g1", "g4", "g2", "g5"],
            "identity": {
                name: str(value) for name, value in line_reductions.items()
            },
            "deduction": "line_x, line_y, line_z belong to radical(I)",
            "identity_sha256": {
                name: expression_digest(value)
                for name, value in line_reductions.items()
            },
        }
    )

    result = {
        "schema": "hc4-five-support-endpoint-radical-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_field": "Q(lambda,mu)",
        "parameter_scope": (
            "identities lie in Q[lambda,mu,g0,...,g9] and therefore include "
            "all finite parameter fibres, including the collision divisor"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "stages": stages,
        "conclusion": (
            "the residual-line ideal (line_x,line_y,line_z) is contained in "
            "radical(I_nor) for partition (6,1,1,1,1)"
        ),
        "claim_boundary": (
            "this closes the clean normal-layer residual-line gate for this "
            "single partition; it does not decide the other six partitions "
            "or the full HC4 theorem"
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
