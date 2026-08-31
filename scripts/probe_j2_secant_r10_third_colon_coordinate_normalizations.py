#!/usr/bin/env python3
"""Bounded structural rescaling scout for one third-colon coordinate.

This does not reconstruct a QQ identity.  It asks whether a fixed modular
coordinate becomes rationally reconstructible after any of a predeclared
finite family of exact basis changes.  Each scale is applied to every source
and selector residue before complete strict-product EEA enumeration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path

from probe_j2_secant_r10_third_colon_coordinate13_adaptive_crt import (
    canonical_hash,
    complete_strict_product_candidates,
    crt_pair,
    file_sha256,
    load_artifact,
)


COEFFICIENT_LCM = 154224
DIVIDED_POWER_FACTOR = 10
CLASSICAL_VARIABLE_FACTOR = 36000


def positive_divisors(value: int) -> list[int]:
    small = []
    large = []
    for divisor in range(1, math.isqrt(value) + 1):
        if value % divisor:
            continue
        small.append(divisor)
        if divisor * divisor != value:
            large.append(value // divisor)
    return small + list(reversed(large))


def structural_scales() -> list[Fraction]:
    """Freeze the exact v1 normalization family (995 reduced scales)."""

    scales = set()
    for divisor in positive_divisors(COEFFICIENT_LCM):
        for monomial_factor in (1, DIVIDED_POWER_FACTOR, CLASSICAL_VARIABLE_FACTOR):
            scales.update(
                {
                    Fraction(divisor * monomial_factor, 1),
                    Fraction(divisor, monomial_factor),
                    Fraction(monomial_factor, divisor),
                    Fraction(1, divisor * monomial_factor),
                }
            )
    return sorted(scales)


def scaled_residue(value: int, prime: int, scale: Fraction) -> int:
    if math.gcd(scale.denominator, prime) != 1:
        raise ValueError("normalization denominator is not a unit")
    return (
        value
        * (scale.numerator % prime)
        * pow(scale.denominator % prime, -1, prime)
    ) % prime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--selector", type=Path, action="append", required=True)
    parser.add_argument("--coordinate", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    sources = [load_artifact(path, arguments.coordinate) for path in arguments.source]
    selectors = [
        load_artifact(path, arguments.coordinate) for path in arguments.selector
    ]
    all_inputs = sources + selectors
    characteristics = [int(item["characteristic"]) for item in all_inputs]
    if len(set(characteristics)) != len(characteristics):
        raise ValueError("source and selector characteristics must be distinct")
    signatures = {canonical_hash(item["signature"]) for item in all_inputs}
    if len(signatures) != 1:
        raise ValueError("fixed-gauge problem signatures differ")
    vector_lengths = {int(item["coordinate_vector_length"]) for item in all_inputs}
    if vector_lengths != {38048}:
        raise ValueError("coordinate-vector length changed")

    residue, modulus = 0, 1
    for source in sources:
        residue, modulus = crt_pair(
            residue,
            modulus,
            int(source["coordinate_residue"]),
            int(source["characteristic"]),
        )

    scales = structural_scales()
    scale_stream = [
        [str(scale.numerator), str(scale.denominator)] for scale in scales
    ]
    records = []
    total_candidates = 0
    total_survivors = 0
    maximum_prefix_survivors = 0
    full_survivors = []
    for scale in scales:
        transformed = scaled_residue(residue, modulus, scale)
        candidates, steps = complete_strict_product_candidates(transformed, modulus)
        total_candidates += len(candidates)
        survivors = list(candidates)
        selector_trace = []
        for selector in selectors:
            prime = int(selector["characteristic"])
            observed = scaled_residue(
                int(selector["coordinate_residue"]), prime, scale
            )
            filtered = []
            for numerator, denominator in survivors:
                if denominator % prime == 0:
                    continue
                predicted = (
                    numerator
                    * pow(denominator % prime, -1, prime)
                ) % prime
                if predicted == observed:
                    filtered.append((numerator, denominator))
            survivors = filtered
            maximum_prefix_survivors = max(maximum_prefix_survivors, len(survivors))
            selector_trace.append(
                {
                    "characteristic": prime,
                    "transformed_observed_residue": observed,
                    "survivor_count": len(survivors),
                }
            )

        survivor_records = []
        for numerator, denominator in survivors:
            scaled_value = Fraction(numerator, denominator)
            original_value = scaled_value / scale
            checks = []
            for item in all_inputs:
                prime = int(item["characteristic"])
                if original_value.denominator % prime == 0:
                    passed = False
                    predicted = None
                else:
                    predicted = (
                        original_value.numerator
                        * pow(original_value.denominator % prime, -1, prime)
                    ) % prime
                    passed = predicted == int(item["coordinate_residue"])
                checks.append(
                    {
                        "characteristic": prime,
                        "predicted_original_residue": predicted,
                        "observed_original_residue": int(item["coordinate_residue"]),
                        "passed": passed,
                    }
                )
            if not all(item["passed"] for item in checks):
                raise AssertionError("survivor failed original-coordinate replay")
            survivor_records.append(
                {
                    "scaled_numerator": str(scaled_value.numerator),
                    "scaled_denominator": str(scaled_value.denominator),
                    "scaled_twice_product_bit_length": (
                        2 * abs(scaled_value.numerator) * scaled_value.denominator
                    ).bit_length(),
                    "original_numerator": str(original_value.numerator),
                    "original_denominator": str(original_value.denominator),
                    "original_twice_product_bit_length": (
                        2 * abs(original_value.numerator) * original_value.denominator
                    ).bit_length(),
                    "all_input_replays_pass": True,
                }
            )
        total_survivors += len(survivor_records)
        if survivor_records:
            full_survivors.append(
                {
                    "scale_numerator": str(scale.numerator),
                    "scale_denominator": str(scale.denominator),
                    "survivors": survivor_records,
                }
            )
        records.append(
            {
                "scale_numerator": str(scale.numerator),
                "scale_denominator": str(scale.denominator),
                "complete_eea_step_count": steps,
                "strict_product_candidate_count": len(candidates),
                "selector_trace": selector_trace,
                "survivor_count_after_all_selectors": len(survivors),
            }
        )

    def input_record(item: dict[str, object]) -> dict[str, object]:
        return {
            "path": str(item["path"]),
            "sha256": item["sha256"],
            "characteristic": item["characteristic"],
            "coordinate_residue": item["coordinate_residue"],
        }

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.third-colon-coordinate-structural-normalization-scout.v1",
        "status": (
            "PASS_BOUNDED_NO_STRUCTURAL_SCALE_SURVIVOR"
            if total_survivors == 0
            else "CANDIDATE_STRUCTURAL_SCALE_SURVIVOR_REQUIRES_EXACT_QQ_REPLAY"
        ),
        "coordinate": arguments.coordinate,
        "fixed_gauge_signature_sha256": next(iter(signatures)),
        "source_artifacts": [input_record(item) for item in sources],
        "selector_artifacts": [input_record(item) for item in selectors],
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "normalization_family": {
            "name": "structural-v1",
            "coefficient_lcm": COEFFICIENT_LCM,
            "coefficient_lcm_factorization": {"2": 4, "3": 4, "7": 1, "17": 1},
            "divided_power_factor": DIVIDED_POWER_FACTOR,
            "classical_variable_factor": CLASSICAL_VARIABLE_FACTOR,
            "construction": (
                "For every positive divisor d of 154224 and m in {1,10,36000}, "
                "test the reduced scales d*m, d/m, m/d, and 1/(d*m)."
            ),
            "scale_count": len(scales),
            "scale_stream_sha256": canonical_hash(scale_stream),
            "maximum_scale_numerator_or_denominator_bit_length": max(
                max(abs(scale.numerator).bit_length(), scale.denominator.bit_length())
                for scale in scales
            ),
        },
        "total_complete_candidates_across_scales": total_candidates,
        "maximum_selector_prefix_survivor_count": maximum_prefix_survivors,
        "total_survivors_after_all_selectors": total_survivors,
        "full_survivors": full_survivors,
        "scale_records": records,
        "conditional_height_conclusion": (
            "If one rational fixed-gauge coordinate reduces to every displayed "
            "source and selector residue, then for every declared scale s the "
            "reduced value s*q satisfies 2*abs(num(s*q))*den(s*q) >= M."
            if total_survivors == 0
            else None
        ),
        "source_script": {
            "path": str(script_path),
            "sha256": file_sha256(script_path),
        },
        "claim_boundary": (
            "This is a finite modular height scout for one coordinate. It neither "
            "proves nor disproves a QQ solution or polynomial identity, and it "
            "makes no colon, saturation, secant-closure, or HC4 claim."
        ),
    }
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "source_modulus_bit_length": modulus.bit_length(),
                "scale_count": len(scales),
                "total_complete_candidates_across_scales": total_candidates,
                "maximum_selector_prefix_survivor_count": maximum_prefix_survivors,
                "total_survivors_after_all_selectors": total_survivors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
