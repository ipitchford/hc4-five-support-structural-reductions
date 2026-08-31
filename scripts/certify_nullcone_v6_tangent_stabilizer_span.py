#!/usr/bin/env python3
"""Propagate tangent V6-highest vanishing to the full cubic V6 family.

The tangent residual target q^4*x is preserved by the unipotent ternary map

    (x,y,z) -> (x, y+u*x, z+2*u*y+u^2*x),

whose restriction to the conic is (s,t) -> (s,t+u*s).  The exact orbit of
the already-certified highest coefficient has seven independent u
coefficients, hence spans the order-six irreducible cubic family.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import canonical_lift, q, s, t, x, y, z
from scout_decimic_nullcone_hsop import digest, f_coefficients, generic_decimic
from scout_five_support import general_cubic
from scout_nullcone_cubic_families import raw_coefficient_family


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def primitive_content(expression: sp.Expr) -> int:
    coefficients = sp.Poly(expression, *f_coefficients, domain=sp.QQ).coeffs()
    numerators = [abs(int(sp.Rational(value).p)) for value in coefficients if value]
    return int(sp.igcd(*numerators)) if numerators else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v6-tangent-stabilizer-span.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent

    highest_path = campaign / "receipts/nullcone-v6-tangent-highest-all-strata.json"
    highest = json.loads(highest_path.read_text(encoding="utf-8"))
    if highest.get("status") != "PASS_EXACT_TANGENT_V6_HIGHEST_RADICAL_CONTAINMENT":
        raise AssertionError("the exact highest-coordinate certificate is unavailable")
    cubic_path = (
        campaign
        / "receipts/decimic-nullcone-cubic-covariant-identification-corrected-lifts-exact.json"
    )
    cubic = json.loads(cubic_path.read_text(encoding="utf-8"))
    if cubic.get("status") != "PASS_EXACT_CUBIC_COVARIANT_IDENTIFICATION":
        raise AssertionError("the exact cubic covariant identification is unavailable")
    if cubic["checks"].get("m_order") != 6 or cubic["checks"].get("v6_weight") != 6:
        raise AssertionError("the identified cubic family is not the order-six V6")

    u = sp.Symbol("u")
    ternary_images = (x, y + u * x, z + 2 * u * y + u**2 * x)
    transformation = sp.Matrix(
        [
            [1, 0, 0],
            [u, 1, 0],
            [u**2, 2 * u, 1],
        ]
    )
    q_image = sp.expand(
        q.subs(dict(zip((x, y, z), ternary_images, strict=True)), simultaneous=True)
    )
    target_image = sp.expand(
        (q**4 * x).subs(
            dict(zip((x, y, z), ternary_images, strict=True)), simultaneous=True
        )
    )
    if (
        transformation.det() != 1
        or sp.expand(q_image - q) != 0
        or sp.expand(target_image - q**4 * x) != 0
    ):
        raise AssertionError("the tangent ternary unipotent does not preserve the target")
    conic_images = tuple(
        sp.expand(image.subs({x: s**2, y: s * t, z: t**2}))
        for image in ternary_images
    )
    expected_conic_images = (s**2, s * (t + u * s), (t + u * s) ** 2)
    if any(sp.expand(left - right) != 0 for left, right in zip(conic_images, expected_conic_images)):
        raise AssertionError("the ternary and binary unipotent actions disagree")

    # Exact stability of the chosen canonical-lift chart.  The transformed
    # quintic differs from the canonical lift of its transformed restriction
    # by q times another cubic, so the free cubic absorbs the correction.
    binary = generic_decimic()
    h5 = canonical_lift(binary, 5) + q * general_cubic
    h5_image = sp.expand(
        h5.subs(dict(zip((x, y, z), ternary_images, strict=True)), simultaneous=True)
    )
    binary_image = sp.expand(binary.subs({t: t + u * s}))
    chart_difference = sp.Poly(
        sp.expand(h5_image - canonical_lift(binary_image, 5)), z
    )
    chart_quotient, chart_remainder = sp.div(chart_difference, sp.Poly(q, z))
    if chart_remainder.as_expr() != 0 or sp.Poly(chart_quotient.as_expr(), x, y, z).total_degree() != 3:
        raise AssertionError("the tangent unipotent does not preserve the canonical-lift chart")

    # Chain-rule determinant check for an arbitrary symmetric Hessian matrix.
    h00, h01, h02, h11, h12, h22 = sp.symbols("h00 h01 h02 h11 h12 h22")
    generic_hessian = sp.Matrix(
        [[h00, h01, h02], [h01, h11, h12], [h02, h12, h22]]
    )
    hessian_covariance = sp.expand(
        (transformation.T * generic_hessian * transformation).det()
        - generic_hessian.det()
    )
    if hessian_covariance != 0:
        raise AssertionError("the determinant-one Hessian covariance check failed")

    transformed_binary = sp.expand(binary.subs({t: t + u * s}))
    coefficient_images = tuple(
        sp.Poly(transformed_binary, s, t).coeff_monomial(s ** (10 - index) * t**index)
        for index in range(11)
    )
    target = raw_coefficient_family("V6")
    orbit_polynomial = sp.Poly(
        sp.expand(
            target.subs(
                dict(zip(f_coefficients, coefficient_images, strict=True)),
                simultaneous=True,
            )
        ),
        u,
    )
    if orbit_polynomial.degree() != 6:
        raise AssertionError("the V6 unipotent orbit does not have degree six")
    orbit_coefficients = [
        sp.expand(orbit_polynomial.coeff_monomial(u**index)) for index in range(7)
    ]
    monomials = sorted(
        set().union(
            *(sp.Poly(item, *f_coefficients, domain=sp.QQ).as_dict() for item in orbit_coefficients)
        )
    )
    coefficient_matrix = sp.Matrix(
        [
            [
                sp.Poly(item, *f_coefficients, domain=sp.QQ).as_dict().get(monomial, 0)
                for item in orbit_coefficients
            ]
            for monomial in monomials
        ]
    )
    orbit_rank = coefficient_matrix.rank()
    if orbit_rank != 7 or orbit_coefficients[0] != target:
        raise AssertionError("the unipotent orbit does not span seven coordinates from V6")

    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-stabilizer-span.v1",
        "status": "PASS_EXACT_TANGENT_V6_FAMILY_RADICAL_CONTAINMENT",
        "claim": (
            "all seven coordinates of the cubic V6 nullcone-generator family lie "
            "in the radical of the tangent residual-orbit normal-layer ideal"
        ),
        "characteristic": 0,
        "stabilizer": {
            "binary_action": "(s,t)->(s,t+u*s)",
            "ternary_action": "(x,y,z)->(x,y+u*x,z+2*u*y+u^2*x)",
            "determinant": 1,
            "q_invariant": True,
            "target_q4x_invariant": True,
            "canonical_lift_chart_stable": True,
            "chart_correction_degree": 3,
            "hessian_determinant_covariance_verified": True,
        },
        "orbit": {
            "parameter_degree": orbit_polynomial.degree(),
            "coefficient_count": len(orbit_coefficients),
            "exact_rank": orbit_rank,
            "ambient_irreducible_dimension": 7,
            "coefficient_term_counts": [
                len(sp.Poly(item, *f_coefficients).terms()) for item in orbit_coefficients
            ],
            "coefficient_integer_contents": [
                primitive_content(item) for item in orbit_coefficients
            ],
            "coefficient_sha256": [digest((item,)) for item in orbit_coefficients],
            "orbit_polynomial_sha256": digest((orbit_polynomial.as_expr(),)),
        },
        "inputs": {
            "highest_coordinate_audit": str(highest_path.relative_to(campaign)),
            "highest_coordinate_audit_sha256": sha256(highest_path),
            "cubic_identification": str(cubic_path.relative_to(campaign)),
            "cubic_identification_sha256": sha256(cubic_path),
        },
        "source_sha256": {
            "scripts/certify_nullcone_v6_tangent_stabilizer_span.py": sha256(script_path),
            "scripts/scout_nullcone_cubic_families.py": sha256(
                campaign / "scripts/scout_nullcone_cubic_families.py"
            ),
            "scripts/reconstruct_normal_layers.py": sha256(
                campaign / "scripts/reconstruct_normal_layers.py"
            ),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero theorem candidate "
            "for the full cubic V6 family on the tangent normal layer; V2, the quartic "
            "families, the secant orbit, polynomial-level lifting, and HC4 remain open"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
