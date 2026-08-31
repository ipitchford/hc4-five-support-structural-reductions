#!/usr/bin/env python3
"""Independently verify the Sage degree-six r=5 certificate with SymPy."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_r5_rational_slice import SELECTED_INDICES, rational_slice
from export_j2_tangent_r5_degree6_system import canonical_sha256, sparse_terms


def from_terms(terms, variables: tuple[sp.Symbol, ...]) -> sp.Expr:
    expression = sp.Integer(0)
    for term in terms:
        coefficient_data = term["coefficient"]
        if isinstance(coefficient_data, dict):
            coefficient = sp.Rational(
                coefficient_data["numerator"], coefficient_data["denominator"]
            )
        else:
            coefficient = sp.Integer(coefficient_data)
        monomial = sp.prod(
            variable ** exponent for variable, exponent in zip(variables, term["exponents"])
        )
        expression += coefficient * monomial
    return sp.expand(expression)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", type=Path, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()

    system_bytes = arguments.system.read_bytes()
    certificate_bytes = arguments.certificate.read_bytes()
    system = json.loads(system_bytes)
    certificate = json.loads(certificate_bytes)
    if certificate["status"] != "PASS_EXACT_RATIONAL_CERTIFICATE":
        raise SystemExit("the supplied artifact is not an exact rational certificate")

    equations, variables, substitutions = rational_slice()
    indexed = dict(zip(SELECTED_INDICES, equations, strict=True))
    if system["variables"] != [str(variable) for variable in variables]:
        raise AssertionError("system variables do not match the independent reconstruction")
    reconstructed_core = {key: value for key, value in system.items() if key not in {
        "system_sha256", "source_sha256", "claim_boundary"
    }}
    if canonical_sha256(reconstructed_core) != system["system_sha256"]:
        raise AssertionError("system payload hash does not verify")
    if certificate["system_sha256"] != system["system_sha256"]:
        raise AssertionError("certificate targets a different system")

    P = sp.expand(indexed[36] + 1)
    if sparse_terms(P, variables) != system["P_terms"]:
        raise AssertionError("exported P differs from the independent reconstruction")
    for entry in system["residual_equations"]:
        index = entry["normal_equation_index"]
        if sparse_terms(indexed[index], variables) != entry["terms"]:
            raise AssertionError(f"exported equation {index} differs from reconstruction")

    multiplier_by_index = {
        entry["normal_equation_index"]: from_terms(entry["terms"], variables)
        for entry in certificate["multipliers"]
    }
    membership = sp.expand(
        sum(multiplier_by_index[index] * indexed[index] for index in multiplier_by_index)
        - P**2
    )
    if membership != 0:
        raise AssertionError("degree-six membership identity failed")
    unit_identity = sp.expand(
        sum(multiplier_by_index[index] * indexed[index] for index in multiplier_by_index)
        - (P + 1) * indexed[36]
        - 1
    )
    if unit_identity != 0:
        raise AssertionError("derived unit identity failed")

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4-decimic-j2-tangent-r5-degree6-verification-v1",
        "status": "PASS_INDEPENDENT_EXACT_IDENTITY",
        "orbit": "tangent",
        "top_index": 5,
        "substitutions": substitutions,
        "system_sha256": system["system_sha256"],
        "system_file_sha256": hashlib.sha256(system_bytes).hexdigest(),
        "certificate_file_sha256": hashlib.sha256(certificate_bytes).hexdigest(),
        "verified_membership_identity": "P^2=sum(h_i*E_i)",
        "verified_unit_identity": "1=sum(h_i*E_i)-(P+1)*E36",
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/verify_j2_tangent_r5_degree6_certificate.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_r5_rational_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_r5_rational_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this closes the rational tangent r=5 slice only; the equivalence to "
            "the full localized r=5 stratum and all other tangent/secant strata "
            "must be audited separately"
        ),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
