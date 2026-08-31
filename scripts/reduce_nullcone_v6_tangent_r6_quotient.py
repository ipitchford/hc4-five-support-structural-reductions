#!/usr/bin/env python3
"""Quotient-native reduction of the tangent V6 top-index-six cell.

The cover cell contains the unit relation ``topinv*f6-1`` and the normalized
V6 equation, whose coefficient of ``f0`` is ``648*f6^2``.  Hence ``f0`` can
be eliminated exactly with reciprocal ``topinv^2/648``.  All substituted
polynomials are then reduced monomialwise by ``f6*topinv=1`` before the
standard-basis calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, run_source
from scout_j2_normalized_chart import singular_source
from scout_nullcone_v6_tangent_top_stratum import stratum, top_inverse


def reduce_unit_pair(
    expression: sp.Expr,
    variables: tuple[sp.Symbol, ...],
    unit: sp.Symbol,
    inverse: sp.Symbol,
) -> sp.Expr:
    """Return the canonical Laurent-pair reduction modulo unit*inverse-1."""
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    unit_index = variables.index(unit)
    inverse_index = variables.index(inverse)
    result = sp.Integer(0)
    for exponents, coefficient in polynomial.terms():
        exponents = list(exponents)
        cancellation = min(exponents[unit_index], exponents[inverse_index])
        exponents[unit_index] -= cancellation
        exponents[inverse_index] -= cancellation
        result += coefficient * sp.prod(
            variable**exponent for variable, exponent in zip(variables, exponents)
        )
    return sp.expand(result)


def primitive(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> sp.Expr:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    denominator = sp.ilcm(1, *(coefficient.q for coefficient in polynomial.coeffs()))
    integral = sp.Poly(polynomial.as_expr() * denominator, *variables, domain=sp.ZZ)
    content = math.gcd(*(abs(int(coefficient)) for coefficient in integral.coeffs()))
    result = sp.expand(integral.as_expr() / content)
    return -result if sp.Poly(result, *variables).LC() < 0 else result


def reduced_system():
    equations, auxiliary, variables, substitutions, target, build_seconds = stratum(6)
    f0 = f_coefficients[0]
    f6 = f_coefficients[6]
    target_equation = auxiliary[0]
    unit_equation = auxiliary[1]
    polynomial = sp.Poly(target_equation, f0)
    if polynomial.degree() != 1:
        raise AssertionError("the normalized V6 equation is no longer linear in f0")
    coefficient = sp.expand(polynomial.coeff_monomial(f0))
    remainder = sp.expand(polynomial.coeff_monomial(1))
    if coefficient != 648 * f6**2:
        raise AssertionError(f"unexpected f0 pivot: {coefficient}")
    replacement = sp.expand(-remainder * top_inverse**2 / 648)

    substituted_target = sp.expand(target_equation.subs({f0: replacement}))
    target_reduction = reduce_unit_pair(substituted_target, variables, f6, top_inverse)
    if target_reduction != 0:
        raise AssertionError("the f0 replacement does not solve V6=1 modulo the unit relation")

    reduced_variables = tuple(variable for variable in variables if variable != f0)
    reduced_equations = []
    for equation in equations:
        substituted = sp.expand(equation.subs({f0: replacement}))
        reduced = reduce_unit_pair(substituted, variables, f6, top_inverse)
        if reduced != 0:
            reduced_equations.append(primitive(reduced, reduced_variables))
    reduced_unit = primitive(unit_equation, reduced_variables)
    reduced_auxiliary = [reduced_unit]
    return {
        "equations": reduced_equations,
        "auxiliary": reduced_auxiliary,
        "variables": reduced_variables,
        "substitutions": substitutions,
        "target": target,
        "build_seconds": build_seconds,
        "pivot_coefficient": coefficient,
        "replacement": replacement,
        "target_reduction": target_reduction,
        "original_variables": variables,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="std")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    data = reduced_system()
    equations = data["equations"]
    auxiliary = data["auxiliary"]
    variables = data["variables"]
    source = singular_source(
        equations,
        auxiliary,
        variables,
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        disposition = "PASS_EXACT_R6_COVER_CELL_EMPTY"
    elif calculation["is_unit"]:
        disposition = "PASS_MODULAR_R6_REDUCTION_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    before_equations, before_auxiliary, before_variables, *_ = stratum(6)
    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-r6-quotient-reduction.v1",
        "status": disposition,
        "orbit": "tangent",
        "family": "V6",
        "top_index": 6,
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "exact_reduction": {
            "unit_relation": "f6*topinv-1",
            "pivot_coefficient": str(data["pivot_coefficient"]),
            "eliminated_variable": "f0",
            "replacement": str(data["replacement"]),
            "target_remainder_after_unit_pair_reduction": str(data["target_reduction"]),
        },
        "before": {
            "variable_count": len(before_variables),
            "equation_count": len(before_equations) + len(before_auxiliary),
            "maximum_total_degree": max(
                sp.Poly(item, *before_variables).total_degree()
                for item in before_equations + before_auxiliary
            ),
            "total_term_count": sum(
                len(sp.Poly(item, *before_variables).terms())
                for item in before_equations + before_auxiliary
            ),
        },
        "after": {
            "variable_names": [str(variable) for variable in variables],
            "variable_count": len(variables),
            "equation_count": len(equations) + len(auxiliary),
            "maximum_total_degree": max(
                sp.Poly(item, *variables).total_degree() for item in equations + auxiliary
            ),
            "total_term_count": sum(
                len(sp.Poly(item, *variables).terms()) for item in equations + auxiliary
            ),
            "equation_stream_sha256": digest(tuple(equations)),
            "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        },
        "calculation": calculation,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/reduce_nullcone_v6_tangent_r6_quotient.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/scout_nullcone_v6_tangent_top_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_nullcone_v6_tangent_top_stratum.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing characteristic-zero result closes only the r=6 cell of "
            "the highest-weight tangent cover; five other cells and the full-family "
            "gate remain separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = script_path.parent.parent / f"receipts/nullcone-v6-tangent-r6-quotient-{field}.json"
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
