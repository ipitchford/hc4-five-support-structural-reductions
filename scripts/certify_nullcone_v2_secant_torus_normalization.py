#!/usr/bin/env python3
"""Certify the secant-torus normalization of the cubic V2 highest coordinate.

This is a structural lemma only.  It verifies directly from the frozen
normal-equation and cubic-covariant producers that the secant normal ideal is
graded by the residual-preserving torus and that the primitive V2 highest
coordinate has character one.  Consequently its nonzero locus is represented
without loss by the equation ``V2_highest = 1``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import q, x, y, z
from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations
from scout_five_support import cubic_monomials, g_coefficients, general_cubic
from scout_nullcone_cubic_families import raw_coefficient_family


CHARACTERISTIC = 101


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def monomial_weight(monomial: tuple[int, ...], weights: tuple[int, ...]) -> int:
    return sum(exponent * weight for exponent, weight in zip(monomial, weights))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v2-secant-torus-normalization.json"),
    )
    arguments = parser.parse_args()

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output

    target = sp.expand(raw_coefficient_family("V2"))
    target_polynomial = sp.Poly(target, *f_coefficients, domain=sp.ZZ)
    target_content = math.gcd(*(abs(int(value)) for value in target_polynomial.coeffs()))
    if target_content != 1:
        raise AssertionError("the V2 representative is not primitive integral")

    f_weights = tuple(5 - index for index in range(11))
    g_weights_list: list[int] = []
    cubic_weight_rows: list[dict[str, object]] = []
    for coefficient, monomial in zip(g_coefficients, cubic_monomials):
        exponent = sp.Poly(monomial, x, y, z).monoms()[0]
        x_degree, y_degree, _ = exponent
        # h' = tau^-5 h(tau^2*x,tau*y,z), while q acquires tau^2.
        weight = 2 * x_degree + y_degree - 3
        g_weights_list.append(weight)
        cubic_weight_rows.append(
            {
                "coefficient": str(coefficient),
                "monomial": str(monomial),
                "monomial_exponents_xyz": list(exponent),
                "coefficient_weight": weight,
            }
        )
    g_weights = tuple(g_weights_list)

    tau = sp.Symbol("tau", nonzero=True)
    variable_substitution = {
        x: tau**2 * x,
        y: tau * y,
        z: z,
    }
    correction_lhs = sp.expand(
        tau**-5
        * (q * general_cubic).subs(variable_substitution, simultaneous=True)
    )
    correction_rhs = sp.expand(
        q
        * general_cubic.subs(
            {
                coefficient: tau**weight * coefficient
                for coefficient, weight in zip(g_coefficients, g_weights)
            },
            simultaneous=True,
        )
    )
    if sp.expand(correction_lhs - correction_rhs) != 0:
        raise AssertionError("the derived correction-coefficient weights are wrong")

    variables = f_coefficients + g_coefficients
    weights = f_weights + g_weights
    equations, equation_build_seconds = normal_equations("secant")
    equation_characters: list[int] = []
    equation_term_counts: list[int] = []
    for index, equation in enumerate(equations):
        polynomial = sp.Poly(equation, *variables)
        characters = {
            monomial_weight(monomial, weights)
            for monomial, _ in polynomial.terms()
        }
        if len(characters) != 1:
            raise AssertionError(
                f"normal equation {index} is not secant-torus homogeneous: {characters}"
            )
        equation_characters.append(next(iter(characters)))
        equation_term_counts.append(len(polynomial.terms()))

    target_characters = {
        monomial_weight(monomial, f_weights)
        for monomial, _ in target_polynomial.terms()
    }
    if target_characters != {1}:
        raise AssertionError(f"expected V2 highest character one, got {target_characters}")
    transformed_target = sp.expand(
        target.subs(
            {
                coefficient: tau**weight * coefficient
                for coefficient, weight in zip(f_coefficients, f_weights)
            },
            simultaneous=True,
        )
    )
    if sp.expand(transformed_target - tau * target) != 0:
        raise AssertionError("the direct V2 torus transformation identity failed")

    target_mod_p = sp.Poly(target, *f_coefficients, modulus=CHARACTERISTIC)
    target_mod_p_term_count = len(target_mod_p.terms())
    if target_mod_p_term_count != len(target_polynomial.terms()):
        raise AssertionError("V2 support drops in characteristic 101")

    residual_torus_path = campaign / "receipts/residual-orbit-torus.json"
    residual_torus = json.loads(residual_torus_path.read_text(encoding="utf-8"))
    if residual_torus.get("status") != "PASS":
        raise AssertionError("the frozen residual-torus receipt is not passing")

    character_payload = json.dumps(
        {
            "f_weights": f_weights,
            "g_weights": g_weights,
            "equation_characters": equation_characters,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    result = {
        "schema": "hc4.decimic-nullcone-v2-secant-torus-normalization.v1",
        "status": "PASS_EXACT_SECANT_V2_HIGHEST_TORUS_NORMALIZATION",
        "orbit": "secant",
        "torus_parameterization": "a=tau, b=1, h_scale=tau^-5",
        "field_scope": (
            "every field in which the primitive V2 polynomial is defined; because "
            "the character is one, target!=0 is normalized by tau=target^-1 "
            "without adjoining a root"
        ),
        "f_coefficient_weights": list(f_weights),
        "g_correction_weights": list(g_weights),
        "cubic_correction_weight_rows": cubic_weight_rows,
        "normal_equation_count": len(equations),
        "normal_equation_term_counts": equation_term_counts,
        "normal_equation_characters": equation_characters,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "weight_audit_sha256": hashlib.sha256(character_payload).hexdigest(),
        "target": str(target),
        "target_term_count": len(target_polynomial.terms()),
        "target_integer_content": target_content,
        "target_character": 1,
        "target_transformation": "V2_highest -> tau*V2_highest",
        "target_sha256": digest((target,)),
        "characteristic_101": {
            "full_support": True,
            "term_count": target_mod_p_term_count,
        },
        "normalization_equivalence": (
            "V(I_secant) intersect D(V2_highest) is nonempty iff "
            "V(I_secant,V2_highest-1) is nonempty"
        ),
        "checks": {
            "primitive_integral_target": True,
            "correction_action_exact": True,
            "all_55_normal_equations_weight_homogeneous": True,
            "target_character_one": True,
            "direct_target_transformation_exact": True,
            "characteristic_101_full_target_support": True,
            "frozen_residual_torus_receipt_pass": True,
        },
        "equation_build_seconds": equation_build_seconds,
        "source_sha256": {
            "scripts/certify_nullcone_v2_secant_torus_normalization.py": sha256(script_path),
            "scripts/scout_nullcone_cubic_families.py": sha256(
                script_path.parent / "scout_nullcone_cubic_families.py"
            ),
            "scripts/identify_decimic_nullcone_cubic_covariants.py": sha256(
                script_path.parent / "identify_decimic_nullcone_cubic_covariants.py"
            ),
            "scripts/scout_decimic_nullcone_hsop.py": sha256(
                script_path.parent / "scout_decimic_nullcone_hsop.py"
            ),
            "scripts/scout_five_support.py": sha256(
                script_path.parent / "scout_five_support.py"
            ),
            "receipts/residual-orbit-torus.json": sha256(residual_torus_path),
        },
        "claim_boundary": (
            "This exact receipt proves only a branch-safe torus normalization of "
            "the nonzero V2 highest-coordinate locus. It does not prove that the "
            "normalized ideal is empty, prove the other V2 coordinates, establish "
            "secant nullcone containment, lift to the polynomial problem, or prove HC4."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
