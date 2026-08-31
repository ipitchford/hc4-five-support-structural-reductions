#!/usr/bin/env python3
"""Identify the cubic generators of the padded-binary-decimic ideal.

The CoincidentRootLoci package uses the divided-power convention

    F(x,y) = sum(binomial(10,i) * a_i * x^(10-i) * y^i, i=0..10).

This script forms the classical transvectants

    j2 = (F,F)_10,
    C6[r] = (F,(F,F)_r)_(12-r),  r in {2,4,6,8},
    C2[r] = (F,(F,F)_r)_(14-r),  r in {4,6},

and compares the endpoint coefficients of m and r with exact minimal
generators extracted from the ideal of CRL(6,1,1,1,1).  It also checks the
SL2 lowering relation which distinguishes the V2 cubic from the weight-2
descendant of the V6 cubic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Iterable, Sequence

import sympy as sp


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
EXTRACTOR = HERE / "extract_decimic_nullcone_weight_generators.m2"
M2_PACKAGE = Path("/opt/homebrew/share/Macaulay2/CoincidentRootLoci.m2")
M2_DOCS = Path("/opt/homebrew/share/Macaulay2/CoincidentRootLoci/documentation.m2")

x, y = sp.symbols("x y")
a = sp.symbols("a_0:11")
LOCAL_DICT = {str(v): v for v in a}


V6_TEXT = """
42*a_1*a_5*a_6-126*a_0*a_6**2-90*a_1*a_4*a_7+210*a_0*a_5*a_7
+75*a_1*a_3*a_8-120*a_0*a_4*a_8-35*a_1*a_2*a_9+45*a_0*a_3*a_9
+9*a_1**2*a_10-10*a_0*a_2*a_10
"""

V0_QUADRATIC_TEXT = """
126*a_5**2-210*a_4*a_6+120*a_3*a_7-45*a_2*a_8+10*a_1*a_9-a_0*a_10
"""

WEIGHT2_TEXTS = [
    """
54*a_2*a_5*a_7-150*a_1*a_6*a_7+168*a_0*a_7**2-135*a_2*a_4*a_8
+315*a_1*a_5*a_8-270*a_0*a_6*a_8+135*a_2*a_3*a_9-250*a_1*a_4*a_9
+135*a_0*a_5*a_9-72*a_2**2*a_10+105*a_1*a_3*a_10-35*a_0*a_4*a_10
""",
    """
