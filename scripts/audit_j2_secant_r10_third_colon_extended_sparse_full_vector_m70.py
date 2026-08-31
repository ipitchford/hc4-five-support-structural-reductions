#!/usr/bin/env python3
"""Complete bounded M70 census for the extended-sparse p181 gauge.

The source modulus is frozen to

    M = 181 * 2147483647 * 2147483629,

and p=173,197 are selectors only.  At every one of the 38,048 multiplier
coordinates, enumerate all reduced fractions n/d satisfying

    d > 0, gcd(d, M) = 1, n = r*d (mod M), 2*abs(n)*d < M,

then filter that complete strict-product candidate set through both held-out
selectors in the frozen order.  The receipt commits to the full ordered
candidate, selector-survivor, and outcome streams and compares the resulting
coordinate labels with the frozen old-gauge M566 and dense-swap M70 censuses.

This file is standalone.  It does not import or execute any earlier census
producer.  It is a bounded modular height census and makes no QQ identity or
geometric conclusion.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import platform
import resource
import sys
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parent.parent
ARTIFACTS = CAMPAIGN / "artifacts"
RECEIPTS = CAMPAIGN / "receipts"
RESEARCH = CAMPAIGN / "research"

EXPECTED_SOURCE_PRIMES = [181, 2147483647, 2147483629]
EXPECTED_SELECTOR_PRIMES = [173, 197]
EXPECTED_SOURCE_MODULUS = 834715161561466408303
EXPECTED_SOURCE_MODULUS_BITS = 70
EXPECTED_COORDINATE_COUNT = 38048
EXPECTED_PIVOT_COUNT = 35881
EXPECTED_FREE_COUNT = 2167

EXPECTED_P181_ARTIFACT_SHA256 = (
    "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b"
)
EXPECTED_P181_RECEIPT_SHA256 = (
    "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c"
)
EXPECTED_FREE_INDICES_SHA256 = (
    "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
)
EXPECTED_PIVOT_SET_SHA256 = (
    "2e59d83eba84cab80823a8277b2b40f1af518a02e7ae5de595baed358de01a1c"
)
EXPECTED_P181_ORDERED_PIVOT_SHA256 = (
    "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d"
)

P181_ARTIFACT = ARTIFACTS / (
    "j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
)
P181_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
)

INPUT_SPECS = [
    {
        "role": "source",
        "characteristic": 181,
        "artifact": P181_ARTIFACT,
        "artifact_sha256": EXPECTED_P181_ARTIFACT_SHA256,
        "receipt": P181_RECEIPT,
        "receipt_sha256": EXPECTED_P181_RECEIPT_SHA256,
    },
    {
        "role": "source",
        "characteristic": 2147483647,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "artifact_sha256": (
            "a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad"
        ),
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "receipt_sha256": (
            "dba8ffbaf933500d5e532f9f4b19f356b20710383614b9d8b03200980e611f79"
        ),
    },
    {
        "role": "source",
        "characteristic": 2147483629,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "artifact_sha256": (
            "2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90"
        ),
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "receipt_sha256": (
            "f572ebb40bbb4d590506210737347b0c6c964927ac866d9fba410621d4e354bb"
        ),
    },
    {
        "role": "selector",
        "characteristic": 173,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "artifact_sha256": (
            "b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c"
        ),
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "receipt_sha256": (
            "ddaed2462174438e89b31cfacb95ee2adf7971bf2290c58422031baab9314f44"
        ),
    },
    {
        "role": "selector",
        "characteristic": 197,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "artifact_sha256": (
            "f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272"
        ),
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "receipt_sha256": (
            "671df724adb16f279f9be31dfe0c87f90b0d48f02a9ea6161245f26d86c701fe"
        ),
    },
]

EXPECTED_MODULAR_RECEIPT_STATUS = "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"

PREREGISTRATION = RESEARCH / "THIRD_COLON_EXTENDED_SPARSE_P181_PREREGISTRATION.md"
EXPECTED_PREREGISTRATION_SHA256 = (
    "f26461b829d82d453e3447db6d4956d903238997fb83d516f8db934b8234f497"
)
EXTERNAL_TELEMETRY = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.time.txt"
)
EXPECTED_EXTERNAL_TELEMETRY_SHA256 = (
    "67e37fb4b7a8cf22a8f9a37c2757341e9324e9277783728739178ce7babab92d"
)

OLD_GAUGE_ARTIFACT = ARTIFACTS / (
    "j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)
OLD_GAUGE_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)
EXPECTED_OLD_GAUGE_ARTIFACT_SHA256 = (
    "26be0a64574c3cdbe6f7d0c323f9a5e4beb9b8df8e568f9daa054744160bc0a1"
)
EXPECTED_OLD_GAUGE_RECEIPT_SHA256 = (
    "fe32cc53e81cf50e6c34881c5c61605938178a366986fae6ce872670aa9ddc6a"
)
EXPECTED_OLD_FREE_INDICES_SHA256 = (
    "0fc299317fc6e2aff3c3a89031e71a9f81f4145f59332f9ae8b4ff9040b44e68"
)
EXPECTED_OLD_PIVOT_SET_SHA256 = (
    "8ca3d8472b2562e75db28924e5c4f5cdad7e099d17d932dd11a8b7b914d2f02f"
)

EXPECTED_GAUGE_CHANGE_REGIONS = {
    "shared_pivots": {
        "coordinate_count": 35623,
        "coordinate_set_sha256": (
            "4f9e92a57736ca9d67b58a0df275c7435a14aa58b549e77fc93afda96f5daf4e"
        ),
    },
    "old_pivots_now_free": {
        "coordinate_count": 258,
        "coordinate_set_sha256": (
            "cc8cdb84d1916b6e83cd17da3da3932b195b4930171c746a5eee8ac6a01ec8e4"
        ),
    },
    "old_free_now_pivots": {
        "coordinate_count": 258,
        "coordinate_set_sha256": (
            "a8ec0af6a742b7a2828d6bcc73fa0f411668afa2af3543cd1fd54343f6703e58"
        ),
    },
    "shared_free": {
        "coordinate_count": 1909,
        "coordinate_set_sha256": (
            "355934d536bb87455621233e49f622ce2246d89f7d8fcfedcfec41e3541cde5a"
        ),
    },
}
EXPECTED_GAUGE_REGION_PARTITION_SHA256 = (
    "55b4d12c133fcf0bf4244058921b6d575132170a99e805019f6e3690a10922f9"
)

BENCHMARK_SPECS = [
    {
        "name": "old_alt_p181_gauge_m566",
        "path": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-alt-p181-gauge-full-vector-m566-census.json",
        "sha256": (
            "096d74c093aed06874cc5b569ff89ee3f7a513bcdd1eb51d77599208176e5c33"
        ),
        "schema": "hc4.third-colon-alt-gauge-full-vector-m566-census.v1",
        "status": "PASS_BOUNDED_FULL_VECTOR_HEIGHT_CENSUS",
        "source_modulus_bit_length": 566,
        "source_characteristics": [
            181,
            2147483647,
            2147483629,
            2147483587,
            2147483579,
            2147483563,
            2147483543,
            2147483497,
            2147483489,
            2147483477,
            2147483423,
            2147483399,
            2147483353,
            2147483323,
            2147483269,
            2147483249,
            2147483237,
            2147483179,
            2147483171,
        ],
        "selector_characteristics": [173, 197, 199, 2147483549],
        "outcome": {
            "no_candidate": 19762,
            "ambiguous": 0,
            "unique_zero": 17751,
            "unique_nonzero": 535,
        },
    },
    {
        "name": "dense_pivot_swap_m70",
        "path": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-dense-pivot-swap-full-vector-m70-census.json",
        "sha256": (
            "ede0ec6658eb8254a0cea833e8d185b2b3f19c736919905d09fea66db80f1bea"
        ),
        "schema": "hc4.third-colon-dense-pivot-swap-full-vector-m70-census.v1",
        "status": "PASS_BOUNDED_DENSE_PIVOT_SWAP_FULL_VECTOR_M70_CENSUS",
        "source_modulus_bit_length": 70,
        "source_characteristics": [181, 2147483647, 2147483629],
        "selector_characteristics": [173, 197, 199],
        "outcome": {
            "no_candidate": 19844,
            "ambiguous": 0,
            "unique_zero": 17660,
            "unique_nonzero": 544,
        },
    },
]

DEFAULT_OUTPUT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-m70-census.json"
)

OUTCOME_LABELS = (
    "no_candidate",
    "ambiguous",
    "unique_zero",
    "unique_nonzero",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def is_prime_32(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def complete_strict_product_candidates(
    residue: int, modulus: int
) -> tuple[list[tuple[int, int]], int]:
    """Enumerate the complete strict-product region by extended Euclid."""

    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0

    old_remainder, remainder = modulus, residue
    old_coefficient, coefficient = 0, 1
    candidates: set[tuple[int, int]] = set()
    steps = 0
    while remainder:
        steps += 1
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
        quotient = old_remainder // remainder
        old_remainder, remainder = (
            remainder,
            old_remainder - quotient * remainder,
        )
        old_coefficient, coefficient = (
            coefficient,
            old_coefficient - quotient * coefficient,
        )
    return sorted(candidates), steps


def iterative_crt_setup(primes: list[int]) -> tuple[list[tuple[int, int, int]], int]:
    modulus = 1
    stages: list[tuple[int, int, int]] = []
    for prime in primes:
        if math.gcd(modulus, prime) != 1:
            raise AssertionError("source characteristics are not pairwise coprime")
        inverse = pow(modulus % prime, -1, prime)
        stages.append((prime, modulus, inverse))
        modulus *= prime
    return stages, modulus


def iterative_crt(residues: list[int], stages: list[tuple[int, int, int]]) -> int:
    value = 0
    for residue, (prime, modulus, inverse) in zip(residues, stages, strict=True):
        correction = (residue - value) % prime
        value += modulus * (correction * inverse % prime)
    return value


def exact_replay_passes(receipt: dict[str, object]) -> bool:
    replay = receipt.get("same_process_sparse_replay", {})
    return bool(
        replay.get("completed")
        and replay.get("identity_zero")
        and int(replay.get("mismatch_count", -1)) == 0
        and replay.get("first_mismatch") is None
    )


def validate_partition(
    pivots: list[int], free: list[int], artifact_path: Path
) -> None:
    universe = set(range(EXPECTED_COORDINATE_COUNT))
    if (
        len(pivots) != EXPECTED_PIVOT_COUNT
        or len(free) != EXPECTED_FREE_COUNT
        or len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != universe
    ):
        raise AssertionError(f"invalid pivot/free partition: {artifact_path}")


def load_input(spec: dict[str, object]) -> dict[str, object]:
    artifact_path = Path(spec["artifact"]).resolve()
    receipt_path = Path(spec["receipt"]).resolve()
    if not artifact_path.is_file() or not receipt_path.is_file():
        raise FileNotFoundError(f"frozen modular input is absent: {artifact_path}")

    artifact_sha = file_sha256(artifact_path)
    receipt_sha = file_sha256(receipt_path)
    if artifact_sha != spec["artifact_sha256"]:
        raise AssertionError(f"artifact hash left frozen manifest: {artifact_path}")
    if receipt_sha != spec["receipt_sha256"]:
        raise AssertionError(f"receipt hash left frozen manifest: {receipt_path}")

    artifact = json.loads(artifact_path.read_text(encoding="ascii"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    characteristic = int(spec["characteristic"])
    if not is_prime_32(characteristic):
        raise AssertionError(f"nonprime characteristic: {characteristic}")
    if int(artifact.get("characteristic", -1)) != characteristic:
        raise AssertionError(f"artifact characteristic mismatch: {artifact_path}")
    if int(receipt.get("characteristic", -1)) != characteristic:
        raise AssertionError(f"receipt characteristic mismatch: {receipt_path}")
    if receipt.get("status") != EXPECTED_MODULAR_RECEIPT_STATUS:
        raise AssertionError(f"nonpassing modular receipt: {receipt_path}")
    if not exact_replay_passes(receipt):
        raise AssertionError(f"modular replay is not exact: {receipt_path}")

    certificate = receipt.get("certificate", {})
    if (
        certificate.get("sha256") != artifact_sha
        or int(certificate.get("byte_count", -1)) != artifact_path.stat().st_size
        or Path(str(certificate.get("path", ""))).resolve() != artifact_path
    ):
        raise AssertionError(f"receipt does not exactly bind artifact: {receipt_path}")

    vector = list(map(int, artifact["coordinate_vector"]))
    pivots = list(map(int, artifact["pivot_unknown_indices"]))
    free = list(map(int, artifact["free_unknown_indices"]))
    if len(vector) != EXPECTED_COORDINATE_COUNT:
        raise AssertionError(f"coordinate-vector length mismatch: {artifact_path}")
    if any(value < 0 or value >= characteristic for value in vector):
        raise AssertionError(f"noncanonical field residue: {artifact_path}")
    if artifact.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise AssertionError(f"coordinate-vector hash mismatch: {artifact_path}")
    if artifact.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise AssertionError(f"ordered-pivot hash mismatch: {artifact_path}")
    if artifact.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise AssertionError(f"free-coordinate hash mismatch: {artifact_path}")
    validate_partition(pivots, free, artifact_path)
    if artifact.get("free_unknown_indices_sha256") != EXPECTED_FREE_INDICES_SHA256:
        raise AssertionError(f"extended-sparse free gauge changed: {artifact_path}")
    pivot_set_sha = canonical_hash(sorted(pivots))
    if pivot_set_sha != EXPECTED_PIVOT_SET_SHA256:
        raise AssertionError(f"extended-sparse pivot set changed: {artifact_path}")

    if characteristic == 181:
        if artifact.get("pivot_unknown_indices_sha256") != (
            EXPECTED_P181_ORDERED_PIVOT_SHA256
        ):
            raise AssertionError("the frozen p181 ordered pivot stream changed")
        if artifact.get("gauge_source") is not None:
            raise AssertionError("the p181 experiment unexpectedly imports a gauge")
    else:
        gauge_source = artifact.get("gauge_source", {})
        if (
            int(gauge_source.get("characteristic", -1)) != 181
            or gauge_source.get("sha256") != EXPECTED_P181_ARTIFACT_SHA256
            or gauge_source.get("free_unknown_indices_sha256")
            != EXPECTED_FREE_INDICES_SHA256
            or gauge_source.get("pivot_unknown_set_sha256")
            != EXPECTED_PIVOT_SET_SHA256
            or gauge_source.get("policy")
            != "freeze source free-coordinate set; adapt pivot order"
        ):
            raise AssertionError(f"transfer gauge source changed: {artifact_path}")

    gauge = receipt.get("gauge", {})
    solver = receipt.get("solver", {})
    if (
        not gauge.get("coverage_verified")
        or gauge.get("free_unknown_indices_sha256")
        != EXPECTED_FREE_INDICES_SHA256
        or int(solver.get("free_unknown_count", -1)) != EXPECTED_FREE_COUNT
        or int(solver.get("pivot_count", -1)) != EXPECTED_PIVOT_COUNT
        or not solver.get("completed")
        or not solver.get("consistent")
        or solver.get("timed_out")
    ):
        raise AssertionError(f"modular gauge/solver audit failed: {receipt_path}")

    signature = {
        key: artifact.get(key)
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
    signature["pivot_unknown_set_sha256"] = pivot_set_sha
    return {
        "role": str(spec["role"]),
        "characteristic": characteristic,
        "path": str(artifact_path),
        "sha256": artifact_sha,
        "byte_count": artifact_path.stat().st_size,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_sha,
        "receipt_byte_count": receipt_path.stat().st_size,
        "receipt_status": receipt["status"],
        "receipt_wall_seconds": receipt.get("timings", {}).get("wall_seconds"),
        "receipt_maximum_rss_native": receipt.get("resources", {}).get(
            "maximum_rss_native"
        ),
        "vector": vector,
        "pivots": pivots,
        "free": free,
        "signature": signature,
    }


def validate_bound_file(path: Path, expected_sha256: str, label: str) -> dict[str, object]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"frozen {label} is absent: {resolved}")
    actual = file_sha256(resolved)
    if actual != expected_sha256:
        raise AssertionError(f"frozen {label} hash changed: {resolved}")
    return {
        "path": str(resolved),
        "sha256": actual,
        "byte_count": resolved.stat().st_size,
    }


def derive_gauge_change_regions(
    p181: dict[str, object]
) -> tuple[dict[str, list[int]], dict[str, object]]:
    old_artifact_record = validate_bound_file(
        OLD_GAUGE_ARTIFACT,
        EXPECTED_OLD_GAUGE_ARTIFACT_SHA256,
        "old-gauge artifact",
    )
    old_receipt_record = validate_bound_file(
        OLD_GAUGE_RECEIPT,
        EXPECTED_OLD_GAUGE_RECEIPT_SHA256,
        "old-gauge receipt",
    )
    old_artifact = json.loads(OLD_GAUGE_ARTIFACT.read_text(encoding="ascii"))
    old_receipt = json.loads(OLD_GAUGE_RECEIPT.read_text(encoding="utf-8"))
    certificate = old_receipt.get("certificate", {})
    if (
        old_receipt.get("status") != EXPECTED_MODULAR_RECEIPT_STATUS
        or not exact_replay_passes(old_receipt)
        or certificate.get("sha256") != EXPECTED_OLD_GAUGE_ARTIFACT_SHA256
        or Path(str(certificate.get("path", ""))).resolve()
        != OLD_GAUGE_ARTIFACT.resolve()
        or int(certificate.get("byte_count", -1))
        != OLD_GAUGE_ARTIFACT.stat().st_size
    ):
        raise AssertionError("old-gauge receipt provenance failed")

    old_pivots = list(map(int, old_artifact["pivot_unknown_indices"]))
    old_free = list(map(int, old_artifact["free_unknown_indices"]))
    validate_partition(old_pivots, old_free, OLD_GAUGE_ARTIFACT)
    if (
        canonical_hash(old_free) != EXPECTED_OLD_FREE_INDICES_SHA256
        or canonical_hash(sorted(old_pivots)) != EXPECTED_OLD_PIVOT_SET_SHA256
    ):
        raise AssertionError("old-gauge coordinate partition changed")

    invariant_keys = (
        "schema",
        "row_descriptor_sha256",
        "monomial_stream_sha256",
        "generator_stream_sha256",
        "target_sha256",
        "target_character_weight",
    )
    p181_artifact = json.loads(P181_ARTIFACT.read_text(encoding="ascii"))
    if any(old_artifact.get(key) != p181_artifact.get(key) for key in invariant_keys):
        raise AssertionError("old and extended-sparse gauges encode different problems")

    old_pivot_set = set(old_pivots)
    old_free_set = set(old_free)
    new_pivot_set = set(map(int, p181["pivots"]))
    new_free_set = set(map(int, p181["free"]))
    regions = {
        "shared_pivots": sorted(old_pivot_set & new_pivot_set),
        "old_pivots_now_free": sorted(old_pivot_set & new_free_set),
        "old_free_now_pivots": sorted(old_free_set & new_pivot_set),
        "shared_free": sorted(old_free_set & new_free_set),
    }
    if canonical_hash(regions) != EXPECTED_GAUGE_REGION_PARTITION_SHA256:
        raise AssertionError("extended-sparse gauge-change partition changed")
    if set().union(*(set(indices) for indices in regions.values())) != set(
        range(EXPECTED_COORDINATE_COUNT)
    ):
        raise AssertionError("gauge-change regions do not cover all coordinates")
    for name, indices in regions.items():
        expected = EXPECTED_GAUGE_CHANGE_REGIONS[name]
        if (
            len(indices) != expected["coordinate_count"]
            or canonical_hash(indices) != expected["coordinate_set_sha256"]
        ):
            raise AssertionError(f"gauge-change region changed: {name}")

    old_handoff = old_receipt.get("solver", {}).get("hybrid_dense_handoff", {})
    new_receipt = json.loads(P181_RECEIPT.read_text(encoding="utf-8"))
    if int(old_handoff.get("dense_pivot_count", -1)) != 581:
        raise AssertionError("old-gauge dense benchmark telemetry changed")
    if new_receipt.get("solver", {}).get("hybrid_dense_handoff") is not None:
        raise AssertionError("extended-sparse p181 unexpectedly used a dense handoff")
    telemetry = {
        "old_gauge": {
            "solve_wall_seconds": old_receipt.get("solver", {}).get(
                "solve_seconds"
            ),
            "receipt_wall_seconds": old_receipt.get("timings", {}).get(
                "wall_seconds"
            ),
            "maximum_rss_native": old_receipt.get("resources", {}).get(
                "maximum_rss_native"
            ),
            "dense_pivot_count": old_handoff.get("dense_pivot_count"),
            "dense_augmented_shape": old_handoff.get("dense_augmented_shape"),
        },
        "extended_sparse_p181": {
            "solve_wall_seconds": new_receipt.get("solver", {}).get(
                "solve_seconds"
            ),
            "receipt_wall_seconds": new_receipt.get("timings", {}).get(
                "wall_seconds"
            ),
            "maximum_rss_native": new_receipt.get("resources", {}).get(
                "maximum_rss_native"
            ),
            "dense_pivot_count": 0,
            "dense_augmented_shape": None,
            "all_pivots_completed_by_sparse_elimination": True,
        },
    }
    return regions, {
        "old_artifact": old_artifact_record,
        "old_receipt": old_receipt_record,
        "telemetry": telemetry,
    }


def load_benchmark(spec: dict[str, object]) -> dict[str, object]:
    record = validate_bound_file(
        Path(spec["path"]), str(spec["sha256"]), f"benchmark {spec['name']}"
    )
    data = json.loads(Path(spec["path"]).read_text(encoding="utf-8"))
    normalized_outcome = {
        label: int(data.get("outcome", {}).get(label, 0))
        for label in OUTCOME_LABELS
    }
    if (
        data.get("schema") != spec["schema"]
        or data.get("status") != spec["status"]
        or int(data.get("coordinate_count", -1)) != EXPECTED_COORDINATE_COUNT
        or int(data.get("source_modulus_bit_length", -1))
        != spec["source_modulus_bit_length"]
        or list(map(int, data.get("source_characteristics", [])))
        != spec["source_characteristics"]
        or list(map(int, data.get("selector_characteristics", [])))
        != spec["selector_characteristics"]
        or normalized_outcome != spec["outcome"]
        or sum(normalized_outcome.values()) != EXPECTED_COORDINATE_COUNT
    ):
        raise AssertionError(f"benchmark contents changed: {spec['name']}")

    coordinates = data.get("coordinates_by_outcome", {})
    normalized_coordinates = {
        label: list(map(int, coordinates.get(label, [])))
        for label in OUTCOME_LABELS
    }
    sets = {label: set(values) for label, values in normalized_coordinates.items()}
    if any(len(values) != normalized_outcome[label] for label, values in sets.items()):
        raise AssertionError(f"benchmark coordinate counts changed: {spec['name']}")
    if sum(len(values) for values in sets.values()) != len(set().union(*sets.values())):
        raise AssertionError(f"benchmark outcomes overlap: {spec['name']}")
    if set().union(*sets.values()) != set(range(EXPECTED_COORDINATE_COUNT)):
        raise AssertionError(f"benchmark outcomes do not cover all coordinates: {spec['name']}")
    for label, values in normalized_coordinates.items():
        if values != sorted(values):
            raise AssertionError(f"benchmark coordinate stream is unordered: {spec['name']}")
    record.update(
        {
            "name": spec["name"],
            "schema": data["schema"],
            "status": data["status"],
            "source_modulus_bit_length": data["source_modulus_bit_length"],
            "source_characteristics": data["source_characteristics"],
            "selector_characteristics": data["selector_characteristics"],
            "outcome": normalized_outcome,
            "coordinates": normalized_coordinates,
        }
    )
    return record


def benchmark_comparison(
    benchmark: dict[str, object], current_labels: list[str], current_outcome: dict[str, int]
) -> dict[str, object]:
    benchmark_labels = [""] * EXPECTED_COORDINATE_COUNT
    for label, coordinates in benchmark["coordinates"].items():
        for coordinate in coordinates:
            benchmark_labels[coordinate] = label
    if not all(benchmark_labels):
        raise AssertionError(f"incomplete benchmark label stream: {benchmark['name']}")

    transition = {
        old: {new: 0 for new in OUTCOME_LABELS} for old in OUTCOME_LABELS
    }
    changed: list[int] = []
    transition_hasher = hashlib.sha256()
    for coordinate, (old, new) in enumerate(
        zip(benchmark_labels, current_labels, strict=True)
    ):
        transition[old][new] += 1
        if old != new:
            changed.append(coordinate)
        transition_hasher.update(f"{coordinate}:{old}>{new}\n".encode("ascii"))

    benchmark_outcome = benchmark["outcome"]
    old_no_candidate = int(benchmark_outcome["no_candidate"])
    new_no_candidate = int(current_outcome["no_candidate"])
    return {
        "benchmark": {
            key: benchmark[key]
            for key in (
                "name",
                "path",
                "sha256",
                "byte_count",
                "schema",
                "status",
                "source_modulus_bit_length",
                "source_characteristics",
                "selector_characteristics",
                "outcome",
            )
        },
        "current_minus_benchmark_outcome_count_delta": {
            label: int(current_outcome[label]) - int(benchmark_outcome[label])
            for label in OUTCOME_LABELS
        },
        "no_candidate_fraction": {
            "benchmark": old_no_candidate / EXPECTED_COORDINATE_COUNT,
            "current": new_no_candidate / EXPECTED_COORDINATE_COUNT,
            "current_minus_benchmark": (
                new_no_candidate - old_no_candidate
            )
            / EXPECTED_COORDINATE_COUNT,
            "relative_change_from_benchmark": (
                (new_no_candidate - old_no_candidate) / old_no_candidate
            ),
        },
        "coordinatewise": {
            "agreement_count": EXPECTED_COORDINATE_COUNT - len(changed),
            "changed_count": len(changed),
            "changed_coordinates": changed,
            "changed_coordinates_sha256": canonical_hash(changed),
            "transition_count_matrix": transition,
            "full_transition_stream_sha256": transition_hasher.hexdigest(),
        },
        "comparison_boundary": (
            "This is a descriptive comparison of bounded coordinate labels. "
            "The gauges, selector sets, and for the old-gauge benchmark the "
            "source modulus differ, so the deltas are not causal evidence and "
            "are not a QQ reconstruction result."
        ),
    }


def compact_input_record(item: dict[str, object]) -> dict[str, object]:
    return {
        key: item[key]
        for key in (
            "role",
            "characteristic",
            "path",
            "sha256",
            "byte_count",
            "receipt_path",
            "receipt_sha256",
            "receipt_byte_count",
            "receipt_status",
            "receipt_wall_seconds",
            "receipt_maximum_rss_native",
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    started_wall = time.perf_counter()
    started_usage = resource.getrusage(resource.RUSAGE_SELF)
    load_started = time.perf_counter()
    preregistration_record = validate_bound_file(
        PREREGISTRATION, EXPECTED_PREREGISTRATION_SHA256, "preregistration"
    )
    external_telemetry_record = validate_bound_file(
        EXTERNAL_TELEMETRY,
        EXPECTED_EXTERNAL_TELEMETRY_SHA256,
        "external p181 telemetry",
    )
    inputs = [load_input(spec) for spec in INPUT_SPECS]
    sources = [item for item in inputs if item["role"] == "source"]
    selectors = [item for item in inputs if item["role"] == "selector"]
    source_primes = [int(item["characteristic"]) for item in sources]
    selector_primes = [int(item["characteristic"]) for item in selectors]
    if source_primes != EXPECTED_SOURCE_PRIMES:
        raise AssertionError("frozen M70 source order changed")
    if selector_primes != EXPECTED_SELECTOR_PRIMES:
        raise AssertionError("frozen selector order changed")
    if set(source_primes) & set(selector_primes):
        raise AssertionError("a selector entered the source modulus")
    signatures = {canonical_hash(item["signature"]) for item in inputs}
    if len(signatures) != 1:
        raise AssertionError("extended-sparse problem/gauge signatures differ")
    fixed_gauge_signature_sha = next(iter(signatures))
    p181 = next(item for item in sources if item["characteristic"] == 181)
    gauge_regions, gauge_provenance = derive_gauge_change_regions(p181)
    benchmarks = [load_benchmark(spec) for spec in BENCHMARK_SPECS]
    load_seconds = time.perf_counter() - load_started

    crt_stages, modulus = iterative_crt_setup(source_primes)
    if modulus != EXPECTED_SOURCE_MODULUS:
        raise AssertionError("source modulus left the frozen M70 gate")
    if modulus.bit_length() != EXPECTED_SOURCE_MODULUS_BITS:
        raise AssertionError("source modulus bit length is not 70")

    outcome: collections.Counter[str] = collections.Counter()
    outcome_coordinates = {label: [] for label in OUTCOME_LABELS}
    outcome_label_vector: list[str] = []
    candidate_histogram: collections.Counter[int] = collections.Counter()
    final_survivor_histogram: collections.Counter[int] = collections.Counter()
    product_height_histogram: collections.Counter[int] = collections.Counter()
    candidate_count_vector: list[int] = []
    selector_stage_count_vectors = [[] for _ in selectors]
    selector_stage_totals = [0] * len(selectors)
    selector_stage_nonempty_counts = [0] * len(selectors)
    combined_residues: list[str] = []
    final_survivor_records: list[dict[str, object]] = []
    total_eea_steps = 0
    total_candidates = 0
    all_source_zero_count = 0
    maximum_unique_profile: tuple[int, int, int, int, int, int] | None = None
    candidate_stream_hasher = hashlib.sha256()
    selector_stream_hashers = [hashlib.sha256() for _ in selectors]
    outcome_stream_hasher = hashlib.sha256()
    unique_candidate_hasher = hashlib.sha256()

    census_started = time.perf_counter()
    for coordinate in range(EXPECTED_COORDINATE_COUNT):
        source_residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        all_source_zero_count += int(not any(source_residues))
        combined = iterative_crt(source_residues, crt_stages)
        combined_residues.append(str(combined))
        candidates, eea_steps = complete_strict_product_candidates(combined, modulus)
        total_eea_steps += eea_steps
        total_candidates += len(candidates)
        candidate_count_vector.append(len(candidates))
        candidate_histogram[len(candidates)] += 1
        candidate_stream_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in candidates:
            candidate_stream_hasher.update(
                f"{numerator}/{denominator};".encode("ascii")
            )
        candidate_stream_hasher.update(b"\n")

        survivors = candidates
        for selector_index, selector in enumerate(selectors):
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
            selector_stage_count_vectors[selector_index].append(len(survivors))
            selector_stage_totals[selector_index] += len(survivors)
            selector_stage_nonempty_counts[selector_index] += int(bool(survivors))
            selector_stream_hashers[selector_index].update(
                f"{coordinate}:".encode("ascii")
            )
            for numerator, denominator in survivors:
                selector_stream_hashers[selector_index].update(
                    f"{numerator}/{denominator};".encode("ascii")
                )
            selector_stream_hashers[selector_index].update(b"\n")

        final_survivor_histogram[len(survivors)] += 1
        if survivors:
            final_survivor_records.append(
                {
                    "coordinate": coordinate,
                    "candidates": [
                        {
                            "reduced_numerator": numerator,
                            "positive_denominator": denominator,
                        }
                        for numerator, denominator in survivors
                    ],
                }
            )

        if not survivors:
            label = "no_candidate"
        elif len(survivors) > 1:
            label = "ambiguous"
        else:
            numerator, denominator = survivors[0]
            label = "unique_zero" if numerator == 0 else "unique_nonzero"
            unique_candidate_hasher.update(
                f"{coordinate}:{numerator}/{denominator}\n".encode("ascii")
            )
            if numerator:
                product_bits = (2 * abs(numerator) * denominator).bit_length()
                product_height_histogram[product_bits] += 1
                profile = (
                    product_bits,
                    abs(numerator).bit_length(),
                    denominator.bit_length(),
                    coordinate,
                    numerator,
                    denominator,
                )
                if maximum_unique_profile is None or profile > maximum_unique_profile:
                    maximum_unique_profile = profile
        outcome[label] += 1
        outcome_coordinates[label].append(coordinate)
        outcome_label_vector.append(label)
        outcome_stream_hasher.update(f"{coordinate}:{label}\n".encode("ascii"))
    census_seconds = time.perf_counter() - census_started

    if sum(outcome.values()) != EXPECTED_COORDINATE_COUNT:
        raise AssertionError("outcomes do not cover all coordinates")
    if any(
        len(selector_stage_count_vectors[index]) != EXPECTED_COORDINATE_COUNT
        for index in range(len(selectors))
    ):
        raise AssertionError("selector stage stream is incomplete")
    outcome_sets = {
        label: set(indices) for label, indices in outcome_coordinates.items()
    }
    gauge_cross_tab: dict[str, object] = {}
    for name, indices in gauge_regions.items():
        index_set = set(indices)
        row = {
            label: len(index_set & outcome_sets[label]) for label in OUTCOME_LABELS
        }
        if sum(row.values()) != len(indices):
            raise AssertionError(f"gauge-region cross-tab row does not total: {name}")
        gauge_cross_tab[name] = {
            "coordinate_count": len(indices),
            "coordinate_set_sha256": canonical_hash(indices),
            "outcome": row,
        }
    for label in OUTCOME_LABELS:
        if sum(
            int(row["outcome"][label]) for row in gauge_cross_tab.values()
        ) != outcome[label]:
            raise AssertionError(f"gauge-region cross-tab column does not total: {label}")

    maximum_record = None
    if maximum_unique_profile is not None:
        (
            product_bits,
            numerator_bits,
            denominator_bits,
            coordinate,
            numerator,
            denominator,
        ) = maximum_unique_profile
        maximum_record = {
            "coordinate": coordinate,
            "reduced_numerator": numerator,
            "positive_denominator": denominator,
            "twice_absolute_product": 2 * abs(numerator) * denominator,
            "twice_product_bit_length": product_bits,
            "numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }

    normalized_outcome = {label: outcome[label] for label in OUTCOME_LABELS}
    comparisons = [
        benchmark_comparison(benchmark, outcome_label_vector, normalized_outcome)
        for benchmark in benchmarks
    ]
    compact_inputs = [compact_input_record(item) for item in inputs]
    finished_usage = resource.getrusage(resource.RUSAGE_SELF)
    script_path = Path(__file__).resolve()
    selector_stage_records = []
    for index, selector in enumerate(selectors):
        counts = selector_stage_count_vectors[index]
        selector_stage_records.append(
            {
                "characteristic": selector["characteristic"],
                "survivor_count_sum_after_selector": selector_stage_totals[index],
                "coordinates_with_a_survivor_after_selector": (
                    selector_stage_nonempty_counts[index]
                ),
                "survivor_count_vector": counts,
                "survivor_count_vector_sha256": canonical_hash(counts),
                "survivor_candidate_stream_sha256": (
                    selector_stream_hashers[index].hexdigest()
                ),
            }
        )

    result = {
        "schema": "hc4.third-colon-extended-sparse-full-vector-m70-census.v1",
        "status": "PASS_BOUNDED_EXTENDED_SPARSE_FULL_VECTOR_M70_CENSUS",
        "method": (
            "iterative CRT over exactly p=181,2147483647,2147483629; "
            "complete coordinatewise strict-product extended-Euclid candidate "
            "enumeration; sequential held-out filtering at exactly p=173,197"
        ),
        "coordinate_count": EXPECTED_COORDINATE_COUNT,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "source_characteristics": source_primes,
        "selector_characteristics": selector_primes,
        "fixed_gauge_signature_sha256": fixed_gauge_signature_sha,
        "outcome": normalized_outcome,
        "full_outcome_streams": {
            "outcome_label_vector": outcome_label_vector,
            "outcome_label_vector_sha256": canonical_hash(outcome_label_vector),
            "outcome_text_stream_sha256": outcome_stream_hasher.hexdigest(),
            "coordinates_by_outcome": outcome_coordinates,
            "coordinates_by_outcome_sha256": {
                label: canonical_hash(indices)
                for label, indices in outcome_coordinates.items()
            },
            "nonempty_final_survivor_records": final_survivor_records,
            "nonempty_final_survivor_records_sha256": canonical_hash(
                final_survivor_records
            ),
        },
        "candidate_enumeration": {
            "total_candidates_before_selectors": total_candidates,
            "total_extended_euclid_steps": total_eea_steps,
            "all_source_residues_zero_coordinate_count": all_source_zero_count,
            "candidate_count_histogram": {
                str(key): value for key, value in sorted(candidate_histogram.items())
            },
            "candidate_count_vector": candidate_count_vector,
            "candidate_count_vector_sha256": canonical_hash(candidate_count_vector),
            "complete_candidate_text_stream_sha256": (
                candidate_stream_hasher.hexdigest()
            ),
            "combined_crt_residue_vector_sha256": canonical_hash(
                combined_residues
            ),
        },
        "selector_filtering": {
            "stages": selector_stage_records,
            "final_survivor_count_histogram": {
                str(key): value
                for key, value in sorted(final_survivor_histogram.items())
            },
            "unique_candidate_coordinate_value_stream_sha256": (
                unique_candidate_hasher.hexdigest()
            ),
        },
        "unique_nonzero_product_bit_length_histogram": {
            str(key): value
            for key, value in sorted(product_height_histogram.items())
        },
        "maximum_unique_nonzero_profile": maximum_record,
        "extended_sparse_gauge_provenance": {
            "preregistration": preregistration_record,
            "external_p181_telemetry": external_telemetry_record,
            "p181_artifact": {
                "path": p181["path"],
                "sha256": p181["sha256"],
                "free_unknown_indices_sha256": EXPECTED_FREE_INDICES_SHA256,
                "pivot_unknown_set_sha256": EXPECTED_PIVOT_SET_SHA256,
                "ordered_pivot_unknown_indices_sha256": (
                    EXPECTED_P181_ORDERED_PIVOT_SHA256
                ),
            },
            "old_gauge": gauge_provenance,
            "region_partition_sha256": canonical_hash(gauge_regions),
            "regions": {
                name: {
                    "coordinate_count": len(indices),
                    "coordinate_set_sha256": canonical_hash(indices),
                }
                for name, indices in gauge_regions.items()
            },
            "outcome_cross_tab": gauge_cross_tab,
            "checks": {
                "old_and_new_gauges_encode_same_modular_problem": True,
                "regions_pairwise_disjoint": True,
                "regions_partition_all_38048_coordinates": True,
                "old_and_new_each_have_35881_pivots_and_2167_free": True,
                "exactly_258_old_pivots_became_free": True,
                "exactly_258_old_free_coordinates_became_pivots": True,
                "all_extended_sparse_p181_pivots_completed_without_dense_handoff": True,
            },
        },
        "benchmark_comparisons": comparisons,
        "inputs": {
            "artifacts_and_receipts": compact_inputs,
            "input_manifest_sha256": canonical_hash(compact_inputs),
            "total_input_bytes": sum(
                int(item["byte_count"]) + int(item["receipt_byte_count"])
                for item in compact_inputs
            ),
            "checks": {
                "source_characteristics_exact_and_ordered": True,
                "selector_characteristics_exact_and_ordered": True,
                "source_and_selector_sets_disjoint": True,
                "all_ten_artifact_and_receipt_hashes_exact": True,
                "all_five_modular_replays_exact": True,
                "all_five_fixed_free_gauge_sets_identical": True,
            },
        },
        "source_script": {
            "path": str(script_path),
            "sha256": file_sha256(script_path),
            "standalone": True,
            "imports_or_executes_frozen_dense_swap_producer": False,
        },
        "resources": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "load_and_validation_wall_seconds": load_seconds,
            "census_wall_seconds": census_seconds,
            "total_wall_seconds": time.perf_counter() - started_wall,
            "user_cpu_seconds": finished_usage.ru_utime - started_usage.ru_utime,
            "system_cpu_seconds": finished_usage.ru_stime - started_usage.ru_stime,
            "maximum_rss_native_self": finished_usage.ru_maxrss,
        },
        "completeness_statement": (
            "For each coordinate, every reduced n/d with d>0, gcd(d,M)=1, "
            "n=r*d mod M, and 2*abs(n)*d<M occurs among the tested Euclidean "
            "convergents by Legendre's theorem. The complete ordered candidate "
            "and post-selector stream hashes bind every enumerated pair."
        ),
        "claim_boundary": (
            "This is a complete bounded strict-product height census at one "
            "70-bit source modulus in the finite-field-compatible extended-"
            "sparse p181 fixed-free gauge. A surviving or unique candidate is "
            "not a reconstructed rational coefficient. No QQ multiplier "
            "identity is assembled or replayed, and no QQ colon, saturation, "
            "secant, nullcone, quartic Hessian, or HC4 statement is proved."
        ),
    }

    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    output_sha = file_sha256(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "output_sha256": output_sha,
                "source_script_sha256": result["source_script"]["sha256"],
                "source_characteristics": source_primes,
                "selector_characteristics": selector_primes,
                "source_modulus_bit_length": modulus.bit_length(),
                "coordinate_count": EXPECTED_COORDINATE_COUNT,
                "outcome": normalized_outcome,
                "gauge_outcome_cross_tab": gauge_cross_tab,
                "benchmark_outcome_deltas": {
                    item["benchmark"]["name"]: item[
                        "current_minus_benchmark_outcome_count_delta"
                    ]
                    for item in comparisons
                },
                "total_candidates_before_selectors": total_candidates,
                "total_wall_seconds": result["resources"]["total_wall_seconds"],
                "maximum_rss_native_self": result["resources"][
                    "maximum_rss_native_self"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
