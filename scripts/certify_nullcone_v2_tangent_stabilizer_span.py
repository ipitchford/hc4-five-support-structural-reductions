#!/usr/bin/env python3
"""Propagate tangent V2-highest vanishing to the full cubic V2 family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import s, t
from scout_decimic_nullcone_hsop import digest, f_coefficients, generic_decimic
from scout_nullcone_cubic_families import raw_coefficient_family


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v2-tangent-stabilizer-span.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent

    highest_path = campaign / "receipts/nullcone-v2-tangent-highest-all-strata.json"
    highest = json.loads(highest_path.read_text(encoding="utf-8"))
    if highest.get("status") != "PASS_EXACT_TANGENT_V2_HIGHEST_RADICAL_CONTAINMENT":
        raise AssertionError("the exact V2 highest-coordinate certificate is unavailable")
    geometry_path = campaign / "receipts/nullcone-v6-tangent-stabilizer-span.json"
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    if geometry.get("status") != "PASS_EXACT_TANGENT_V6_FAMILY_RADICAL_CONTAINMENT":
        raise AssertionError("the exact tangent stabilizer geometry is unavailable")
    required_geometry = {
        "q_invariant",
        "target_q4x_invariant",
        "canonical_lift_chart_stable",
        "hessian_determinant_covariance_verified",
    }
    if not all(geometry["stabilizer"].get(key) for key in required_geometry):
        raise AssertionError("the tangent stabilizer geometry receipt is incomplete")
    cubic_path = (
        campaign
        / "receipts/decimic-nullcone-cubic-covariant-identification-corrected-lifts-exact.json"
    )
    cubic = json.loads(cubic_path.read_text(encoding="utf-8"))
    if cubic.get("status") != "PASS_EXACT_CUBIC_COVARIANT_IDENTIFICATION":
        raise AssertionError("the exact cubic covariant identification is unavailable")
    if cubic["checks"].get("r_order") != 2 or not cubic["highest_weight_checks"].get(
        "v2_highest_is_raising_annihilated"
    ):
        raise AssertionError("the identified target is not the highest coordinate of V2")

    u = sp.Symbol("u")
    binary = generic_decimic()
    transformed_binary = sp.expand(binary.subs({t: t + u * s}))
    coefficient_images = tuple(
        sp.Poly(transformed_binary, s, t).coeff_monomial(s ** (10 - index) * t**index)
        for index in range(11)
    )
    target = raw_coefficient_family("V2")
    orbit_polynomial = sp.Poly(
        sp.expand(
            target.subs(
                dict(zip(f_coefficients, coefficient_images, strict=True)),
                simultaneous=True,
            )
        ),
        u,
    )
    if orbit_polynomial.degree() != 2:
        raise AssertionError("the V2 orbit polynomial does not have degree two")
    orbit_coefficients = [
        sp.expand(orbit_polynomial.coeff_monomial(u**index)) for index in range(3)
    ]
    dictionaries = [
        sp.Poly(item, *f_coefficients, domain=sp.QQ).as_dict()
        for item in orbit_coefficients
    ]
    monomials = sorted(set().union(*dictionaries))
    matrix = sp.Matrix(
        [[dictionary.get(monomial, 0) for dictionary in dictionaries] for monomial in monomials]
    )
    rank = matrix.rank()
    if rank != 3 or orbit_coefficients[0] != target:
        raise AssertionError("the tangent unipotent orbit does not span V2")

    result = {
        "schema": "hc4.decimic-nullcone-v2-tangent-stabilizer-span.v1",
        "status": "PASS_EXACT_TANGENT_V2_FAMILY_RADICAL_CONTAINMENT",
        "claim": (
            "all three coordinates of the cubic V2 nullcone-generator family lie "
            "in the radical of the tangent residual-orbit normal-layer ideal"
        ),
        "characteristic": 0,
        "stabilizer_geometry_reused": {
            "receipt": str(geometry_path.relative_to(campaign)),
            "sha256": sha256(geometry_path),
            "binary_action": geometry["stabilizer"]["binary_action"],
            "ternary_action": geometry["stabilizer"]["ternary_action"],
            "all_required_checks_pass": True,
        },
        "orbit": {
            "parameter_degree": orbit_polynomial.degree(),
            "coefficient_count": len(orbit_coefficients),
            "exact_rank": rank,
            "ambient_irreducible_dimension": 3,
            "coefficient_term_counts": [
                len(sp.Poly(item, *f_coefficients).terms()) for item in orbit_coefficients
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
            "scripts/certify_nullcone_v2_tangent_stabilizer_span.py": sha256(script_path),
            "scripts/scout_nullcone_cubic_families.py": sha256(
                campaign / "scripts/scout_nullcone_cubic_families.py"
            ),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero theorem candidate "
            "for the full cubic V2 family on the tangent normal layer; the quartic "
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
