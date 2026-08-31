#!/usr/bin/env python3
"""Independent CRT/continued-fraction audit for third-colon coordinate 13.

This script intentionally does not import the production reconstruction code.
It starts from the frozen M512 diagnostic, verifies every referenced artifact
hash, extracts one coordinate, and records how the complete strict-product
continued-fraction candidate set changes when held-out primes are absorbed into
the CRT modulus.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parent.parent
INPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-qq-reconstruction-"
    "asymmetric-m512-diagnostic.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-rr-coordinate13-independent-audit.json"
)
COORDINATE = 13


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def crt_pair(value: int, modulus: int, residue: int, prime: int) -> tuple[int, int]:
    """Combine x=value (mod modulus) and x=residue (mod prime)."""

    if math.gcd(modulus, prime) != 1:
        raise ValueError("CRT moduli are not coprime")
    correction = (residue - value) % prime
    correction = correction * pow(modulus % prime, -1, prime) % prime
    combined_modulus = modulus * prime
    return (value + modulus * correction) % combined_modulus, combined_modulus


def strict_product_candidates(residue: int, modulus: int) -> list[tuple[int, int]]:
    """Return all primitive a/b with a=b*residue mod M and 2|a|b<M.

    Legendre's theorem makes the continued-fraction convergents complete under
    this strict product bound.  Extended-Euclid remainders and their residue
    coefficients encode those convergents directly.
    """

    residue %= modulus
    if residue == 0:
        return [(0, 1)]
    previous_remainder, remainder = modulus, residue
    previous_coefficient, coefficient = 0, 1
    candidates: set[tuple[int, int]] = set()
    while remainder:
        numerator, denominator = remainder, coefficient
        if denominator < 0:
            numerator, denominator = -numerator, -denominator
        common = math.gcd(abs(numerator), denominator)
        numerator //= common
        denominator //= common
        if (
            denominator > 0
            and math.gcd(denominator, modulus) == 1
            and 2 * abs(numerator) * denominator < modulus
            and (numerator - residue * denominator) % modulus == 0
        ):
            candidates.add((numerator, denominator))
        quotient = previous_remainder // remainder
        previous_remainder, remainder = (
            remainder,
            previous_remainder - quotient * remainder,
        )
        previous_coefficient, coefficient = (
            coefficient,
            previous_coefficient - quotient * coefficient,
        )
    return sorted(candidates)


def matches(candidate: tuple[int, int], residue: int, prime: int) -> bool:
    numerator, denominator = candidate
    return denominator % prime != 0 and (
        numerator * pow(denominator % prime, -1, prime) - residue
    ) % prime == 0


def load_reference(record: dict[str, object]) -> tuple[int, int, Path]:
    path = Path(str(record["path"]))
    expected = str(record["sha256"])
    observed = file_sha256(path)
    if observed != expected:
        raise ValueError(f"artifact hash mismatch: {path}")
    payload = json.loads(path.read_text(encoding="ascii"))
    prime = int(record["characteristic"])
    if int(payload["characteristic"]) != prime:
        raise ValueError(f"characteristic mismatch: {path}")
    vector = payload["coordinate_vector"]
    if len(vector) <= COORDINATE:
        raise ValueError(f"coordinate vector too short: {path}")
    return prime, int(vector[COORDINATE]) % prime, path


def profile(
    residue: int,
    modulus: int,
    remaining: list[tuple[int, int, Path]],
) -> dict[str, object]:
    candidates = strict_product_candidates(residue, modulus)
    filters = []
    survivors = candidates
    for prime, observed, _ in remaining:
        survivors = [item for item in survivors if matches(item, observed, prime)]
        filters.append({"characteristic": prime, "survivor_count": len(survivors)})
    return {
        "modulus_bit_length": modulus.bit_length(),
        "strict_product_candidate_count": len(candidates),
        "remaining_prime_filter_profile": filters,
        "survivor_count_after_all_remaining_primes": len(survivors),
        "survivor_height_profiles_first_eight": [
            {
                "numerator": str(numerator),
                "denominator": str(denominator),
                "numerator_bit_length": abs(numerator).bit_length(),
                "denominator_bit_length": denominator.bit_length(),
                "twice_product_bit_length": (
                    2 * abs(numerator) * denominator
                ).bit_length(),
            }
            for numerator, denominator in survivors[:8]
        ],
    }


def main() -> int:
    diagnostic = json.loads(INPUT.read_text(encoding="utf-8"))
    source_records = diagnostic["input_certificates"]
    appended_records = (
        diagnostic["selection_heldout_certificates"]
        + diagnostic["heldout_certificates"]
    )
    # Two further independently generated primes were not in the M512 run.
    for prime in (2147483171, 2147483137):
        path = CAMPAIGN / "artifacts" / (
            f"j2-secant-r10-third-colon-identity-fixed-free-p{prime}.json"
        )
        appended_records.append(
            {
                "path": str(path),
                "sha256": file_sha256(path),
                "characteristic": prime,
            }
        )

    source = [load_reference(record) for record in source_records]
    appended = [load_reference(record) for record in appended_records]
    residue, modulus = 0, 1
    for prime, observed, _ in source:
        residue, modulus = crt_pair(residue, modulus, observed, prime)

    profiles = [
        {
            "absorbed_characteristics": [prime for prime, _, _ in source],
            **profile(residue, modulus, appended),
        }
    ]
    absorbed = [prime for prime, _, _ in source]
    for offset, (prime, observed, _) in enumerate(appended):
        residue, modulus = crt_pair(residue, modulus, observed, prime)
        absorbed.append(prime)
        profiles.append(
            {
                "absorbed_characteristics": list(absorbed),
                **profile(residue, modulus, appended[offset + 1 :]),
            }
        )

    all_data = source + appended
    leave_one_out = []
    for heldout_prime in (173, 197, 199):
        heldout = next(item for item in all_data if item[0] == heldout_prime)
        residue, modulus = 0, 1
        for prime, observed, _ in all_data:
            if prime != heldout_prime:
                residue, modulus = crt_pair(residue, modulus, observed, prime)
        candidates = strict_product_candidates(residue, modulus)
        survivors = [
            item for item in candidates if matches(item, heldout[1], heldout_prime)
        ]
        leave_one_out.append(
            {
                "heldout_characteristic": heldout_prime,
                "source_modulus_bit_length": modulus.bit_length(),
                "candidate_count_before_heldout": len(candidates),
                "candidate_count_after_heldout": len(survivors),
                "survivors": [
                    {
                        "numerator": str(numerator),
                        "denominator": str(denominator),
                        "numerator_bit_length": abs(numerator).bit_length(),
                        "denominator_bit_length": denominator.bit_length(),
                        "twice_product_bit_length": (
                            2 * abs(numerator) * denominator
                        ).bit_length(),
                    }
                    for numerator, denominator in survivors
                ],
            }
        )

    survivor_sets = [
        {
            (int(item["numerator"]), int(item["denominator"]))
            for item in record["survivors"]
        }
        for record in leave_one_out
    ]
    common_leave_one_out = set.intersection(*survivor_sets)

    result = {
        "schema": "hc4.third-colon-coordinate13-independent-rr-audit.v1",
        "status": "PASS_INDEPENDENT_COORDINATE13_CRT_PROFILE",
        "coordinate": COORDINATE,
        "input_diagnostic": str(INPUT),
        "input_diagnostic_sha256": file_sha256(INPUT),
        "source_count": len(source),
        "appended_prime_order": [prime for prime, _, _ in appended],
        "profiles": profiles,
        "small_prime_leave_one_out_profiles": leave_one_out,
        "common_candidate_across_all_three_small_prime_leave_one_out_runs": [
            {"numerator": str(numerator), "denominator": str(denominator)}
            for numerator, denominator in sorted(common_leave_one_out)
        ],
        "claim_boundary": (
            "This audits only coordinate 13 and the completeness of the strict-"
            "product continued-fraction search. It does not reconstruct the full "
            "multiplier vector or prove the rational polynomial identity."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
