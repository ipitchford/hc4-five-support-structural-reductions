#!/usr/bin/env python3
"""Export the bounded degree-six Macaulay problem for the tangent r=5 slice."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from certify_j2_tangent_r5_rational_slice import SELECTED_INDICES, rational_slice


def sparse_terms(
    expression: sp.Expr, variables: tuple[sp.Symbol, ...]
) -> list[dict[str, object]]:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    terms: list[dict[str, object]] = []
    for exponents, coefficient in polynomial.terms():
        if coefficient.q != 1:
            raise AssertionError("the frozen r=5 system should have integer coefficients")
        terms.append({"exponents": list(exponents), "coefficient": int(coefficient)})
    return terms


def canonical_sha256(payload: object) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-degree6-system.json"),
    )
    arguments = parser.parse_args()

    equations, variables, substitutions = rational_slice()
    indexed = list(zip(SELECTED_INDICES, equations, strict=True))
    distinguished = dict(indexed)[36]
    if sp.Poly(distinguished, *variables).TC() != -1:
        raise AssertionError("the distinguished equation must have constant term -1")
    cubic = sp.expand(distinguished + 1)
    residual = [(index, expression) for index, expression in indexed if index != 36]
    if any(
        sp.Poly(expression, *variables).total_degree() > 3
        or sp.Poly(expression, *variables).TC() != 0
        for _, expression in residual
    ):
        raise AssertionError("the twelve residual equations must have degree at most three and no constant")
    if any(sum(exponents) != 3 for exponents, _ in sp.Poly(cubic, *variables).terms()):
        raise AssertionError("P must be a homogeneous cubic")

    core = {
        "schema": "hc4-decimic-j2-tangent-r5-degree6-system-v1",
        "orbit": "tangent",
        "top_index": 5,
        "gauge": "primitive_j2=-5",
        "substitutions": substitutions,
        "variables": [str(variable) for variable in variables],
        "selected_normal_equation_indices": list(SELECTED_INDICES),
        "distinguished_equation_index": 36,
        "residual_equations": [
            {"normal_equation_index": index, "terms": sparse_terms(expression, variables)}
            for index, expression in residual
        ],
        "P_terms": sparse_terms(cubic, variables),
        "target": "P^2",
        "certificate_implication": "1=sum(h_i*E_i)-(P+1)*(P-1)",
        "multiplier_maximum_degree": 3,
        "target_maximum_degree": 6,
    }
    script_path = Path(__file__).resolve()
    payload = {
        **core,
        "system_sha256": canonical_sha256(core),
        "source_sha256": {
            "scripts/export_j2_tangent_r5_degree6_system.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_r5_rational_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_r5_rational_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this file exports a finite exact linear membership problem; it is not "
            "a certificate until a rational solution is independently verified"
        ),
    }
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
