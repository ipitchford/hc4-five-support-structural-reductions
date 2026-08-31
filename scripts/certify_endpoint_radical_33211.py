#!/usr/bin/env python3
"""Certify the endpoint radical reduction for the (3,3,2,1,1) stratum."""

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


PARTITION = (3, 3, 2, 1, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients
la, mu = lambda_parameter, mu_parameter
L = la * mu
Q = 2 * L + la + mu
R = la + mu + 2
H = g5 + L + 2 * la + 2 * mu + 1
D = g6 - R


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

    # Endpoint staircase.  Only the E47 step uses lambda*mu != 0.
    check(equations[51], 32 * g0**3, "E51")
    check(equations[40].subs({g0: 0}), 12 * (g1 + L) ** 3, "E40")
    step_g1 = {g0: 0, g1: -L}
    check(equations[47].subs(step_g1), -48 * L**2 * (g4 - Q), "E47")
    step_g4 = {**step_g1, g4: Q}
    check(equations[0].subs(step_g4), 32 * g9**3, "E0")
    step_g9 = {**step_g4, g9: 0}
    check(equations[4].subs(step_g9), 12 * (g8 + 1) ** 3, "E4")
    step_g8 = {**step_g9, g8: -1}
    check(equations[10].subs(step_g8), -48 * (g7 - R), "E10")
    endpoint = {**step_g8, g7: R}

    # At the endpoint, two normal equations give a fixed-content radical
    # certificate for the sole remaining line factor H.
    e14 = sp.expand(equations[14].subs(endpoint))
    e17 = sp.expand(equations[17].subs(endpoint))
    check(e14, 16 * (D**2 - 3 * H), "E14 endpoint")
    check(e17, 32 * D * H**2, "E17 endpoint")
    radical_identity = sp.expand(-H**4 * e14 / 16 + e17**2 / 1024)
    check(radical_identity, 3 * H**5, "radical identity")

    endpoint_lines = {
        name: sp.factor(value.subs(endpoint)) for name, value in lines.items()
    }
    check(endpoint_lines["line_x"], 0, "endpoint line_x")
    check(endpoint_lines["line_y"], 16 * H**3, "endpoint line_y")
    check(endpoint_lines["line_z"], 0, "endpoint line_z")

    result = {
        "schema": "hc4-five-support-endpoint-radical-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_ring": "Q[lambda,mu,g0,...,g9,1/(lambda*mu)]",
        "endpoint_steps": [
            "E51=32*g0^3",
            "E40 mod (g0)=12*(g1+lambda*mu)^3",
            "E47 mod preceding=-48*(lambda*mu)^2*(g4-2*lambda*mu-lambda-mu)",
            "E0 mod preceding=32*g9^3",
            "E4 mod preceding=12*(g8+1)^3",
            "E10 mod preceding=-48*(g7-lambda-mu-2)",
        ],
        "radical_step": {
            "H": str(H),
            "D": str(D),
            "equations": [
                "E14=16*(D^2-3*H)",
                "E17=32*D*H^2",
            ],
            "identity": "3*H^5=-H^4*E14/16+E17^2/1024",
            "conclusion": "H belongs to the radical of the endpoint normal ideal",
        },
        "line_reductions": {
            name: str(value) for name, value in endpoint_lines.items()
        },
        "boundary": (
            "the only inverted factor is lambda*mu; its zero locus is a "
            "collision with the normalized root 0"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "selected_identity_sha256": {
            "endpoint_E14": digest(e14),
            "endpoint_E17": digest(e17),
            "radical_identity": digest(radical_identity),
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "conclusion": (
            "the residual-line ideal is contained in the radical of the normal "
            "ideal on the lambda*mu-nonzero locus"
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
