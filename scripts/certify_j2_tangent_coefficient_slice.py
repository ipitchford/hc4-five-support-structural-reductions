#!/usr/bin/env python3
"""Exact coefficient-normalized tangent j2 certificate for top index 6--10."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import primitive_j2, singular_source


j2_inverse = sp.Symbol("j2inv")


def coefficient_slice(
    top_index: int,
) -> tuple[list[sp.Expr], list[sp.Expr], tuple[sp.Symbol, ...], dict[str, int], sp.Expr]:
    equations, _ = normal_equations("tangent")
    substitutions = {
        f_coefficients[top_index - 1]: 0,
        f_coefficients[top_index]: 1,
        **{f_coefficients[index]: 0 for index in range(top_index + 1, 11)},
    }
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    j2 = sp.expand(primitive_j2().subs(substitutions))
    if j2 == 0:
        raise AssertionError("j2 vanished identically on a claimed nonzero stratum")
    localizers = [sp.expand(j2_inverse * j2 - 1)]
    remaining_f = tuple(
        coefficient for coefficient in f_coefficients if coefficient not in substitutions
    )
    variables = remaining_f + g_coefficients + (j2_inverse,)
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + localizers):
        raise AssertionError("an eliminated coefficient survived the slice")
    return (
        reduced,
        localizers,
        variables,
        {str(symbol): int(value) for symbol, value in substitutions.items()},
        j2,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(6, 11), required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    equations, localizers, variables, substitutions, j2 = coefficient_slice(
        arguments.top_index
    )

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    torus_receipt_path = campaign / "receipts/residual-orbit-torus.json"
    torus_receipt = json.loads(torus_receipt_path.read_text(encoding="utf-8"))
    if torus_receipt.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    weight = torus_receipt["tangent"]["coefficient_weights"][arguments.top_index]
    if weight == 0:
        raise AssertionError("the selected top coefficient cannot be normalized")
    if arguments.top_index not in torus_receipt["tangent_unipotent"][
        "exhaustive_first_nonzero_indices_under_j2_nonzero"
    ]:
        raise AssertionError("the selected top index is absent from the exact cover")

    source = singular_source(equations, localizers, variables, 0, "slimgb")
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_TANGENT_STRATUM_EMPTY"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_TANGENT_STRATUM"
    )
    result = {
        "schema": "hc4-decimic-j2-tangent-coefficient-slice-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": arguments.top_index,
        "coefficient_normalization": f"f{arguments.top_index}=1",
        "coefficient_torus_weight": weight,
        "unipotent_normalization": f"f{arguments.top_index - 1}=0",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "j2_sha256": digest((j2,)),
        "localizer": str(localizers[0]),
        "characteristic": 0,
        "algorithm": "Singular slimgb",
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_equation_count": len(equations),
        "localizer_count": len(localizers),
        "generator_count": len(equations) + len(localizers),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + localizers
        ),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "localizer_stream_sha256": digest(tuple(localizers)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "torus_normalization_preconditions_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_coefficient_slice.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_residual_orbit_torus.py": hashlib.sha256(
                (script_path.parent / "certify_residual_orbit_torus.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                torus_receipt_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact characteristic-zero emptiness of this "
            "single tangent first-nonzero-jet stratum; all six tangent strata are "
            "required for tangent j2 radical containment, and the secant orbit remains"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-tangent-r{arguments.top_index}-coefficient-slice-exact.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
