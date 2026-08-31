#!/usr/bin/env python3
"""Tangent first-jet scouts for the cubic V6 nullcone family.

On the open where the primitive highest-weight cubic C6 is nonzero, its
residual-orbit torus weight is six, so C6 may be normalized to one.  Its
monomial support forces the largest nonzero decimic coefficient to have index
5 through 10.  The tangent unipotent then sets the preceding coefficient to
zero on each stratum.

Finite-characteristic units are route signals only.  Exact characteristic-zero
certificates and the stabilizer-to-full-family argument are separate gates.
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


def stratum(top_index: int):
    equations, build_seconds = normal_equations("tangent")
    target = raw_coefficient_family("V6")
    substitutions = {
        **{f_coefficients[index]: 0 for index in range(top_index + 1, 11)},
        f_coefficients[top_index - 1]: 0,
    }
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    reduced_target = sp.expand(target.subs(substitutions))
    if reduced_target == 0:
        raise AssertionError("V6 vanished identically on a claimed open stratum")
    localizers = [sp.expand(reduced_target - 1)]
    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    variables = remaining_f + g_coefficients
    eliminated = set(substitutions)
    if any(expression.free_symbols & eliminated for expression in reduced + localizers):
        raise AssertionError("an eliminated coefficient survived the stratum")
    return reduced, localizers, variables, substitutions, reduced_target, build_seconds


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(5, 11), required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="std")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    equations, localizers, variables, substitutions, target, build_seconds = stratum(
        arguments.top_index
    )
    source = singular_source(
        equations,
        localizers,
        variables,
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        disposition = "EXACT_HIGHEST_WEIGHT_RADICAL_ON_STRATUM"
    elif calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_UNIT_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-first-jet-scout.v1",
        "orbit": "tangent",
        "family": "V6",
        "top_index": arguments.top_index,
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "substitutions": {str(key): int(value) for key, value in substitutions.items()},
        "normalization": "primitive V6 highest-weight polynomial = 1",
        "target_after_substitution": str(target),
        "target_term_count": len(sp.Poly(target, *variables).terms()),
        "target_sha256": digest((target,)),
        "normal_equation_count": len(equations),
        "localizer_count": len(localizers),
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in equations + localizers
        ),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "localizer_stream_sha256": digest(tuple(localizers)),
        "equation_build_seconds": build_seconds,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_nullcone_v6_tangent_stratum.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/scout_nullcone_cubic_families.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_cubic_families.py").read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                (script_path.parent.parent / "receipts/residual-orbit-torus.json").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a modular unit is a route signal for one tangent first-jet stratum; "
            "all six exact characteristic-zero strata plus a formal stabilizer "
            "argument are required for tangent V6-family containment"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = script_path.parent.parent / (
            f"receipts/nullcone-v6-tangent-r{arguments.top_index}-{field}.json"
        )
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
