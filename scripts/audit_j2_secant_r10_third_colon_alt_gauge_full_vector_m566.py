#!/usr/bin/env python3
"""Census the full p181-gauge multiplier vector at the frozen M566 gate.

The nineteen source primes define a 566-bit CRT modulus.  The three small
selectors and the reserved large validator are deliberately excluded from
that modulus and are used only to reject strict-product candidates.  This is
a bounded gauge-height audit; it does not reconstruct a QQ identity.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import time
from pathlib import Path

from probe_j2_secant_r10_third_colon_coordinate13_adaptive_crt import (
    canonical_hash,
    complete_strict_product_candidates,
)


CAMPAIGN = Path(__file__).resolve().parent.parent
CHECKPOINT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-coordinate13-adaptive-crt-"
    "alt-p181-gauge-m566-predeclared-checkpoint.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-alt-p181-gauge-full-vector-"
    "m566-census.json"
)
EXPECTED_SOURCE_COUNT = 19
EXPECTED_SOURCE_BITS = 566
EXPECTED_SELECTORS = [173, 197, 199, 2147483549]
GAUGE_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def load_vector(record: dict[str, object]) -> dict[str, object]:
    path = Path(str(record["path"])).resolve()
    observed_hash = file_sha256(path)
    if observed_hash != record["sha256"]:
        raise ValueError(f"artifact hash mismatch: {path}")
    payload = json.loads(path.read_text(encoding="ascii"))
    characteristic = int(payload["characteristic"])
    if characteristic != int(record["characteristic"]):
        raise ValueError(f"characteristic mismatch: {path}")
    vector = list(map(int, payload["coordinate_vector"]))
    if payload.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise ValueError(f"coordinate-vector hash mismatch: {path}")
    pivots = list(map(int, payload["pivot_unknown_indices"]))
    free = list(map(int, payload["free_unknown_indices"]))
    if payload.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise ValueError(f"ordered-pivot hash mismatch: {path}")
    if payload.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise ValueError(f"free-coordinate hash mismatch: {path}")
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != set(range(len(vector)))
    ):
        raise ValueError(f"invalid pivot/free partition: {path}")
    signature = {
        key: payload.get(key)
        for key in (
            "schema",
            "row_descriptor_sha256",
            "monomial_stream_sha256",
            "generator_stream_sha256",
            "target_sha256",
            "free_unknown_indices_sha256",
            "target_character_weight",
        )
    }
    signature["pivot_unknown_set_sha256"] = canonical_hash(sorted(pivots))
    return {
        "path": str(path),
        "sha256": observed_hash,
        "characteristic": characteristic,
        "vector": vector,
        "signature": signature,
    }


def main() -> int:
    started = time.perf_counter()
    checkpoint_hash = file_sha256(CHECKPOINT)
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    sources = [load_vector(record) for record in checkpoint["source_artifacts"]]
    selectors = [
        load_vector(record) for record in checkpoint["selector_artifacts"]
    ]
    if len(sources) != EXPECTED_SOURCE_COUNT:
        raise ValueError("unexpected M566 source count")
    if [item["characteristic"] for item in selectors] != EXPECTED_SELECTORS:
        raise ValueError("selector/validator order changed")
    all_inputs = sources + selectors
    characteristics = [int(item["characteristic"]) for item in all_inputs]
    if len(set(characteristics)) != len(characteristics):
        raise ValueError("source and selector primes overlap")
    signatures = {canonical_hash(item["signature"]) for item in all_inputs}
    if len(signatures) != 1:
        raise ValueError("fixed-gauge problem signatures differ")
    coordinate_lengths = {len(item["vector"]) for item in all_inputs}
    if len(coordinate_lengths) != 1:
        raise ValueError("coordinate-vector lengths differ")
    coordinate_count = coordinate_lengths.pop()

    modulus = math.prod(int(item["characteristic"]) for item in sources)
    if modulus.bit_length() != EXPECTED_SOURCE_BITS:
        raise ValueError("source modulus left the frozen M566 gate")
    if str(modulus) != checkpoint["source_modulus"]:
        raise ValueError("source modulus disagrees with the checkpoint")
    crt_weights = []
    for item in sources:
        prime = int(item["characteristic"])
        cofactor = modulus // prime
        crt_weights.append(cofactor * pow(cofactor % prime, -1, prime))

    outcome = collections.Counter()
    coordinate_lists: dict[str, list[int]] = collections.defaultdict(list)
    candidate_count_histogram = collections.Counter()
    nonzero_product_height_histogram = collections.Counter()
    maximum_unique_nonzero_profile = None
    total_eea_steps = 0

    for coordinate in range(coordinate_count):
        source_residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        if not any(source_residues):
            candidates = [(0, 1)]
            eea_steps = 0
        else:
            combined = sum(
                residue * weight
                for residue, weight in zip(
                    source_residues, crt_weights, strict=True
                )
            ) % modulus
            candidates, eea_steps = complete_strict_product_candidates(
                combined, modulus
            )
        total_eea_steps += eea_steps
        candidate_count_histogram[len(candidates)] += 1

        survivors = list(candidates)
        for selector in selectors:
            prime = int(selector["characteristic"])
            observed = int(selector["vector"][coordinate]) % prime
            survivors = [
                (numerator, denominator)
                for numerator, denominator in survivors
                if denominator % prime
                and numerator % prime * pow(denominator % prime, -1, prime)
                % prime
                == observed
            ]

        if not survivors:
            label = "no_candidate"
        elif len(survivors) > 1:
            label = "ambiguous"
        else:
            numerator, denominator = survivors[0]
            label = "unique_zero" if numerator == 0 else "unique_nonzero"
            if numerator:
                product_bits = (2 * abs(numerator) * denominator).bit_length()
                nonzero_product_height_histogram[product_bits] += 1
                profile = (
                    product_bits,
                    abs(numerator).bit_length(),
                    denominator.bit_length(),
                    coordinate,
                )
                if (
                    maximum_unique_nonzero_profile is None
                    or profile > maximum_unique_nonzero_profile
                ):
                    maximum_unique_nonzero_profile = profile
        outcome[label] += 1
        coordinate_lists[label].append(coordinate)

    maximum_record = None
    if maximum_unique_nonzero_profile is not None:
        product_bits, numerator_bits, denominator_bits, coordinate = (
            maximum_unique_nonzero_profile
        )
        maximum_record = {
            "coordinate": coordinate,
            "twice_product_bit_length": product_bits,
            "numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }

    gauge_source = next(
        item for item in sources if int(item["characteristic"]) == 181
    )
    gauge_payload = json.loads(
        Path(str(gauge_source["path"])).read_text(encoding="ascii")
    )
    gauge_receipt_hash = file_sha256(GAUGE_RECEIPT)
    gauge_receipt = json.loads(GAUGE_RECEIPT.read_text(encoding="utf-8"))
    dense_handoff = gauge_receipt["solver"]["hybrid_dense_handoff"]
    dense_pivot_count = int(dense_handoff["dense_pivot_count"])
    ordered_pivots = list(map(int, gauge_payload["pivot_unknown_indices"]))
    free_coordinates = set(map(int, gauge_payload["free_unknown_indices"]))
    dense_pivots = set(ordered_pivots[-dense_pivot_count:])
    early_sparse_pivots = set(ordered_pivots[:-dense_pivot_count])
    if (
        dense_pivots & early_sparse_pivots
        or dense_pivots & free_coordinates
        or early_sparse_pivots & free_coordinates
        or dense_pivots | early_sparse_pivots | free_coordinates
        != set(range(coordinate_count))
    ):
        raise ValueError("gauge elimination regions do not partition coordinates")
    outcome_sets = {
        key: set(value) for key, value in coordinate_lists.items()
    }
    elimination_regions = {
        "early_sparse_pivots": early_sparse_pivots,
        "dense_handoff_pivots": dense_pivots,
        "free_coordinates": free_coordinates,
    }
    elimination_cross_tab = {
        region: {
            "coordinate_count": len(indices),
            "outcome": {
                label: len(indices & outcome_indices)
                for label, outcome_indices in sorted(outcome_sets.items())
            },
        }
        for region, indices in elimination_regions.items()
    }
    if len(dense_pivots & outcome_sets["no_candidate"]) != dense_pivot_count:
        raise ValueError("not every dense-handoff pivot fails the M566 gate")
    if free_coordinates != outcome_sets["unique_zero"] & free_coordinates:
        raise ValueError("a frozen free coordinate is not uniquely zero")

    result = {
        "schema": "hc4.third-colon-alt-gauge-full-vector-m566-census.v1",
        "status": "PASS_BOUNDED_FULL_VECTOR_HEIGHT_CENSUS",
        "method": (
            "complete strict-product continued-fraction candidates over the "
            "nineteen-source M566 modulus, sequentially filtered by p=173, "
            "p=197, p=199, and the reserved large validator"
        ),
        "coordinate_count": coordinate_count,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "fixed_gauge_signature_sha256": next(iter(signatures)),
        "source_characteristics": [item["characteristic"] for item in sources],
        "selector_characteristics": [
            item["characteristic"] for item in selectors
        ],
        "outcome": dict(sorted(outcome.items())),
        "coordinates_by_outcome": {
            key: value for key, value in sorted(coordinate_lists.items())
        },
        "candidate_count_histogram": {
            str(key): value
            for key, value in sorted(candidate_count_histogram.items())
        },
        "complete_eea_step_count_total": total_eea_steps,
        "unique_nonzero_product_bit_length_histogram": {
            str(key): value
            for key, value in sorted(nonzero_product_height_histogram.items())
        },
        "maximum_unique_nonzero_profile": maximum_record,
        "elimination_provenance": {
            "gauge_receipt": str(GAUGE_RECEIPT),
            "gauge_receipt_sha256": gauge_receipt_hash,
            "dense_handoff": dense_handoff,
            "cross_tab": elimination_cross_tab,
            "certified_observation": (
                "All 581 dense-handoff pivots fail the M566 reconstruction "
                "gate; their back-substitution reaches 19,181 earlier sparse "
                "pivots, while all 2,167 frozen free coordinates are uniquely "
                "zero in the bounded census."
            ),
        },
        "inputs": {
            "checkpoint": str(CHECKPOINT),
            "checkpoint_sha256": checkpoint_hash,
            "source_artifacts": [
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "characteristic": item["characteristic"],
                }
                for item in sources
            ],
            "selector_artifacts": [
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "characteristic": item["characteristic"],
                }
                for item in selectors
            ],
        },
        "source_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "wall_seconds": time.perf_counter() - started,
        "completeness_statement": (
            "For each coordinate, every reduced n/d with d>0, gcd(d,M)=1, "
            "n=r*d mod M, and 2*abs(n)*d<M occurs among the enumerated "
            "continued-fraction candidates by Legendre's theorem."
        ),
        "claim_boundary": (
            "This is a bounded coefficient-height census for one fixed-free "
            "gauge. Unique candidates are not a QQ polynomial identity. No "
            "colon, saturation, secant, nullcone, or HC4 claim follows."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT),
                "source_modulus_bit_length": result[
                    "source_modulus_bit_length"
                ],
                "coordinate_count": coordinate_count,
                "outcome": result["outcome"],
                "maximum_unique_nonzero_profile": maximum_record,
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
