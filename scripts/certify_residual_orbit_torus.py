#!/usr/bin/env python3
"""Certify torus normalizations preserving the two residual-quadratic orbits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import q, s, t, x, y, z


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/residual-orbit-torus.json"),
    )
    arguments = parser.parse_args()

    sigma, tau, u = sp.symbols("sigma tau u", nonzero=True)
    f = sp.symbols("f0:11")
    binary = sum(f[index] * s ** (10 - index) * t**index for index in range(11))

    # Tangent: a=sigma^3, b=1, h-scale c=sigma^-16.  The determinant
    # covariance factor is c^3*(ab)^14*a^2=1 and coefficient i has the
    # displayed nonzero weight.
    tangent_weights = tuple(14 - 3 * index for index in range(11))
    tangent_factor = sp.simplify((sigma**-16) ** 3 * (sigma**3) ** 14 * (sigma**3) ** 2)
    tangent_transformed = sp.expand(
        sigma**-16 * binary.subs({s: sigma**3 * s, t: t})
    )
    tangent_coefficients = tuple(
        sp.Poly(tangent_transformed, s, t).coeff_monomial(
            s ** (10 - index) * t**index
        )
        for index in range(11)
    )

    # Secant: a=tau, b=1, h-scale c=tau^-5.  Here
    # c^3*(ab)^15=1 and coefficient i has weight 5-i.
    secant_weights = tuple(5 - index for index in range(11))
    secant_factor = sp.simplify((tau**-5) ** 3 * tau**15)
    secant_transformed = sp.expand(
        tau**-5 * binary.subs({s: tau * s, t: t})
    )
    secant_coefficients = tuple(
        sp.Poly(secant_transformed, s, t).coeff_monomial(
            s ** (10 - index) * t**index
        )
        for index in range(11)
    )

    tangent_unipotent = sp.expand(binary.subs({t: t + u * s}))
    tangent_unipotent_coefficients = tuple(
        sp.Poly(tangent_unipotent, s, t).coeff_monomial(
            s ** (10 - index) * t**index
        )
        for index in range(11)
    )
    tangent_unipotent_f9 = tangent_unipotent_coefficients[9]
    primitive_j2 = (
        2520 * f[0] * f[10]
        - 252 * f[1] * f[9]
        + 56 * f[2] * f[8]
        - 21 * f[3] * f[7]
        + 12 * f[4] * f[6]
        - 5 * f[5] ** 2
    )

    checks = {
        "q_tangent_diagonal_scale": sp.expand(
            q.subs({x: sigma**6 * x, y: sigma**3 * y, z: z})
            - sigma**6 * q
        )
        == 0,
        "q_secant_diagonal_scale": sp.expand(
            q.subs({x: tau**2 * x, y: tau * y, z: z}) - tau**2 * q
        )
        == 0,
        "tangent_residual_prefactor_one": tangent_factor == 1,
        "secant_residual_prefactor_one": secant_factor == 1,
        "tangent_coefficient_weights": all(
            sp.simplify(tangent_coefficients[index] - sigma ** tangent_weights[index] * f[index]) == 0
            for index in range(11)
        ),
        "secant_coefficient_weights": all(
            sp.simplify(secant_coefficients[index] - tau ** secant_weights[index] * f[index]) == 0
            for index in range(11)
        ),
        "tangent_left_chart_weights_nonzero": all(
            tangent_weights[index] != 0 for index in range(6)
        ),
        "secant_noncentral_left_chart_weights_nonzero": all(
            secant_weights[index] != 0 for index in range(5)
        ),
        "secant_central_weight_zero": secant_weights[5] == 0,
        "tangent_unipotent_f9_identity": sp.expand(
            tangent_unipotent_f9 - (f[9] + 10 * u * f[10])
        )
        == 0,
        "tangent_unipotent_j2_invariant": sp.expand(
            primitive_j2.subs(
                {
                    f[index]: tangent_unipotent_coefficients[index]
                    for index in range(11)
                },
                simultaneous=True,
            )
            - primitive_j2
        )
        == 0,
        "tangent_j2_weight_minus_two": sp.expand(
            primitive_j2.subs(
                {
                    f[index]: sigma ** tangent_weights[index] * f[index]
                    for index in range(11)
                },
                simultaneous=True,
            )
            - sigma**-2 * primitive_j2
        )
        == 0,
        "secant_j2_weight_zero": sp.expand(
            primitive_j2.subs(
                {
                    f[index]: tau ** secant_weights[index] * f[index]
                    for index in range(11)
                },
                simultaneous=True,
            )
            - primitive_j2
        )
        == 0,
        "tangent_first_nonzero_jet_identities": all(
            sp.expand(
                tangent_unipotent_coefficients[index - 1].subs(
                    {
                        f[higher]: 0
                        for higher in range(index + 1, 11)
                    }
                )
                - (f[index - 1] + index * u * f[index])
            )
            == 0
            for index in range(5, 11)
        ),
        "j2_forces_a_nonzero_upper_half_coefficient": sp.expand(
            primitive_j2.subs({f[index]: 0 for index in range(5, 11)})
        )
        == 0,
    }
    if not all(checks.values()):
        raise AssertionError(checks)

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-residual-orbit-torus-normalization-v1",
        "status": "PASS",
        "tangent": {
            "parameterization": "a=sigma^3, b=1, h_scale=sigma^-16",
            "coefficient_weights": list(tangent_weights),
            "safe_normalized_indices": list(range(6)),
            "j2_weight": -2,
            "global_j2_nonzero_gauge": "j2=1",
            "alternative_rational_gauge": "j2=-5",
            "r5_sign_normalization": "under j2=-5 and top_index=5, set f5=1",
        },
        "secant": {
            "parameterization": "a=tau, b=1, h_scale=tau^-5",
            "coefficient_weights": list(secant_weights),
            "safe_normalized_indices": list(range(5)),
            "unnormalized_central_index": 5,
            "j2_weight": 0,
        },
        "tangent_unipotent": {
            "substitution": "(s,t)->(s,t+u*s)",
            "f9_image": "f9+10*u*f10",
            "use_boundary": (
                "after the global tangent j2=1 gauge, split f10=0 from "
                "f10!=0; on the latter branch set f9=0"
            ),
            "exhaustive_first_nonzero_indices_under_j2_nonzero": list(
                range(5, 11)
            ),
        },
        "checks": checks,
        "source_sha256": {
            "scripts/certify_residual_orbit_torus.py": sha256(script_path),
        },
        "claim_boundary": (
            "normalization is an existence-preserving orbit reduction over "
            "an algebraic closure; it is not a chart-emptiness certificate"
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
