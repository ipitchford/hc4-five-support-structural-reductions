#!/usr/bin/env -S sage -python
"""Independent direct-polynomial audit of the 16 reconstructed source syzygies."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp

import build_p173_fourth_colon_integral_lift_system as base


SELECTED_GLOBAL = (46, 47, 57, 66, 68, 102, 155, 547,
                   763, 965, 966, 1261, 1269, 1499, 1699, 1711)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()

    candidate_document = json.loads(arguments.candidates.read_text(encoding="ascii"))
    base.require(candidate_document.get("selected_global_coordinates") == list(SELECTED_GLOBAL),
                 "candidate selection drift")
    certificate = json.loads(base.MODULAR_CERTIFICATE.read_text(encoding="ascii"))
    pivots = [int(value) for value in certificate["pivot_unknown_indices"]]
    base.require(len(pivots) == base.LOCAL_COLUMNS, "pivot dimension drift")

    equations, variables, _leading, _open_factor = base.homogeneous_saturation_system()
    first, _ = base.reconstruct_quartic(base.CAMPAIGN, variables)
    second, _ = base.load_second_quartic(base.CAMPAIGN, variables)
    third, _ = base.load_third_quartic(base.CAMPAIGN, variables)
    generators = list(equations) + [first, second, third]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]

    weights = []
    for generator in generators:
        terms = sp.Poly(generator, *variables, domain=sp.QQ).terms()
        observed = {base.character_weight(tuple(map(int, exponents)))
                    for exponents, _coefficient in terms}
        base.require(len(observed) == 1, "generator character drift")
        weights.append(next(iter(observed)))
    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in base.exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, base.character_weight(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (weight, degree) in enumerate(zip(weights, multiplier_degrees, strict=True)):
        multiplier_weight = (2 - weight) % base.CHARACTER_MODULUS
        descriptors.extend((generator_index, multiplier)
                           for multiplier in pools.get((degree, multiplier_weight), []))
    descriptor_hash = base.canonical_hash(descriptors)
    base.require(descriptor_hash == base.EXPECTED_HASHES["descriptor"], "descriptor hash drift")

    coefficients = [dict() for _ in SELECTED_GLOBAL]
    for entry in candidate_document["entries"]:
        column = int(entry["column"])
        local = int(entry["pivot_coordinate"])
        base.require(0 <= column < len(SELECTED_GLOBAL) and 0 <= local < len(pivots),
                     "candidate coordinate out of range")
        global_coordinate = pivots[local]
        base.require(global_coordinate not in coefficients[column], "duplicate candidate coordinate")
        coefficients[column][global_coordinate] = Fraction(int(entry["numerator"]),
                                                            int(entry["denominator"]))

    polynomial_mismatches = 0
    residual_term_counts = []
    support = []
    for column, selected_coordinate in enumerate(SELECTED_GLOBAL):
        combination = sp.Integer(0)
        column_coefficients = dict(coefficients[column])
        base.require(selected_coordinate not in column_coefficients, "pivot/free overlap")
        column_coefficients[selected_coordinate] = Fraction(1)
        support.append(len(column_coefficients))
        for global_coordinate, coefficient in column_coefficients.items():
            generator_index, exponents = descriptors[global_coordinate]
            multiplier = sp.prod(variable ** exponent
                                 for variable, exponent in zip(variables, exponents, strict=True))
            combination += sp.Rational(coefficient.numerator, coefficient.denominator) * multiplier * generators[generator_index]
        polynomial = sp.Poly(sp.expand(combination), *variables, domain=sp.QQ)
        term_count = len(polynomial.terms()) if not polynomial.is_zero else 0
        residual_term_counts.append(term_count)
        polynomial_mismatches += not polynomial.is_zero

    base.require(polynomial_mismatches == 0, "direct polynomial syzygy audit failed")
    result = {
        "schema": "hc4.fourth-colon-c16-direct-polynomial-audit.v1",
        "status": "PASS_INDEPENDENT_DIRECT_POLYNOMIAL_C16_RATIONAL_SYZYGIES",
        "selected_global_coordinates": list(SELECTED_GLOBAL),
        "checks": {"descriptor_sha256": descriptor_hash,
                   "source_syzygies": len(SELECTED_GLOBAL),
                   "coefficient_support_including_free_unit": support,
                   "residual_term_counts": residual_term_counts,
                   "polynomial_mismatches": polynomial_mismatches},
        "inputs": {"rational_candidates": sha256(arguments.candidates),
                   "modular_certificate": sha256(base.MODULAR_CERTIFICATE)},
        "producer": {"path": str(Path(__file__).relative_to(base.CAMPAIGN)),
                     "sha256": sha256(Path(__file__))},
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "claim_boundary": "Sixteen exact rational source-module syzygies in the frozen fourth character block; no h4 target membership, colon equality, saturation, secant-orbit closure, full nullcone closure, quartic Hessian conjecture, or Jacobian conjecture follows.",
    }
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": result["status"], "receipt": str(arguments.output),
                      "sha256": sha256(arguments.output), "checks": result["checks"],
                      "resources": result["resources"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