84*a_3*a_5*a_6-210*a_2*a_6**2-180*a_3*a_4*a_7+960*a_1*a_6*a_7
-1050*a_0*a_7**2+150*a_3**2*a_8+675*a_2*a_4*a_8-2016*a_1*a_5*a_8
+1686*a_0*a_6*a_8-870*a_2*a_3*a_9+1600*a_1*a_4*a_9-840*a_0*a_5*a_9
+450*a_2**2*a_10-654*a_1*a_3*a_10+215*a_0*a_4*a_10
""",
]


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def transvectant(first: sp.Expr, second: sp.Expr, order: int) -> sp.Expr:
    """Return the unnormalised order-th transvectant."""
    result = sp.Integer(0)
    for index in range(order + 1):
        result += (
            (-1) ** index
            * sp.binomial(order, index)
            * sp.diff(first, x, order - index, y, index)
            * sp.diff(second, x, index, y, order - index)
        )
    return sp.expand(result)


def parse_polynomial(text: str) -> sp.Expr:
    return sp.Poly(sp.sympify(text, locals=LOCAL_DICT), *a, domain=sp.QQ).as_expr()


def coefficient_vector(polynomial: sp.Expr, monomials: Sequence[tuple[int, ...]]) -> sp.Matrix:
    poly = sp.Poly(polynomial, *a, domain=sp.QQ)
    values = poly.as_dict()
    return sp.Matrix([values.get(monomial, sp.Integer(0)) for monomial in monomials])


def exact_coordinates(target: sp.Expr, basis: Sequence[sp.Expr]) -> list[sp.Rational] | None:
    dictionaries = [sp.Poly(item, *a, domain=sp.QQ).as_dict() for item in [target, *basis]]
    monomials = sorted(set().union(*(dictionary.keys() for dictionary in dictionaries)))
    matrix = sp.Matrix.hstack(*(coefficient_vector(item, monomials) for item in basis))
    vector = coefficient_vector(target, monomials)
    try:
        solution, parameters = matrix.gauss_jordan_solve(vector)
    except ValueError:
        return None
    if parameters.rows:
        # A non-unique expression is still useful, but freeze the canonical zero
        # specialisation of the free parameters.
        solution = solution.subs({symbol: 0 for symbol in parameters})
    coordinates = [sp.Rational(value) for value in solution]
    if sp.expand(target - sum(c * b for c, b in zip(coordinates, basis))) != 0:
        return None
    return coordinates


def lower(polynomial: sp.Expr) -> sp.Expr:
    """The weight-lowering vector field for divided-power coefficients."""
    return sp.expand(sum((10 - index) * a[index + 1] * sp.diff(polynomial, a[index]) for index in range(10)))


def raise_weight(polynomial: sp.Expr) -> sp.Expr:
    """The weight-raising vector field for divided-power coefficients."""
    return sp.expand(sum(index * a[index - 1] * sp.diff(polynomial, a[index]) for index in range(1, 11)))


def endpoint(covariant: sp.Expr, order: int, side: str) -> sp.Expr:
    if side == "x":
        return sp.expand(covariant.coeff(x, order).coeff(y, 0))
    return sp.expand(covariant.coeff(x, 0).coeff(y, order))


def rational_strings(values: Iterable[sp.Rational] | None) -> list[str] | None:
    return None if values is None else [str(value) for value in values]


def primitive_vector(vector: sp.Matrix) -> list[sp.Integer]:
    """Clear denominators and content, then choose a positive leading sign."""
    values = [sp.Rational(value) for value in vector]
    common_denominator = sp.ilcm(*(value.q for value in values))
    integers = [sp.Integer(value * common_denominator) for value in values]
    content = sp.igcd(*(abs(int(value)) for value in integers if value != 0))
    if content:
        integers = [value // content for value in integers]
    first_nonzero = next((value for value in integers if value != 0), sp.Integer(1))
    if first_nonzero < 0:
        integers = [-value for value in integers]
    return integers


def intersection_relations(left: Sequence[sp.Expr], right: Sequence[sp.Expr]) -> list[dict[str, list[str]]]:
    """Return primitive relations sum(left_i*u_i) = sum(right_j*v_j)."""
    dictionaries = [sp.Poly(item, *a, domain=sp.QQ).as_dict() for item in [*left, *right]]
    monomials = sorted(set().union(*(dictionary.keys() for dictionary in dictionaries)))
    left_matrix = sp.Matrix.hstack(*(coefficient_vector(item, monomials) for item in left))
    right_matrix = sp.Matrix.hstack(*(coefficient_vector(item, monomials) for item in right))
    kernel = left_matrix.row_join(-right_matrix).nullspace()
    relations = []
    for vector in kernel:
        primitive = primitive_vector(vector)
        relations.append(
            {
                "extracted_coordinates": [str(value) for value in primitive[: len(left)]],
                "transvectant_coordinates": [str(value) for value in primitive[len(left) :]],
            }
        )
    return relations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write the JSON receipt here")
    args = parser.parse_args()

    form = sp.expand(
        sum(sp.binomial(10, index) * a[index] * x ** (10 - index) * y**index for index in range(11))
    )

    j2 = transvectant(form, form, 10)
    quadratic_covariants = {order: transvectant(form, form, order) for order in (2, 4, 6, 8)}
    order6_channels = {
        order: transvectant(form, quadratic_covariants[order], 12 - order)
        for order in (2, 4, 6, 8)
    }
    order2_channels = {
        order: transvectant(form, quadratic_covariants[order], 14 - order)
        for order in (4, 6)
    }

    quadratic = parse_polynomial(V0_QUADRATIC_TEXT)
    v6 = parse_polynomial(V6_TEXT)
    weight2 = [parse_polynomial(text) for text in WEIGHT2_TEXTS]

    # Canonical highest-weight representatives in the ideal.  The printed
    # minimal generators are only defined modulo the quadratic ideal times
    # linear forms.
    v6_highest = sp.expand(v6 - quadratic * a[2])
    v2_highest = sp.expand(6 * weight2[0] + weight2[1] - quadratic * a[4])
    lowered_v6 = lower(lower(v6_highest))

    endpoint_tests: dict[str, object] = {}
    for side in ("x", "y"):
        order6_endpoints = [endpoint(order6_channels[index], 6, side) for index in (2, 4, 6, 8)]
        order2_endpoints = [endpoint(order2_channels[index], 2, side) for index in (4, 6)]
        endpoint_tests[side] = {
            "v6_highest_in_order6_channel_coordinates": rational_strings(
                exact_coordinates(v6_highest, order6_endpoints)
            ),
            "v2_highest_in_order2_channel_coordinates": rational_strings(
                exact_coordinates(v2_highest, order2_endpoints)
            ),
            "v6_full_ideal_intersection_relations": intersection_relations(
                [v6, quadratic * a[2]], order6_endpoints
            ),
            "v2_full_ideal_intersection_relations": intersection_relations(
                [*weight2, quadratic * a[4]], order2_endpoints
            ),
            "order6_channel_terms": [len(sp.Poly(item, *a).terms()) for item in order6_endpoints],
            "order2_channel_terms": [len(sp.Poly(item, *a).terms()) for item in order2_endpoints],
        }

    matched_sides = [
        side
        for side, test in endpoint_tests.items()
        if test["v6_highest_in_order6_channel_coordinates"] is not None
        and test["v2_highest_in_order2_channel_coordinates"] is not None
    ]

    lowering_coordinates = exact_coordinates(lowered_v6, [*weight2, quadratic * a[4]])

    # The two cubic summands must be independent: the V2 endpoint cannot be the
    # weight-2 descendant of V6.
    independence = None
    v2_full_ideal_coordinates = [sp.Integer(6), sp.Integer(1), sp.Integer(-1)]
    if matched_sides and lowering_coordinates is not None:
        coordinate_matrix = sp.Matrix.hstack(sp.Matrix(lowering_coordinates), sp.Matrix(v2_full_ideal_coordinates))
        independence = coordinate_matrix.rank() == 2

    highest_weight_checks = {
        "quadratic_is_invariant": raise_weight(quadratic) == 0 and lower(quadratic) == 0,
        "v6_highest_is_raising_annihilated": raise_weight(v6_highest) == 0,
        "v2_highest_is_raising_annihilated": raise_weight(v2_highest) == 0,
    }
    j2_coordinates = exact_coordinates(j2, [quadratic])
    highest_weight_checks["j2_matches_quadratic"] = j2_coordinates is not None

    receipt = {
        "schema": "hc4.decimic-nullcone-cubic-covariant-identification.v2",
        "status": "PASS_EXACT_CUBIC_COVARIANT_IDENTIFICATION"
        if matched_sides
        and lowering_coordinates is not None
        and independence
        and all(highest_weight_checks.values())
        else "FAIL_EXACT_CUBIC_COVARIANT_IDENTIFICATION",
        "coefficient_convention": "F=sum(binomial(10,i)*a_i*x^(10-i)*y^i)",
        "transvectant_convention": "unnormalised alternating derivative sum",
        "matched_sides": matched_sides,
        "endpoint_tests": endpoint_tests,
        "canonical_lifts": {
            "v6": "g6 - J2*a_2",
            "v2": "6*g2_1 + g2_2 - J2*a_4",
        },
        "highest_weight_checks": highest_weight_checks,
        "j2_quadratic_coordinates": rational_strings(j2_coordinates),
        "lower_squared_v6_weight2_coordinates": rational_strings(lowering_coordinates),
        "v2_full_ideal_coordinates": rational_strings(v2_full_ideal_coordinates),
        "v2_independent_of_lowered_v6": independence,
        "checks": {
            "m_order": 6,
            "r_order": 2,
            "v6_weight": 6,
            "weight2_slice_dimension": 2,
            "j2_terms": len(sp.Poly(j2, *a).terms()),
        },
        "inputs": {
            "extractor": str(EXTRACTOR.relative_to(CAMPAIGN)),
            "extractor_sha256": sha256(EXTRACTOR),
            "macaulay2_package_sha256": sha256(M2_PACKAGE),
            "macaulay2_documentation_sha256": sha256(M2_DOCS),
            "documentation_normalisation_location": "CoincidentRootLoci/documentation.m2, binary-form switch paragraph",
        },
        "runtime": {
            "python": platform.python_version(),
            "sympy": sp.__version__,
            "platform": platform.platform(),
        },
    }

    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["status"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
