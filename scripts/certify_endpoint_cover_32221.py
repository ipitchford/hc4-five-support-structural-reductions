#!/usr/bin/env python3
"""Certify the endpoint branch cover for the (3,2,2,2,1) stratum."""

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


PARTITION = (3, 2, 2, 2, 1)
g0, g1, g2, g3, g4, g5, g6, g7, g8, g9 = g_coefficients
la, mu = lambda_parameter, mu_parameter
HEAD_G1 = la**2 * mu
HEAD_G4 = -2 * la**2 * mu - la**2 - 2 * la * mu
S = 2 * la + mu + 2
W = g8 - S


def digest(expression: sp.Expr) -> str:
    return hashlib.sha256(str(sp.expand(expression)).encode("ascii")).hexdigest()


def check(actual: sp.Expr, expected: sp.Expr, label: str) -> None:
    difference = sp.cancel(actual - expected)
    if difference != 0:
        raise AssertionError(f"{label} failed: {sp.factor(difference)}")


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    arguments = parser.parse_args()

    started = time.perf_counter()
    equations, lines, build_seconds = eliminated_system(PARTITION)
    if len(equations) != 52:
        raise AssertionError(f"expected 52 equations, got {len(equations)}")

    # Head staircase; only E47 uses lambda*mu != 0.
    check(equations[51], 32 * g0**3, "E51")
    check(
        equations[40].subs({g0: 0}),
        12 * (g1 - HEAD_G1) ** 3,
        "E40",
    )
    head_g1 = {g0: 0, g1: HEAD_G1}
    check(
        equations[47].subs(head_g1),
        -48 * la**4 * mu**2 * (g4 - HEAD_G4),
        "E47",
    )
    head = {**head_g1, g4: HEAD_G4}
    check(lines["line_z"].subs(head), 0, "head line_z")
    check(equations[0].subs(head), 32 * g9 * (g9 + 1) ** 2, "tail cover E0")
    check(equations[1].subs(head), 96 * g8 * (g9 + 1) ** 2, "tail cover E1")

    # Tail A: g9=0 forces g8=0, followed by a constant-coefficient staircase.
    tail_a0 = {**head, g9: 0, g8: 0}
    check(equations[3].subs(tail_a0), 192 * g6, "tail A E3")
    tail_a1 = {**tail_a0, g6: 0}
    check(equations[6].subs(tail_a1), 320 * g3, "tail A E6")
    tail_a2 = {**tail_a1, g3: 0}
    tail_a_g7 = -sp.Rational(3, 8) * S**2
    check(
        equations[2].subs(tail_a2),
        4 * (8 * g7 + 3 * S**2),
        "tail A E2",
    )
    tail_a3 = {**tail_a2, g7: tail_a_g7}
    tail_a_g5 = sp.Rational(1, 16) * S**3
    check(
        equations[4].subs(tail_a3),
        6 * (16 * g5 - S**3),
        "tail A E4",
    )
    tail_a4 = {**tail_a3, g5: tail_a_g5}
    tail_a_g2_solutions = sp.solve(equations[5].subs(tail_a4), g2)
    if len(tail_a_g2_solutions) != 1:
        raise AssertionError("tail A E5 did not solve g2 uniquely")
    tail_a = {**tail_a4, g2: tail_a_g2_solutions[0]}
    check(lines["line_x"].subs(tail_a), -equations[33].subs(tail_a), "tail A line_x")
    check(lines["line_y"].subs(tail_a), -equations[42].subs(tail_a), "tail A line_y")
    check(lines["line_z"].subs(tail_a), 0, "tail A line_z")

    # Tail B: g9=-1.  E3 solves g7 without parameter division.
    tail_b_g7 = (
        g8**2
        - 4 * g8 * la
        - 2 * g8 * mu
        - 4 * g8
        - 4 * la * mu
        - 8 * la
        + mu**2
        - 4 * mu
    ) / 4
    tail_b0 = {**head, g9: -1}
    check(equations[3].subs({**tail_b0, g7: tail_b_g7}), 0, "tail B E3 solution")
    tail_b = {**tail_b0, g7: tail_b_g7}

    # Tail B1: W=0.  One linear equation kills the sole line factor.
    tail_b1_g7 = sp.factor(tail_b_g7.subs({g8: S}))
    tail_b1 = {**head, g9: -1, g8: S, g7: tail_b1_g7}
    H = g5 - la**2 * mu - 2 * la**2 - 4 * la * mu - 2 * la - mu
    check(equations[6].subs(tail_b1), -48 * H, "tail B1 E6")
    check(lines["line_x"].subs(tail_b1), 0, "tail B1 line_x")
    check(lines["line_y"].subs(tail_b1), 16 * H**3, "tail B1 line_y")
    check(lines["line_z"].subs(tail_b1), 0, "tail B1 line_z")

    # Tail B2: W!=0.  E7 and E8 solve g6 and g5.
    a6 = (
        4 * g6
        + 3 * g8**2
        - 4 * g8 * la
        - 2 * g8 * mu
        - 4 * g8
        + 4 * la * mu
        + 8 * la
        - mu**2
        + 4 * mu
    )
    a5 = (
        4 * g5
        + g8**3
        - 4 * g8**2 * la
        - 2 * g8**2 * mu
        - 4 * g8**2
        + 4 * g8 * la**2
        + 4 * g8 * la * mu
        + 8 * g8 * la
        + g8 * mu**2
        + 4 * g8 * mu
        + 4 * g8
        - 4 * la**2 * mu
        - 8 * la**2
        - 16 * la * mu
        - 8 * la
        - 4 * mu
    )
    check(equations[7].subs(tail_b), 9 * W**2 * a6, "tail B2 E7")
    check(equations[8].subs(tail_b), 9 * W**2 * a5, "tail B2 E8")
    tail_b_g6 = sp.solve(a6, g6)[0]
    tail_b_g5 = sp.solve(a5, g5)[0]
    tail_b2 = {**tail_b, g6: tail_b_g6, g5: tail_b_g5}

    # E10 and E13 are a two-by-two linear system in g2,g3.  Its determinant
    # is 864*W, exactly the factor inverted by this branch.
    n10 = sp.cancel(-equations[10].subs(tail_b2) / 2)
    e13 = sp.expand(equations[13].subs(tail_b2))
    n13 = sp.cancel(4 * e13 / W**3)
    check(e13, W**3 * n13 / 4, "tail B2 E13 factor")
    matrix, _ = sp.linear_eq_to_matrix([n10, n13], [g2, g3])
    check(matrix.det(), 864 * W, "tail B2 linear determinant")
    tail_b23_solutions = sp.solve([n10, n13], [g2, g3], dict=True)
    if len(tail_b23_solutions) != 1:
        raise AssertionError("tail B2 E10/E13 did not solve g2,g3 uniquely")
    tail_b2_final = {**tail_b2, **tail_b23_solutions[0]}
    check(
        lines["line_x"].subs(tail_b2_final),
        -W**3 * equations[11].subs(tail_b2_final) / 16,
        "tail B2 line_x",
    )
    check(lines["line_z"].subs(tail_b2_final), 0, "tail B2 line_z")

    # The remaining line_y implication is a three-variable exact calculation.
    # All substitutions above have only constant denominators.
    reduced_equations: list[sp.Expr] = []
    for equation in equations:
        reduced = sp.together(sp.cancel(equation.subs(tail_b2_final)))
        numerator, denominator = reduced.as_numer_denom()
        if denominator.free_symbols:
            raise AssertionError(f"unexpected parameter denominator: {denominator}")
        if numerator != 0:
            reduced_equations.append(sp.expand(numerator))
    reduced_line_y = sp.together(lines["line_y"].subs(tail_b2_final))
    line_y_numerator, line_y_denominator = reduced_line_y.as_numer_denom()
    if line_y_denominator.free_symbols:
        raise AssertionError("unexpected parameter denominator in line_y")

    delta = la * mu * (la - 1) * (mu - 1) * (la - mu)
    inverse = sp.Symbol("inv")
    localization = sp.expand(inverse * delta * W * line_y_numerator - 1)
    expression_source = ",".join(
        render_expression(expression)
        for expression in reduced_equations + [localization]
    )
    singular_source = "\n".join(
        [
            'ring r=0,(g8,la,mu,inv),dp;',
            "option(redSB);",
            "ideal I=" + expression_source + ";",
            "ideal J=std(I);",
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )
    raw = run_singular_process(singular_source, arguments.timeout)
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
            "tail B2 line_y unit calculation failed: "
            f"raw={raw}, remainder={unit_remainder}, stderr={stderr[-500:]}"
        )

    result = {
        "schema": "hc4-five-support-nested-endpoint-cover-certificate-v1",
        "status": "PASS",
        "partition": list(PARTITION),
        "coefficient_ring": "Q[lambda,mu,g0,...,g9,1/Delta]",
        "head_steps": [
            "E51=32*g0^3",
            "E40 mod g0=12*(g1-lambda^2*mu)^3",
            "E47 mod preceding=-48*lambda^4*mu^2*(g4+2*lambda^2*mu+lambda^2+2*lambda*mu)",
            "line_z=0 after the head substitutions",
        ],
        "tail_cover": {
            "equations": [
                "E0=32*g9*(g9+1)^2",
                "E1=96*g8*(g9+1)^2",
            ],
            "branches": ["A: g9=g8=0", "B: g9=-1"],
        },
        "tail_a": {
            "steps": [
                "E3=192*g6",
                "E6=320*g3",
                "E2=4*(8*g7+3*(2*lambda+mu+2)^2)",
                "E4=6*(16*g5-(2*lambda+mu+2)^3)",
                "E5 solves g2 with constant leading coefficient",
            ],
            "line_relations": ["line_x=-E33", "line_y=-E42", "line_z=0"],
        },
        "tail_b1": {
            "branch": "W=g8-2*lambda-mu-2=0",
            "steps": ["E6=-48*H", "line_y=16*H^3"],
            "line_relations": ["line_x=0", "line_y=16*H^3", "line_z=0"],
        },
        "tail_b2": {
            "branch": "W!=0",
            "steps": [
                "E7=9*W^2*A6 solves g6",
                "E8=9*W^2*A5 solves g5",
                "normalized E10,E13 solve g2,g3 with determinant 864*W",
                "line_x=-W^3*E11/16",
                "line_z=0",
            ],
            "line_y_unit_calculation": {
                "ring": "Q[g8,lambda,mu,inv]",
                "localization": "inv*Delta*W*line_y-1",
                "reduced_equation_count": len(reduced_equations),
                "standard_basis_algorithm": "Singular std over characteristic zero",
                "unit_remainder": unit_remainder,
                "basis_size": basis_size,
                "singular_source_sha256": hashlib.sha256(
                    singular_source.encode("ascii")
                ).hexdigest(),
                **raw,
            },
        },
        "boundary": (
            "Delta=0 is exactly the normalized support-collision divisor; W=0 "
            "is handled by tail B1 rather than discarded"
        ),
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": {
            name: stream_digest([expression]) for name, expression in lines.items()
        },
        "selected_identity_sha256": {
            "tail_A_line_x": digest(lines["line_x"].subs(tail_a)),
            "tail_A_line_y": digest(lines["line_y"].subs(tail_a)),
            "tail_B1_line_y": digest(lines["line_y"].subs(tail_b1)),
            "tail_B2_line_x": digest(lines["line_x"].subs(tail_b2_final)),
            "tail_B2_line_y_numerator": digest(line_y_numerator),
        },
        "build_seconds": build_seconds,
        "certificate_seconds": time.perf_counter() - started - build_seconds,
        "conclusion": (
            "the residual-line ideal is radical-zero on the normalized "
            "distinct-five-root locus for partition (3,2,2,2,1)"
        ),
        "claim_boundary": (
            "exact open-locus closure for this partition; Delta=0 invokes the "
            "separately pinned support-at-most-four theorem"
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
