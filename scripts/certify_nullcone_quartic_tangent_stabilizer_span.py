#!/usr/bin/env python3
"""Propagate a tangent quartic highest-coordinate certificate to its family."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import s, t
from scout_decimic_nullcone_hsop import digest, f_coefficients, generic_decimic
from scout_nullcone_quartic_tangent_top_stratum import FAMILIES, load_family


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(family: str) -> str:
    return family.lower().replace("_", "-")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    family_slug = slug(arguments.family)
    highest_path = campaign / f"receipts/nullcone-{family_slug}-tangent-highest-all-strata.json"
    highest = json.loads(highest_path.read_text(encoding="utf-8"))
    if highest.get("status") != "PASS_EXACT_TANGENT_QUARTIC_HIGHEST_RADICAL_CONTAINMENT":
        raise AssertionError("the exact quartic highest-coordinate audit is unavailable")
    geometry_path = campaign / "receipts/nullcone-v6-tangent-stabilizer-span.json"
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    required = {
        "q_invariant",
        "target_q4x_invariant",
        "canonical_lift_chart_stable",
        "hessian_determinant_covariance_verified",
    }
    if geometry.get("status") != "PASS_EXACT_TANGENT_V6_FAMILY_RADICAL_CONTAINMENT" or not all(
        geometry["stabilizer"].get(key) for key in required
    ):
        raise AssertionError("the tangent stabilizer geometry is unavailable")
    target, profile, dictionary_path = load_family(campaign, arguments.family)
    order = int(profile["order"])

    u = sp.Symbol("u")
    binary = generic_decimic()
    transformed = sp.expand(binary.subs({t: t + u * s}))
    images = tuple(
        sp.Poly(transformed, s, t).coeff_monomial(s ** (10 - index) * t**index)
        for index in range(11)
    )
    orbit = sp.Poly(
        sp.expand(target.subs(dict(zip(f_coefficients, images, strict=True)), simultaneous=True)),
        u,
    )
    coefficients = [
        sp.expand(orbit.coeff_monomial(u**index)) for index in range(orbit.degree() + 1)
    ]
    dictionaries = [sp.Poly(item, *f_coefficients).as_dict() for item in coefficients]
    monomials = sorted(set().union(*dictionaries))
    matrix = sp.Matrix(
        [[dictionary.get(monomial, 0) for dictionary in dictionaries] for monomial in monomials]
    )
    rank = matrix.rank()
    if orbit.degree() != order or rank != order + 1:
        raise AssertionError("the tangent unipotent orbit does not span the quartic family")

    result = {
        "schema": "hc4.decimic-nullcone-quartic-tangent-stabilizer-span.v1",
        "status": "PASS_EXACT_TANGENT_QUARTIC_FAMILY_RADICAL_CONTAINMENT",
        "claim": (
            f"all {order + 1} coordinates of the quartic {arguments.family} family "
            "lie in the radical of the tangent residual-orbit normal-layer ideal"
        ),
        "family": arguments.family,
        "family_order": order,
        "characteristic": 0,
        "orbit": {
            "parameter_degree": orbit.degree(),
            "coefficient_count": len(coefficients),
            "exact_rank": rank,
            "coefficient_sha256": [digest((item,)) for item in coefficients],
        },
        "stabilizer_geometry_reused": {
            "receipt": str(geometry_path.relative_to(campaign)),
            "sha256": sha256(geometry_path),
            "all_required_checks_pass": True,
        },
        "inputs": {
            "highest_coordinate_audit": str(highest_path.relative_to(campaign)),
            "highest_coordinate_audit_sha256": sha256(highest_path),
            "quartic_dictionary": str(dictionary_path.relative_to(campaign)),
            "quartic_dictionary_sha256": sha256(dictionary_path),
        },
        "source_sha256": {
            "scripts/certify_nullcone_quartic_tangent_stabilizer_span.py": sha256(script_path),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero theorem candidate "
            "for one full quartic family on the tangent normal layer; other quartic "
            "families, secant, polynomial-level lifting, and HC4 remain open"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output or Path(
        f"receipts/nullcone-{family_slug}-tangent-stabilizer-span.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
