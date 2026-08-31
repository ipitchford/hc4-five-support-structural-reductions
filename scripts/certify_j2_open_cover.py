#!/usr/bin/env python3
"""Certify the six-open cover of the binary-decimic ``j2 != 0`` locus.

The HSOP reconstruction uses an unnormalised transvectant.  This producer
removes its integer content, freezes the resulting primitive quadratic, and
checks the elementary but logically important cover

    D(j2) subset union_i D(m_i),

where the ``m_i`` are the six reciprocal-pair monomials in ``j2``.  In finite
characteristic the same cover is asserted only away from primes annihilating a
primitive coefficient.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import reduce
from math import gcd
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import (
    f_coefficients,
    generic_decimic,
    selected_hsop,
)


EXPECTED_MONOMIALS = (
    (0, 10),
    (1, 9),
    (2, 8),
    (3, 7),
    (4, 6),
    (5, 5),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(expression: sp.Expr) -> str:
    return str(sp.expand(expression)).replace("**", "^")


def prime_divisors(integer: int) -> list[int]:
    return sorted(int(prime) for prime in sp.factorint(abs(integer)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/j2-open-cover.json"),
    )
    arguments = parser.parse_args()

    raw = sp.Poly(
        selected_hsop(generic_decimic(), "j2"),
        *f_coefficients,
        domain=sp.ZZ,
    )
    raw_coefficients = [int(coefficient) for _, coefficient in raw.terms()]
    content = reduce(gcd, (abs(coefficient) for coefficient in raw_coefficients))
    if content <= 0:
        raise AssertionError("j2 must have nonzero integer content")

    primitive = sp.Poly(raw.as_expr() / content, *f_coefficients, domain=sp.ZZ)
    if primitive.LC() < 0:
        primitive = -primitive
    if len(primitive.terms()) != 6:
        raise AssertionError("expected exactly six primitive j2 terms")

    rows: list[dict[str, object]] = []
    term_sum = sp.Integer(0)
    coefficient_product = 1
    observed_monomials: list[tuple[int, int]] = []
    for exponent_vector, coefficient_value in primitive.terms():
        coefficient = int(coefficient_value)
        support: list[int] = []
        for index, exponent in enumerate(exponent_vector):
            support.extend([index] * exponent)
        if len(support) != 2:
            raise AssertionError(f"nonquadratic term support: {support}")
        observed_monomials.append(tuple(support))
        monomial = sp.prod(
            symbol**exponent
            for symbol, exponent in zip(f_coefficients, exponent_vector)
        )
        term = coefficient * monomial
        term_sum += term
        coefficient_product *= coefficient
        rows.append(
            {
                "chart": f"pair_{support[0]}_{support[1]}",
                "coefficient": coefficient,
                "exponent_vector": list(exponent_vector),
                "monomial": render(monomial),
                "term": render(term),
            }
        )

    if tuple(observed_monomials) != EXPECTED_MONOMIALS:
        raise AssertionError(
            f"unexpected reciprocal-pair order: {observed_monomials}"
        )
    if sp.expand(term_sum - primitive.as_expr()) != 0:
        raise AssertionError("six displayed terms do not sum to primitive j2")
    if reduce(gcd, (abs(int(c)) for _, c in primitive.terms())) != 1:
        raise AssertionError("normalised j2 is not primitive")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    dependency_paths = (
        script_path,
        script_path.parent / "scout_decimic_nullcone_hsop.py",
        script_path.parent / "reconstruct_decimic_hsop.py",
    )
    exceptional_primes = prime_divisors(coefficient_product)
    result = {
        "schema": "hc4-decimic-j2-open-cover-v1",
        "status": "PASS",
        "raw_transvectant_content": content,
        "primitive_j2": render(primitive.as_expr()),
        "primitive_coefficients": [
            int(coefficient) for _, coefficient in primitive.terms()
        ],
        "terms": rows,
        "term_count": len(rows),
        "cover_statement_characteristic_zero": (
            "D(j2) is contained in the union of the six D(m_i), because "
            "j2=sum_i c_i*m_i and all c_i are nonzero"
        ),
        "finite_characteristic_exceptional_primes": exceptional_primes,
        "finite_characteristic_scope": (
            "the identical six-open argument is valid away from primes "
            "annihilating a primitive coefficient"
        ),
        "checks": {
            "primitive_integer_content_one": True,
            "six_terms": True,
            "reciprocal_pair_supports": True,
            "displayed_sum_equals_primitive_j2": True,
            "all_primitive_coefficients_nonzero": True,
        },
        "source_sha256": {
            str(path.relative_to(campaign)): sha256(path)
            for path in dependency_paths
        },
        "claim_boundary": (
            "this certifies only the open cover used to test j2 radical "
            "containment; it proves neither a chart unit nor nullcone containment"
        ),
    }

    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
