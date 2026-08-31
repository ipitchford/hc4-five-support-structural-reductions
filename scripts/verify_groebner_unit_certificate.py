#!/usr/bin/env python3
"""Independently replay a sparse Groebner.jl unit certificate in SymPy."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp


def sparse_polynomial(
    terms: list[dict[str, object]], variables: tuple[sp.Symbol, ...]
) -> sp.Poly:
    expression = sp.Integer(0)
    for term in terms:
        coefficient = sp.Rational(int(term["numerator"]), int(term["denominator"]))
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, term["exponents"], strict=True):
            monomial *= variable ** int(exponent)
        expression += coefficient * monomial
    return sp.Poly(expression, *variables, domain=sp.QQ)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    input_path = arguments.input.resolve()
    certificate_path = arguments.certificate.resolve()
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))

    input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
    if certificate["input_sha256"] != input_sha256:
        raise AssertionError("certificate input hash does not match the supplied input")
    if certificate["chart"] != input_data["chart"]:
        raise AssertionError("chart mismatch")
    if certificate["branch"] != input_data["branch"]:
        raise AssertionError("branch mismatch")
    variables = tuple(sp.symbols(input_data["variable_names"]))
    generators = [
        sparse_polynomial(terms, variables) for terms in input_data["equations"]
    ]
    multipliers = [
        sparse_polynomial(terms, variables)
        for terms in certificate["unit_multiplier_terms"]
    ]
    if len(generators) != len(multipliers):
        raise AssertionError("the multiplier row has the wrong length")

    reconstruction = sp.Poly(0, *variables, domain=sp.QQ)
    for multiplier, generator in zip(multipliers, generators, strict=True):
        reconstruction += multiplier * generator
    exact_unit = reconstruction == sp.Poly(1, *variables, domain=sp.QQ)
    if not exact_unit:
        raise AssertionError("the serialized multiplier row does not reconstruct 1")

    script_path = Path(__file__).resolve()
    result = {
        "schema": "independent-sympy-groebner-unit-replay-v1",
        "status": "PASS_INDEPENDENT_EXACT_UNIT_REPLAY",
        "input_path": str(input_path),
        "input_sha256": input_sha256,
        "certificate_path": str(certificate_path),
        "certificate_sha256": hashlib.sha256(certificate_path.read_bytes()).hexdigest(),
        "chart": input_data["chart"],
        "branch": input_data["branch"],
        "variable_count": len(variables),
        "generator_count": len(generators),
        "retained_generator_indices": input_data["retained_generator_indices"],
        "multiplier_nonzero_count": sum(not multiplier.is_zero for multiplier in multipliers),
        "multiplier_term_count": sum(len(multiplier.terms()) for multiplier in multipliers),
        "maximum_multiplier_total_degree": max(
            multiplier.total_degree() for multiplier in multipliers if not multiplier.is_zero
        ),
        "exact_reconstruction": "1",
        "wall_seconds": time.perf_counter() - started,
        "sympy_version": sp.__version__,
        "source_sha256": {
            "scripts/verify_groebner_unit_certificate.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest()
        },
        "claim_boundary": (
            "This independently replays one exact serialized Bezout identity.  "
            "It does not establish coverage of any other chart or branch."
        ),
    }
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
