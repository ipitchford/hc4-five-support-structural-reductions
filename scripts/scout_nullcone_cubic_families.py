#!/usr/bin/env python3
"""Bounded orbitwise scouts for the two cubic nullcone-generator families.

The exact highest-weight lifts are imported from the independently replayable
cubic-covariant identification.  CoincidentRootLoci uses divided-power
coefficients ``a_i`` whereas the HC4 normal-layer code uses raw coefficients
``f_i``; hence ``a_i = f_i/binomial(10,i)``.

A finite-characteristic unit proves only a route signal.  It does not prove
characteristic-zero radical membership or the full SL2 family containment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp

import identify_decimic_nullcone_cubic_covariants as cubic
from scout_decimic_nullcone_hsop import (
    digest,
    f_coefficients,
    normal_equations,
    run_source,
    singular_source,
)


def primitive_integer_polynomial(expression: sp.Expr) -> sp.Expr:
    polynomial = sp.Poly(sp.expand(expression), *f_coefficients, domain=sp.QQ)
    denominators = [coefficient.q for coefficient in polynomial.coeffs()]
    denominator = sp.ilcm(*denominators)
    integral = sp.Poly(sp.expand(polynomial.as_expr() * denominator), *f_coefficients, domain=sp.ZZ)
    content = math.gcd(*(abs(int(value)) for value in integral.coeffs()))
    primitive = sp.expand(integral.as_expr() / content)
    leading = sp.Poly(primitive, *f_coefficients).LC()
    return sp.expand(-primitive if leading < 0 else primitive)


def raw_coefficient_family(name: str) -> sp.Expr:
    quadratic = cubic.parse_polynomial(cubic.V0_QUADRATIC_TEXT)
    v6 = cubic.parse_polynomial(cubic.V6_TEXT) - quadratic * cubic.a[2]
    weight2 = [cubic.parse_polynomial(text) for text in cubic.WEIGHT2_TEXTS]
    v2 = 6 * weight2[0] + weight2[1] - quadratic * cubic.a[4]
    divided_power = sp.expand(v6 if name == "V6" else v2)
    substitutions = {
        cubic.a[index]: f_coefficients[index] / sp.binomial(10, index)
        for index in range(11)
    }
    return primitive_integer_polynomial(divided_power.subs(substitutions))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=("V2", "V6"), required=True)
    parser.add_argument("--orbit", choices=("tangent", "secant"), required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be prime")

    started = time.perf_counter()
    target = raw_coefficient_family(arguments.family)
    equations, equation_build_seconds = normal_equations(arguments.orbit)
    source = singular_source(equations, target, arguments.characteristic)
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"]:
        disposition = "BOUNDED_MODULAR_RADICAL_SIGNAL"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    else:
        disposition = "NONUNIT_OR_ERROR_REQUIRES_EXACT_AUDIT"

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-nullcone-cubic-family-orbit-scout.v1",
        "family": arguments.family,
        "orbit": arguments.orbit,
        "characteristic": arguments.characteristic,
        "coefficient_dictionary": "a_i=f_i/binomial(10,i), then primitive integral content",
        "target": str(target),
        "target_term_count": len(sp.Poly(target, *f_coefficients).terms()),
        "target_sha256": digest((target,)),
        "normal_equation_count": len(equations),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "equation_build_seconds": equation_build_seconds,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_nullcone_cubic_families.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/identify_decimic_nullcone_cubic_covariants.py": hashlib.sha256(
                (script_path.parent / "identify_decimic_nullcone_cubic_covariants.py").read_bytes()
            ).hexdigest(),
            "receipts/decimic-nullcone-cubic-covariant-identification-corrected-lifts-exact.json": hashlib.sha256(
                (
                    script_path.parent.parent
                    / "receipts/decimic-nullcone-cubic-covariant-identification-corrected-lifts-exact.json"
                ).read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a finite-characteristic unit is a route signal for one highest-weight "
            "cubic on one fixed residual orbit; it is not characteristic-zero "
            "membership, full-family containment, nullcone containment, or HC4"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        output = script_path.parent.parent / (
            f"receipts/nullcone-cubic-{arguments.family.lower()}-{arguments.orbit}-p"
            f"{arguments.characteristic}.json"
        )
    elif not output.is_absolute():
        output = script_path.parent.parent / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
