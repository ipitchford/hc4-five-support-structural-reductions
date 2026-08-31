#!/usr/bin/env python3
"""Retract the old-pool interpretation of the coordinate-13 RR candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parent.parent
OLD_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-rr-coordinate13-"
    "independent-audit.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-rr-coordinate13-"
    "old-pool-correction.json"
)
COORDINATE = 13
NUMERATOR = int(
    "-303117853966975809344472432454527326602304150142809814264909409693684376567348940486580259893160254806967553359938433903087461094978379292473369929355112954577338675354410092218484096"
)
DENOMINATOR = 84852601
NEW_PRIMES = (
    2147483123,
    2147483077,
    2147483069,
    2147483059,
    2147483053,
    2147483033,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    old_payload = json.loads(OLD_RECEIPT.read_text(encoding="utf-8"))
    if old_payload.get("status") != "PASS_INDEPENDENT_COORDINATE13_CRT_PROFILE":
        raise ValueError("unexpected old-pool receipt status")
    expected_candidate = {
        "numerator": str(NUMERATOR),
        "denominator": str(DENOMINATOR),
    }
    if old_payload.get(
        "common_candidate_across_all_three_small_prime_leave_one_out_runs"
    ) != [expected_candidate]:
        raise ValueError("old receipt no longer records the frozen candidate")

    falsifiers = []
    for prime in NEW_PRIMES:
        artifact_path = CAMPAIGN / "artifacts" / (
            f"j2-secant-r10-third-colon-identity-fixed-free-p{prime}.json"
        )
        receipt_path = CAMPAIGN / "receipts" / (
            f"hsop-j2-secant-r10-third-colon-identity-fixed-free-p{prime}.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY":
            raise ValueError(f"new-prime receipt is not PASS: {receipt_path}")
        artifact_sha256 = file_sha256(artifact_path)
        if receipt.get("certificate", {}).get("sha256") != artifact_sha256:
            raise ValueError(f"receipt/artifact hash mismatch: {artifact_path}")
        artifact = json.loads(artifact_path.read_text(encoding="ascii"))
        if int(artifact["characteristic"]) != prime:
            raise ValueError(f"artifact characteristic mismatch: {artifact_path}")
        vector = list(map(int, artifact["coordinate_vector"]))
        if artifact.get("coordinate_vector_sha256") != canonical_hash(vector):
            raise ValueError(f"coordinate-vector hash mismatch: {artifact_path}")
        observed = vector[COORDINATE] % prime
        if DENOMINATOR % prime == 0:
            raise ValueError("candidate denominator vanished at a new prime")
        predicted = NUMERATOR % prime * pow(DENOMINATOR % prime, -1, prime) % prime
        falsifiers.append(
            {
                "characteristic": prime,
                "artifact": {
                    "path": str(artifact_path),
                    "sha256": artifact_sha256,
                },
                "modular_receipt": {
                    "path": str(receipt_path),
                    "sha256": file_sha256(receipt_path),
                    "status": receipt["status"],
                },
                "candidate_predicted_residue": predicted,
                "observed_coordinate_residue": observed,
                "difference_mod_characteristic": (predicted - observed) % prime,
                "candidate_matches": predicted == observed,
            }
        )
    if any(item["candidate_matches"] for item in falsifiers):
        raise ValueError("the candidate was not rejected by every frozen new prime")

    result = {
        "schema": "hc4.third-colon-coordinate13-old-pool-correction.v1",
        "status": "CORRECTION_RETRACT_OLD_POOL_COORDINATE13_INTERPRETATION",
        "coordinate": COORDINATE,
        "retracted_interpretation": (
            "The displayed 634-bit fraction was described as the reconstructed "
            "or true fixed-gauge coordinate 13. That interpretation is false."
        ),
        "preserved_old_pool_result": (
            "The fraction remains an exact strict-product candidate compatible "
            "with the old 23-prime pool and its three small-prime leave-one-out "
            "tests. This pool-relative compatibility did not identify the "
            "characteristic-zero coefficient."
        ),
        "old_pool_receipt": {
            "path": str(OLD_RECEIPT),
            "sha256": file_sha256(OLD_RECEIPT),
            "status": old_payload["status"],
        },
        "rejected_candidate": expected_candidate,
        "candidate_twice_product_bit_length": (
            2 * abs(NUMERATOR) * DENOMINATOR
        ).bit_length(),
        "new_prime_falsifiers": falsifiers,
        "all_six_new_primes_reject": True,
        "source_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "claim_boundary": (
            "This correction concerns only the rational interpretation of one "
            "fixed-gauge coordinate. It does not retract any exact modular "
            "identity and makes no characteristic-zero ideal-membership, colon, "
            "saturation, secant, or HC4 claim."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
