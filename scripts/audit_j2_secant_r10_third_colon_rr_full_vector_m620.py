#!/usr/bin/env python3
"""Audit the full third-colon gauge vector at a 620-bit source modulus.

Twenty large source primes define the CRT modulus.  The three small primes
173, 197, and 199 are used only as selectors.  Their product is large enough
that random survival among roughly 260 continued-fraction candidates per
coordinate is negligible, while retaining a clean 620-bit source-height gate.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import time
from pathlib import Path

from audit_j2_secant_r10_third_colon_rr_coordinate13 import (
    file_sha256,
    matches,
    strict_product_candidates,
)


CAMPAIGN = Path(__file__).resolve().parent.parent
DIAGNOSTIC = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-qq-reconstruction-"
    "asymmetric-m512-diagnostic.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-rr-full-vector-m620-audit.json"
)
SMALL_PRIMES = {173, 197, 199}


def load_artifact(record: dict[str, object]) -> dict[str, object]:
    path = Path(str(record["path"]))
    expected = record.get("sha256")
    observed = file_sha256(path)
    if expected is not None and expected != observed:
        raise ValueError(f"artifact hash mismatch: {path}")
    payload = json.loads(path.read_text(encoding="ascii"))
    prime = int(record["characteristic"])
    if int(payload["characteristic"]) != prime:
        raise ValueError(f"characteristic mismatch: {path}")
    vector = list(map(int, payload["coordinate_vector"]))
    return {
        "characteristic": prime,
        "path": path,
        "sha256": observed,
        "vector": vector,
    }


def main() -> int:
    started = time.perf_counter()
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    records = (
        diagnostic["input_certificates"]
        + diagnostic["selection_heldout_certificates"]
        + diagnostic["heldout_certificates"]
    )
    for prime in (2147483171, 2147483137):
        path = CAMPAIGN / "artifacts" / (
            f"j2-secant-r10-third-colon-identity-fixed-free-p{prime}.json"
        )
        records.append(
            {
                "path": str(path),
                "sha256": file_sha256(path),
                "characteristic": prime,
            }
        )
    artifacts = [load_artifact(record) for record in records]
    lengths = {len(item["vector"]) for item in artifacts}
    if len(lengths) != 1:
        raise ValueError("coordinate-vector lengths differ")

    sources = [
        item for item in artifacts if item["characteristic"] not in SMALL_PRIMES
    ]
    selectors = [
        item for item in artifacts if item["characteristic"] in SMALL_PRIMES
    ]
    if len(sources) != 20 or {item["characteristic"] for item in selectors} != SMALL_PRIMES:
        raise ValueError("unexpected source/selector partition")
    modulus = math.prod(int(item["characteristic"]) for item in sources)
    crt_weights = []
    for item in sources:
        prime = int(item["characteristic"])
        cofactor = modulus // prime
        crt_weights.append(cofactor * pow(cofactor % prime, -1, prime))

    outcome = collections.Counter()
    nonzero_height_histogram = collections.Counter()
    candidate_count_histogram = collections.Counter()
    maximum_profile = None
    coordinate_count = lengths.pop()
    for coordinate in range(coordinate_count):
        if all(
            int(item["vector"][coordinate]) % int(item["characteristic"]) == 0
            for item in sources
        ):
            candidates = [(0, 1)]
        else:
            residue = sum(
                (int(item["vector"][coordinate]) % int(item["characteristic"]))
                * weight
                for item, weight in zip(sources, crt_weights, strict=True)
            ) % modulus
            candidates = strict_product_candidates(residue, modulus)
        candidate_count_histogram[len(candidates)] += 1
        survivors = [
            candidate
            for candidate in candidates
            if all(
                matches(
                    candidate,
                    int(item["vector"][coordinate]) % int(item["characteristic"]),
                    int(item["characteristic"]),
                )
                for item in selectors
            )
        ]
        if not survivors:
            outcome["no_candidate"] += 1
        elif len(survivors) > 1:
            outcome["ambiguous"] += 1
        else:
            numerator, denominator = survivors[0]
            if numerator == 0:
                outcome["unique_zero"] += 1
            else:
                outcome["unique_nonzero"] += 1
                product_bits = (2 * abs(numerator) * denominator).bit_length()
                nonzero_height_histogram[product_bits] += 1
                profile = (
                    product_bits,
                    abs(numerator).bit_length(),
                    denominator.bit_length(),
                    coordinate,
                )
                if maximum_profile is None or profile > maximum_profile:
                    maximum_profile = profile

    result = {
        "schema": "hc4.third-colon-full-vector-m620-rr-audit.v1",
        "status": "PASS_BOUNDED_FULL_VECTOR_HEIGHT_CENSUS",
        "method": (
            "complete strict-product continued-fraction candidates over the "
            "20-large-prime CRT modulus, filtered by p=173,197,199"
        ),
        "coordinate_count": coordinate_count,
        "source_modulus_bit_length": modulus.bit_length(),
        "source_characteristics": [item["characteristic"] for item in sources],
        "selector_characteristics": [item["characteristic"] for item in selectors],
        "outcome": dict(sorted(outcome.items())),
        "candidate_count_histogram": {
            str(key): value for key, value in sorted(candidate_count_histogram.items())
        },
        "unique_nonzero_product_bit_length_histogram": {
            str(key): value for key, value in sorted(nonzero_height_histogram.items())
        },
        "maximum_unique_nonzero_profile": (
            {
                "twice_product_bit_length": maximum_profile[0],
                "numerator_bit_length": maximum_profile[1],
                "denominator_bit_length": maximum_profile[2],
                "coordinate": maximum_profile[3],
            }
            if maximum_profile is not None
            else None
        ),
        "input_artifacts": [
            {
                "path": str(item["path"]),
                "sha256": item["sha256"],
                "characteristic": item["characteristic"],
            }
            for item in artifacts
        ],
        "input_diagnostic": {
            "path": str(DIAGNOSTIC),
            "sha256": file_sha256(DIAGNOSTIC),
        },
        "source_sha256": file_sha256(Path(__file__).resolve()),
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "This is a bounded coefficient-height census for one fixed-free "
            "gauge. Unique candidates are not a polynomial identity, and no "
            "claim is made about a colon, saturation, secant closure, or HC4."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
