#!/usr/bin/env python3
"""Bounded projective-ratio scout for one third-colon multiplier block.

Ratios can cancel a block-wide scalar that makes absolute fixed-gauge
coordinates too tall.  This script completely enumerates strict-product EEA
candidates for q_j/q_ref over a declared coordinate interval and filters them
through independent modular selectors.  It does not reconstruct a QQ identity.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import sympy as sp

from probe_j2_secant_r10_third_colon_coordinate13_adaptive_crt import (
    canonical_hash,
    complete_strict_product_candidates,
    crt_pair,
    file_sha256,
)


def load_vector(path: Path) -> dict[str, object]:
    path = path.resolve()
    payload = json.loads(path.read_text(encoding="ascii"))
    prime = int(payload["characteristic"])
    if prime <= 5 or not sp.isprime(prime):
        raise ValueError(f"inadmissible characteristic: {path}")
    vector = list(map(int, payload["coordinate_vector"]))
    if len(vector) != 38048 or payload.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise ValueError(f"invalid coordinate vector: {path}")
    pivots = list(map(int, payload["pivot_unknown_indices"]))
    free = list(map(int, payload["free_unknown_indices"]))
    if (
        payload.get("pivot_unknown_indices_sha256") != canonical_hash(pivots)
        or payload.get("free_unknown_indices_sha256") != canonical_hash(free)
        or free != sorted(set(free))
        or len(set(pivots)) != len(pivots)
        or set(pivots) & set(free)
        or set(pivots) | set(free) != set(range(len(vector)))
    ):
        raise ValueError(f"invalid pivot/free partition: {path}")
    signature_keys = (
        "schema",
        "row_descriptor_sha256",
        "monomial_stream_sha256",
        "generator_stream_sha256",
        "target_sha256",
        "free_unknown_indices_sha256",
        "target_character_weight",
    )
    return {
        "path": path,
        "sha256": file_sha256(path),
        "characteristic": prime,
        "vector": [value % prime for value in vector],
        "free": free,
        "signature": {
            **{key: payload.get(key) for key in signature_keys},
            "pivot_unknown_set_sha256": canonical_hash(sorted(pivots)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--selector", type=Path, action="append", required=True)
    parser.add_argument("--reference", type=int, default=13)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=2229)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not 0 <= arguments.start < arguments.stop <= 38048:
        parser.error("invalid coordinate interval")
    if not arguments.start <= arguments.reference < arguments.stop:
        parser.error("reference must lie inside the coordinate interval")

    sources = [load_vector(path) for path in arguments.source]
    selectors = [load_vector(path) for path in arguments.selector]
    all_inputs = sources + selectors
    characteristics = [int(item["characteristic"]) for item in all_inputs]
    if len(set(characteristics)) != len(characteristics):
        raise ValueError("source and selector characteristics must be distinct")
    signatures = {canonical_hash(item["signature"]) for item in all_inputs}
    if len(signatures) != 1:
        raise ValueError("fixed-gauge problem signatures differ")
    free_lists = {canonical_hash(item["free"]) for item in all_inputs}
    if len(free_lists) != 1:
        raise ValueError("free-coordinate lists differ")
    for item in all_inputs:
        prime = int(item["characteristic"])
        if int(item["vector"][arguments.reference]) % prime == 0:
            raise ValueError("reference coordinate vanishes in an input field")

    source_modulus = math.prod(int(item["characteristic"]) for item in sources)
    records = []
    classifications = {
        "zero_in_every_input": 0,
        "unique_nonzero_ratio": 0,
        "no_candidate": 0,
        "ambiguous_candidates": 0,
    }
    informative_ratio_heights = []
    for coordinate in range(arguments.start, arguments.stop):
        observed_values = [int(item["vector"][coordinate]) for item in all_inputs]
        if not any(observed_values):
            classifications["zero_in_every_input"] += 1
            records.append(
                {
                    "coordinate": coordinate,
                    "classification": "zero_in_every_input",
                    "is_declared_free_coordinate": coordinate in sources[0]["free"],
                }
            )
            continue

        residue, modulus = 0, 1
        for source in sources:
            prime = int(source["characteristic"])
            ratio = (
                int(source["vector"][coordinate])
                * pow(int(source["vector"][arguments.reference]), -1, prime)
            ) % prime
            residue, modulus = crt_pair(residue, modulus, ratio, prime)
        if modulus != source_modulus:
            raise AssertionError("source modulus changed")
        candidates, steps = complete_strict_product_candidates(residue, modulus)
        survivors = list(candidates)
        selector_trace = []
        for selector in selectors:
            prime = int(selector["characteristic"])
            observed = (
                int(selector["vector"][coordinate])
                * pow(int(selector["vector"][arguments.reference]), -1, prime)
            ) % prime
            filtered = []
            for numerator, denominator in survivors:
                if denominator % prime == 0:
                    continue
                predicted = (
                    numerator * pow(denominator % prime, -1, prime)
                ) % prime
                if predicted == observed:
                    filtered.append((numerator, denominator))
            survivors = filtered
            selector_trace.append(
                {
                    "characteristic": prime,
                    "observed_ratio_residue": observed,
                    "survivor_count": len(survivors),
                }
            )

        if len(survivors) == 1:
            numerator, denominator = survivors[0]
            if numerator == 0:
                classification = "zero_in_every_input"
            else:
                classification = "unique_nonzero_ratio"
                informative_ratio_heights.append(
                    (2 * abs(numerator) * denominator).bit_length()
                )
            ratio_record = {
                "numerator": str(numerator),
                "denominator": str(denominator),
                "twice_product_bit_length": (
                    2 * abs(numerator) * denominator
                ).bit_length(),
            }
        elif not survivors:
            classification = "no_candidate"
            ratio_record = None
        else:
            classification = "ambiguous_candidates"
            ratio_record = None
        classifications[classification] += 1
        records.append(
            {
                "coordinate": coordinate,
                "classification": classification,
                "is_declared_free_coordinate": coordinate in sources[0]["free"],
                "complete_eea_step_count": steps,
                "strict_product_candidate_count": len(candidates),
                "selector_trace": selector_trace,
                "survivor_count_after_all_selectors": len(survivors),
                "unique_ratio": ratio_record,
            }
        )

    nonzero_tested = (arguments.stop - arguments.start) - classifications["zero_in_every_input"]
    projective_fraction = (
        classifications["unique_nonzero_ratio"] / nonzero_tested
        if nonzero_tested
        else 0.0
    )

    def input_record(item: dict[str, object]) -> dict[str, object]:
        return {
            "path": str(item["path"]),
            "sha256": item["sha256"],
            "characteristic": item["characteristic"],
        }

    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.third-colon-block-projective-ratio-scout.v1",
        "status": "PASS_BOUNDED_BLOCK_RATIO_CENSUS",
        "coordinate_interval": [arguments.start, arguments.stop],
        "reference_coordinate": arguments.reference,
        "coordinate_count": arguments.stop - arguments.start,
        "fixed_gauge_signature_sha256": next(iter(signatures)),
        "source_artifacts": [input_record(item) for item in sources],
        "selector_artifacts": [input_record(item) for item in selectors],
        "source_modulus": str(source_modulus),
        "source_modulus_bit_length": source_modulus.bit_length(),
        "classifications": classifications,
        "nonzero_coordinate_count_tested": nonzero_tested,
        "unique_nonzero_ratio_fraction": projective_fraction,
        "unique_nonzero_ratio_twice_product_bit_length_minimum": (
            min(informative_ratio_heights) if informative_ratio_heights else None
        ),
        "unique_nonzero_ratio_twice_product_bit_length_maximum": (
            max(informative_ratio_heights) if informative_ratio_heights else None
        ),
        "coordinate_records": records,
        "interpretation": (
            "A high unique-ratio fraction would support reconstructing this block "
            "projectively and solving for one block scalar. A low fraction rejects "
            "that bounded common-content route at the displayed modulus."
        ),
        "source_script": {
            "path": str(script_path),
            "sha256": file_sha256(script_path),
        },
        "claim_boundary": (
            "This is a bounded modular ratio census. A unique ratio is only a "
            "candidate until an exact QQ identity is reconstructed and convolved. "
            "No colon, saturation, secant-closure, or HC4 claim follows."
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
                "source_modulus_bit_length": source_modulus.bit_length(),
                "classifications": classifications,
                "nonzero_coordinate_count_tested": nonzero_tested,
                "unique_nonzero_ratio_fraction": projective_fraction,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
