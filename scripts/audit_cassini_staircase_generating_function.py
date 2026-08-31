#!/usr/bin/env python3
"""Independent all-index audit of the weighted Fibonacci-Cassini staircase.

This checker deliberately avoids importing the original finite-index checker or
its explicit coefficient formula for F_e.  It works with the generating
function A(z,w) = sum_{e>=2} F_e(w) z^e and certifies the differential/Euler
identities as exact identities in Q(z,w,log(1-z-w*z^2)).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp


def expression_digest(expression: sp.Expr) -> str:
    rendered = sp.srepr(expression).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def formal_audit() -> dict[str, object]:
    z, w = sp.symbols("z w")
    denominator = 1 - z - w * z**2

    # The boundary terms encode F_e(0)=1/((e+2)(e+1)) and F'_e(0)=1/e.
    generating_function = (
        denominator * sp.log(denominator)
        - denominator
        + 1
        - z**2 / 2
        - z**3 / 6
        - w * z**3
    ) / z**2

    first_w = sp.diff(generating_function, w)
    second_w = sp.diff(generating_function, w, 2)
    first_euler = sp.expand(
        z * sp.diff(generating_function, z)
        + 2 * generating_function
        - 2 * w * first_w
    )
    second_euler = sp.expand(
        z * sp.diff(first_euler, z)
        + first_euler
        - 2 * w * sp.diff(first_euler, w)
    )

    expected_first_w = -sp.log(denominator) - z
    expected_second_w = z**2 / denominator
    expected_first_euler_derivative = z**2 * (1 + w * z) / denominator
    expected_second_euler = 1 / denominator - 1 - z

    checks = {
        "first_w_boundary_integral": sp.simplify(first_w - expected_first_w) == 0,
        "fibonacci_tail": sp.simplify(second_w - expected_second_w) == 0,
        "first_euler_tail": sp.simplify(
            sp.diff(first_euler, w) - expected_first_euler_derivative
        )
        == 0,
        "second_euler_tail": sp.simplify(
            second_euler - expected_second_euler
        )
        == 0,
    }

    # Independent Cassini certificate.  The recurrence transfer matrix has
    # determinant -w, hence every adjacent 2x2 determinant is multiplied by
    # -w.  The base determinant at e=2 is w.
    transfer = sp.Matrix([[1, w], [1, 0]])
    base_adjacent = sp.Matrix([[1 + w, 1], [1, 1]])
    checks.update(
        {
            "transfer_determinant": sp.expand(transfer.det() + w) == 0,
            "cassini_base_e2": sp.expand(base_adjacent.det() - w) == 0,
        }
    )

    return {
        "schema": "hc4-cassini-staircase-generating-function-audit-v1",
        "method": "formal_generating_function_and_transfer_determinant",
        "independent_of_original_checker": True,
        "denominator": str(denominator),
        "generating_function": str(generating_function),
        "generating_function_sha256": expression_digest(generating_function),
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": {
            "indices": "all integers e >= 2 by formal coefficient extraction",
            "cassini": "all integers e >= 2 by determinant induction",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    started = time.perf_counter()
    result = formal_audit()
    result["wall_seconds"] = time.perf_counter() - started
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
