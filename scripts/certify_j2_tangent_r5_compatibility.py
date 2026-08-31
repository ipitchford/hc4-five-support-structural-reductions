#!/usr/bin/env python3
"""Exact rank-stratified certificate for the tangent top-index-five slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_r5_rational_slice import SELECTED_INDICES, rational_slice
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import primitive_j2, singular_source


LINEAR_INDICES = (33, 37, 38)
PURE_G_INDICES = (35, 36, 45, 46, 47, 48, 49, 50, 51, 52)
DETERMINANT_SCALAR = -55296


def exact_systems() -> dict[str, object]:
    equations, variables, substitutions = rational_slice()
    indexed = dict(zip(SELECTED_INDICES, equations, strict=True))
    f2, f3 = variables[2], variables[3]
    g_variables = variables[4:]
    g0 = g_variables[0]
    symbolic_substitutions = {
        sp.Symbol(name): sp.Integer(value) for name, value in substitutions.items()
    }
    if sp.expand(primitive_j2().subs(symbolic_substitutions)) != -5:
        raise AssertionError("the rational r=5 slice must have primitive_j2=-5")

    rows: list[tuple[sp.Expr, sp.Expr, sp.Expr]] = []
    for index in LINEAR_INDICES:
        equation = indexed[index]
        coefficient_f2 = sp.diff(equation, f2)
        coefficient_f3 = sp.diff(equation, f3)
        constant = sp.expand(
            equation - coefficient_f2 * f2 - coefficient_f3 * f3
        )
        if (coefficient_f2.free_symbols | coefficient_f3.free_symbols | constant.free_symbols) & set(variables[:4]):
            raise AssertionError(f"equation {index} is not affine-linear over Q[g]")
        rows.append((coefficient_f2, coefficient_f3, constant))

    augmented = sp.Matrix(rows)
    determinant = sp.expand(augmented.det())
    cofactors = [sp.expand(augmented.cofactor(row, 2)) for row in range(3)]
    cofactor_identity = sp.expand(
        sum(cofactor * indexed[index] for cofactor, index in zip(cofactors, LINEAR_INDICES, strict=True))
        - determinant
    )
    if cofactor_identity != 0:
        raise AssertionError("the determinant cofactor identity failed")
    quotient = sp.cancel(determinant / (DETERMINANT_SCALAR * g0**2))
    if sp.denom(quotient) != 1:
        raise AssertionError("the compatibility quotient is not a polynomial")
    Q = sp.expand(quotient)
    if sp.expand(determinant - DETERMINANT_SCALAR * g0**2 * Q) != 0:
        raise AssertionError("the determinant factorization failed")

    pure_g = [indexed[index] for index in PURE_G_INDICES]
    if any(expression.free_symbols - set(g_variables) for expression in pure_g):
        raise AssertionError("a pure-g equation contains an unexpected variable")

    inverse = sp.Symbol("g0inv")
    open_equations = pure_g + [Q, sp.expand(inverse * g0 - 1)]
    open_variables = g_variables + (inverse,)

    zero_equations = [sp.expand(expression.subs(g0, 0)) for expression in pure_g]
    zero_equations += [
        g0,
        sp.expand(indexed[33].subs(g0, 0)),
        sp.expand(indexed[37].subs(g0, 0)),
        sp.expand(indexed[38].subs(g0, 0)),
    ]
    zero_variables = g_variables + (f3,)
    if any(expression.has(f2) for expression in zero_equations):
        raise AssertionError("f2 must disappear on the g0=0 branch")

    return {
        "substitutions": substitutions,
        "variables": variables,
        "indexed": indexed,
        "g_variables": g_variables,
        "rows": rows,
        "cofactors": cofactors,
        "determinant": determinant,
        "Q": Q,
        "branches": {
            "g0_open": (open_equations, open_variables),
            "g0_zero": (zero_equations, zero_variables),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-compatibility-exact.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    data = exact_systems()

    branch_results: dict[str, object] = {}
    for branch_name, (equations, variables) in data["branches"].items():
        source = singular_source(equations, [], variables, 0, "qstd")
        source = source.replace(
            "exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;'
        )
        calculation = run_source(source, arguments.timeout)
        branch_results[branch_name] = {
            "characteristic": 0,
            "algorithm": "Singular qstd",
            "variable_names": [str(variable) for variable in variables],
            "variable_count": len(variables),
            "equation_count": len(equations),
            "maximum_total_degree": max(
                sp.Poly(expression, *variables).total_degree() for expression in equations
            ),
            "equation_stream_sha256": digest(tuple(equations)),
            "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
            "calculation": calculation,
            "exact_unit": bool(calculation["is_unit"]),
        }

    all_unit = all(result["exact_unit"] for result in branch_results.values())
    status = "PASS_EXACT_TANGENT_R5_EMPTY" if all_unit else "INCOMPLETE_BRANCH_CERTIFICATE"
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt = campaign / "receipts/residual-orbit-torus.json"
    torus_data = json.loads(torus_receipt.read_text(encoding="utf-8"))
    if torus_data.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    if torus_data.get("tangent", {}).get("alternative_rational_gauge") != "j2=-5":
        raise AssertionError("the torus receipt does not certify the j2=-5 gauge")
    if torus_data.get("tangent", {}).get("r5_sign_normalization") != (
        "under j2=-5 and top_index=5, set f5=1"
    ):
        raise AssertionError("the torus receipt does not certify the f5=1 sign slice")
    result = {
        "schema": "hc4-decimic-j2-tangent-r5-compatibility-certificate-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 5,
        "gauge": "primitive_j2=-5 and f5=1",
        "substitutions": data["substitutions"],
        "linear_equation_indices": list(LINEAR_INDICES),
        "pure_g_equation_indices": list(PURE_G_INDICES),
        "cofactor_identity_verified": True,
        "primitive_j2_on_slice": "-5",
        "torus_normalization_preconditions_verified": True,
        "compatibility_determinant_sha256": digest((data["determinant"],)),
        "compatibility_quotient_sha256": digest((data["Q"],)),
        "compatibility_factorization": "Delta=-55296*g0^2*Q",
        "compatibility_determinant_degree": sp.Poly(
            data["determinant"], *data["g_variables"]
        ).total_degree(),
        "compatibility_quotient_degree": sp.Poly(
            data["Q"], *data["g_variables"]
        ).total_degree(),
        "branch_results": branch_results,
        "gluing_argument": (
            "the g0-open unit gives g0^N in the slice ideal; the g0-zero unit "
            "makes g0 invertible modulo that ideal; hence the slice ideal is the unit ideal"
        ),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r5_compatibility.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_r5_rational_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_r5_rational_slice.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                torus_receipt.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact characteristic-zero emptiness of the "
            "tangent top_index=5 stratum via the previously certified torus/sign "
            "normalization; the other tangent strata and the secant orbit remain open"
        ),
    }
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all_unit else 1


if __name__ == "__main__":
    raise SystemExit(main())
