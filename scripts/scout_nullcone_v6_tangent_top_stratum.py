#!/usr/bin/env python3
"""Branch-safe tangent top-index scouts for the cubic V6 coefficient.

The primitive highest-weight coefficient C6 has nonzero tangent torus weight,
so C6 != 0 may be normalized to C6 = 1.  The remaining split records the
largest nonzero decimic coefficient f_r without using the tangent unipotent:

    f_(r+1)=...=f_10=0,  f_r != 0.

This is an exhaustive cover of C6 != 0 because the explicit target vanishes
when f_5=...=f_10=0.  For r>5, f_r != 0 is retained by an inverse variable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import singular_source
from scout_nullcone_cubic_families import raw_coefficient_family


top_inverse = sp.Symbol("topinv")


def stratum(top_index: int):
    equations, build_seconds = normal_equations("tangent")
    target = raw_coefficient_family("V6")
    substitutions = {
        f_coefficients[index]: 0 for index in range(top_index + 1, 11)
    }
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    reduced_target = sp.expand(target.subs(substitutions))
    if reduced_target == 0:
        raise AssertionError("V6 vanished identically on a claimed top stratum")
    auxiliary = [sp.expand(reduced_target - 1)]
    inverse_variables: tuple[sp.Symbol, ...] = ()
    if top_index > 5:
        auxiliary.append(sp.expand(top_inverse * f_coefficients[top_index] - 1))
        inverse_variables = (top_inverse,)
    elif sp.expand(reduced_target.subs({f_coefficients[5]: 0})) != 0:
        raise AssertionError("the r=5 target no longer forces f5 nonzero")
    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    variables = remaining_f + g_coefficients + inverse_variables
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + auxiliary):
        raise AssertionError("an eliminated coefficient survived the top stratum")
    return reduced, auxiliary, variables, substitutions, reduced_target, build_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(5, 11), required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="std")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    equations, auxiliary, variables, substitutions, target, build_seconds = stratum(
        arguments.top_index
    )
    source = singular_source(
        equations,
        auxiliary,
        variables,
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        disposition = "EXACT_HIGHEST_WEIGHT_RADICAL_ON_COVER_STRATUM"
    elif calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-top-stratum.v1",
        "status": disposition,
        "orbit": "tangent",
        "family": "V6",
        "top_index": arguments.top_index,
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "cover_statement": "V6=1; f_(r+1)=...=f10=0; f_r!=0",
        "unipotent_used": False,
        "substitutions": {str(key): int(value) for key, value in substitutions.items()},
        "target_after_substitution": str(target),
        "target_term_count": len(sp.Poly(target, *variables).terms()),
        "target_sha256": digest((target,)),
        "normal_equation_count": len(equations),
        "auxiliary_equation_count": len(auxiliary),
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + auxiliary
        ),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "equation_build_seconds": build_seconds,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_nullcone_v6_tangent_top_stratum.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/scout_nullcone_cubic_families.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_cubic_families.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                (script_path.parent.parent / "receipts/residual-orbit-torus.json").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "all six cover strata need exact characteristic-zero units to prove "
            "radical membership of this single highest-weight coefficient; "
            "full V6-family containment remains a separate stabilizer/covariant gate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = script_path.parent.parent / (
            f"receipts/nullcone-v6-tangent-top-r{arguments.top_index}-{field}.json"
        )
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
