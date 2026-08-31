#!/usr/bin/env python3
"""Independent ordinary-CF audit of the dense-pivot-swap M70 census.

The producer is read only as a result to compare.  This audit imports and
executes no campaign module.  It combines the three source residues by the
symmetric closed CRT formula, enumerates the complete strict-product region
from the proper convergents of the ordinary continued fraction of r/M, and
filters against p=173,197,199.  A small-modulus exhaustive test independently
checks the continued-fraction enumerator against the literal definition.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import resource
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parent.parent
ARTIFACTS = CAMPAIGN / "artifacts"
RECEIPTS = CAMPAIGN / "receipts"
PRODUCER_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-dense-pivot-swap-full-vector-m70-census.json"
)
PRODUCER_SCRIPT = CAMPAIGN / "scripts" / (
    "audit_j2_secant_r10_third_colon_dense_pivot_swap_full_vector_m70.py"
)
OUTPUT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-dense-pivot-swap-full-vector-"
    "m70-independent-audit.json"
)
OLD_GAUGE_ARTIFACT = ARTIFACTS / (
    "j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)
OLD_GAUGE_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)

EXPECTED_PRODUCER_RECEIPT_SHA256 = (
    "ede0ec6658eb8254a0cea833e8d185b2b3f19c736919905d09fea66db80f1bea"
)
EXPECTED_PRODUCER_SCRIPT_SHA256 = (
    "dbb7f47712fde75210146d3925442a6472e1444ac3c3a8265fcfc20b41c6e489"
)
EXPECTED_OLD_GAUGE_ARTIFACT_SHA256 = (
    "26be0a64574c3cdbe6f7d0c323f9a5e4beb9b8df8e568f9daa054744160bc0a1"
)
EXPECTED_OLD_GAUGE_RECEIPT_SHA256 = (
    "fe32cc53e81cf50e6c34881c5c61605938178a366986fae6ce872670aa9ddc6a"
)
EXPECTED_DENSE_GAUGE_ARTIFACT_SHA256 = (
    "c3e8c2e8f5bb514a3c53944c93a1051c1264323b11624c237217fde091672c3a"
)
EXPECTED_DENSE_GAUGE_RECEIPT_SHA256 = (
    "7765fbec47517b5f90c580b008aa6f3c0352324e23e11dec479d626d781e1798"
)
EXPECTED_FREE_HASH = (
    "3386466c85b77ce0ecffa5833142475c2906da9d5c8c00c87fc5132b097a163e"
)
EXPECTED_PIVOT_SET_HASH = (
    "12e15962e424e58435171e54c666e2ce898be55deebac38e01ece3dde14e4f2a"
)
EXPECTED_SOURCE_PRIMES = [181, 2147483647, 2147483629]
EXPECTED_SELECTOR_PRIMES = [173, 197, 199]
EXPECTED_MODULUS = 834715161561466408303
EXPECTED_COORDINATES = 38_048
EXPECTED_PIVOTS = 35_881
EXPECTED_FREE = 2_167
EXPECTED_OUTCOME = {
    "ambiguous": 0,
    "no_candidate": 19_844,
    "unique_nonzero": 544,
    "unique_zero": 17_660,
}
EXPECTED_MAXIMUM_PROFILE = {
    "coordinate": 8036,
    "denominator_bit_length": 12,
    "numerator_bit_length": 28,
    "positive_denominator": 3731,
    "reduced_numerator": -153792000,
    "twice_absolute_product": 1147595904000,
    "twice_product_bit_length": 41,
}
EXPECTED_INPUTS = [
    {
        "role": "source",
        "characteristic": 181,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json",
        "artifact_sha256": EXPECTED_DENSE_GAUGE_ARTIFACT_SHA256,
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json",
        "receipt_sha256": EXPECTED_DENSE_GAUGE_RECEIPT_SHA256,
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_DENSE_PIVOT_SWAP",
    },
    {
        "role": "source",
        "characteristic": 2147483647,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483647.json",
        "artifact_sha256": "a295cad917abe57ef90aa4209d48ef6579b3674393572c2fd0be059086361c84",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483647.json",
        "receipt_sha256": "c50219a3f5f2d8e24110faaf80e649bd282f52c7747fff23b334b3073f0004bd",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "source",
        "characteristic": 2147483629,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483629.json",
        "artifact_sha256": "9930c4b21e942a790b84ecf751e52604a4fb4a6656a50a824aad002d67aab51f",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483629.json",
        "receipt_sha256": "11d2f3989c045eab247110ebd43f6a7cc2c525d51b1d6a9785e9eea8b7cc0c85",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 173,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p173.json",
        "artifact_sha256": "0139a79fa28683226b54a9190668c49c143b891dfbdafce0a55285b645389ab4",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p173.json",
        "receipt_sha256": "bae335d9594128cdfd51200b298baf880021126c30acd210ae8acd16a0e3b962",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 197,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p197.json",
        "artifact_sha256": "7cf7c2adcde4eb65d609308a8b63863a4a574cb0cc3800446b2ee8756d4b4a07",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p197.json",
        "receipt_sha256": "383c034bcf1de8470d57c6d353c45fcdc4467426e206c2fdfa335bea76f4fce6",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 199,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p199.json",
        "artifact_sha256": "407b5042ce1496dfcfefa20860c2887c17f40c898d43f702cfcb469f2cb0d055",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p199.json",
        "receipt_sha256": "2dff6d2fc0a556eaeeb7ff3cbc4aed28d52bce7018878f62260bbe2294e1eb48",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
]
OUTCOME_LABELS = ("no_candidate", "ambiguous", "unique_zero", "unique_nonzero")


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


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


def replay_is_exact(receipt: dict[str, object], characteristic: int) -> bool:
    replay = (
        receipt.get("replay", {})
        if characteristic == 181
        else receipt.get("same_process_sparse_replay", {})
    )
    return bool(
        replay.get("completed")
        and replay.get("identity_zero")
        and int(replay.get("mismatch_count", -1)) == 0
        and replay.get("first_mismatch") is None
    )


def load_input(spec: dict[str, object]) -> dict[str, object]:
    artifact_path = Path(spec["artifact"]).resolve()
    receipt_path = Path(spec["receipt"]).resolve()
    artifact_hash = file_sha256(artifact_path)
    receipt_hash = file_sha256(receipt_path)
    if artifact_hash != spec["artifact_sha256"]:
        raise AssertionError(f"pinned artifact changed: {artifact_path}")
    if receipt_hash != spec["receipt_sha256"]:
        raise AssertionError(f"pinned receipt changed: {receipt_path}")
    artifact = json.loads(artifact_path.read_text(encoding="ascii"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    prime = int(spec["characteristic"])
    if int(artifact.get("characteristic", -1)) != prime:
        raise AssertionError(f"artifact characteristic mismatch: {artifact_path}")
    if int(receipt.get("characteristic", -1)) != prime:
        raise AssertionError(f"receipt characteristic mismatch: {receipt_path}")
    if not is_prime_32(prime):
        raise AssertionError(f"nonprime characteristic: {prime}")
    if receipt.get("status") != spec["receipt_status"]:
        raise AssertionError(f"nonpassing receipt: {receipt_path}")
    if not replay_is_exact(receipt, prime):
        raise AssertionError(f"receipt lacks exact replay: {receipt_path}")
    certificate_record = receipt.get("certificate", {})
    if (
        certificate_record.get("sha256") != artifact_hash
        or int(certificate_record.get("byte_count", -1)) != artifact_path.stat().st_size
        or Path(str(certificate_record.get("path", ""))).resolve() != artifact_path
    ):
        raise AssertionError(f"receipt does not bind artifact: {artifact_path}")

    vector = list(map(int, artifact["coordinate_vector"]))
    pivots = list(map(int, artifact["pivot_unknown_indices"]))
    free = list(map(int, artifact["free_unknown_indices"]))
    if (
        len(vector) != EXPECTED_COORDINATES
        or len(pivots) != EXPECTED_PIVOTS
        or len(free) != EXPECTED_FREE
    ):
        raise AssertionError(f"coordinate dimensions changed: {artifact_path}")
    if artifact.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise AssertionError(f"coordinate vector hash mismatch: {artifact_path}")
    if artifact.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise AssertionError(f"ordered pivot hash mismatch: {artifact_path}")
    if artifact.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise AssertionError(f"free hash mismatch: {artifact_path}")
    if artifact.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH:
        raise AssertionError(f"fixed free gauge changed: {artifact_path}")
    if (
        len(set(pivots)) != EXPECTED_PIVOTS
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != set(range(EXPECTED_COORDINATES))
    ):
        raise AssertionError(f"pivot/free partition failed: {artifact_path}")
    pivot_set_hash = canonical_hash(sorted(pivots))
    if pivot_set_hash != EXPECTED_PIVOT_SET_HASH:
        raise AssertionError(f"fixed pivot set changed: {artifact_path}")

    if prime != 181:
        gauge_source = artifact.get("gauge_source", {})
        receipt_gauge = receipt.get("gauge", {})
        solver = receipt.get("solver", {})
        if (
            int(gauge_source.get("characteristic", -1)) != 181
            or gauge_source.get("sha256") != EXPECTED_DENSE_GAUGE_ARTIFACT_SHA256
            or gauge_source.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH
            or gauge_source.get("pivot_unknown_set_sha256")
            != EXPECTED_PIVOT_SET_HASH
            or not receipt_gauge.get("coverage_verified")
            or receipt_gauge.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH
            or int(solver.get("pivot_count", -1)) != EXPECTED_PIVOTS
            or int(solver.get("free_unknown_count", -1)) != EXPECTED_FREE
            or not solver.get("completed")
            or not solver.get("consistent")
            or solver.get("timed_out")
        ):
            raise AssertionError(f"transfer gauge binding failed: {artifact_path}")

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
    signature["pivot_unknown_set_sha256"] = pivot_set_hash
    timings = receipt.get("timings", {})
    resources = receipt.get("resources", {})
    return {
        "role": spec["role"],
        "characteristic": prime,
        "path": str(artifact_path),
        "sha256": artifact_hash,
        "byte_count": artifact_path.stat().st_size,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_hash,
        "receipt_byte_count": receipt_path.stat().st_size,
        "receipt_status": receipt["status"],
        "receipt_wall_seconds": timings.get("wall_seconds"),
        "receipt_maximum_rss_native": resources.get("maximum_rss_native"),
        "vector": vector,
        "pivots": pivots,
        "free": free,
        "signature": signature,
    }


def direct_crt_weights(primes: list[int]) -> tuple[int, list[int]]:
    modulus = math.prod(primes)
    weights = []
    for prime in primes:
        partial = modulus // prime
        weights.append(partial * pow(partial % prime, -1, prime))
    return modulus, weights


def direct_crt(residues: list[int], weights: list[int], modulus: int) -> int:
    return sum(
        residue * weight
        for residue, weight in zip(residues, weights, strict=True)
    ) % modulus


def ordinary_cf_candidates(
    residue: int, modulus: int
) -> tuple[list[tuple[int, int]], int]:
    """Return every strict-product candidate from proper CF convergents."""

    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0

    terms: list[int] = []
    numerator, denominator = residue, modulus
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        terms.append(quotient)
        numerator, denominator = denominator, remainder

    h_minus_two, h_minus_one = 0, 1
    k_minus_two, k_minus_one = 1, 0
    candidates: set[tuple[int, int]] = set()
    proper_count = 0
    for index, term in enumerate(terms):
        h = term * h_minus_one + h_minus_two
        k = term * k_minus_one + k_minus_two
        h_minus_two, h_minus_one = h_minus_one, h
        k_minus_two, k_minus_one = k_minus_one, k
        if index + 1 == len(terms):
            break
        proper_count += 1
        candidate_numerator = residue * k - modulus * h
        candidate_denominator = k
        if candidate_denominator < 0:
            candidate_numerator = -candidate_numerator
            candidate_denominator = -candidate_denominator
        common = math.gcd(abs(candidate_numerator), candidate_denominator)
        candidate_numerator //= common
        candidate_denominator //= common
        if (
            candidate_denominator > 0
            and math.gcd(candidate_denominator, modulus) == 1
            and 2 * abs(candidate_numerator) * candidate_denominator < modulus
            and (candidate_numerator - residue * candidate_denominator) % modulus == 0
        ):
            candidates.add((candidate_numerator, candidate_denominator))
    return sorted(candidates), proper_count


def brute_force_candidates(residue: int, modulus: int) -> list[tuple[int, int]]:
    """Literal finite definition, used only for the small-modulus self-test."""

    candidates = set()
    for denominator in range(1, modulus + 1):
        if math.gcd(denominator, modulus) != 1:
            continue
        least_residue = residue * denominator % modulus
        for numerator in {least_residue, least_residue - modulus}:
            if (
                math.gcd(abs(numerator), denominator) == 1
                and 2 * abs(numerator) * denominator < modulus
                and (numerator - residue * denominator) % modulus == 0
            ):
                candidates.add((numerator, denominator))
    return sorted(candidates)


def run_cf_self_test() -> dict[str, object]:
    tested_pairs = 0
    transcript = hashlib.sha256()
    for modulus in range(2, 100):
        for residue in range(modulus):
            tested_pairs += 1
            observed, _proper = ordinary_cf_candidates(residue, modulus)
            expected = brute_force_candidates(residue, modulus)
            if observed != expected:
                raise AssertionError(
                    f"ordinary-CF self-test failed at M={modulus}, r={residue}"
                )
            transcript.update(
                f"{modulus}:{residue}:{observed}\n".encode("ascii")
            )
    return {
        "status": "PASS",
        "modulus_range_inclusive": [2, 99],
        "residue_modulus_pairs_tested": tested_pairs,
        "comparison": "ordinary-CF candidates equal literal brute-force candidates",
        "transcript_sha256": transcript.hexdigest(),
    }


def derive_regions(
    dense_source: dict[str, object], constructor_receipt: dict[str, object]
) -> tuple[dict[str, list[int]], dict[str, bool]]:
    if file_sha256(OLD_GAUGE_ARTIFACT) != EXPECTED_OLD_GAUGE_ARTIFACT_SHA256:
        raise AssertionError("old-gauge artifact changed")
    if file_sha256(OLD_GAUGE_RECEIPT) != EXPECTED_OLD_GAUGE_RECEIPT_SHA256:
        raise AssertionError("old-gauge receipt changed")
    old_artifact = json.loads(OLD_GAUGE_ARTIFACT.read_text(encoding="ascii"))
    old_receipt = json.loads(OLD_GAUGE_RECEIPT.read_text(encoding="utf-8"))
    old_pivots = list(map(int, old_artifact["pivot_unknown_indices"]))
    old_free = list(map(int, old_artifact["free_unknown_indices"]))
    if (
        old_artifact.get("pivot_unknown_indices_sha256") != canonical_hash(old_pivots)
        or old_artifact.get("free_unknown_indices_sha256") != canonical_hash(old_free)
        or old_receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        or old_receipt.get("certificate", {}).get("sha256")
        != EXPECTED_OLD_GAUGE_ARTIFACT_SHA256
    ):
        raise AssertionError("old gauge provenance failed")
    source = constructor_receipt.get("source", {})
    if (
        Path(str(source.get("artifact", ""))).resolve() != OLD_GAUGE_ARTIFACT.resolve()
        or source.get("artifact_sha256") != EXPECTED_OLD_GAUGE_ARTIFACT_SHA256
        or Path(str(source.get("receipt", ""))).resolve() != OLD_GAUGE_RECEIPT.resolve()
        or source.get("receipt_sha256") != EXPECTED_OLD_GAUGE_RECEIPT_SHA256
    ):
        raise AssertionError("constructor receipt does not bind old gauge")

    dimensions = constructor_receipt["frozen_dimensions"]
    swap = constructor_receipt["dense_swap"]
    sparse_count = int(dimensions["sparse_prefix_count"])
    dense_count = int(dimensions["old_dense_pivot_count"])
    if sparse_count != 35_300 or dense_count != 581:
        raise AssertionError("constructor split changed")
    sparse_ordered = old_pivots[:sparse_count]
    zeroed_ordered = old_pivots[sparse_count:]
    promoted_ordered = list(map(int, swap["selected_old_free_indices"]))
    if (
        canonical_hash(sparse_ordered) != dimensions["sparse_prefix_sha256"]
        or canonical_hash(zeroed_ordered)
        != swap["zeroed_old_dense_pivot_indices_sha256"]
        or canonical_hash(promoted_ordered) != swap["selected_old_free_indices_sha256"]
    ):
        raise AssertionError("constructor region hashes changed")

    regions = {
        "promoted_dense_tail_pivots": sorted(promoted_ordered),
        "zeroed_old_dense_pivots": sorted(zeroed_ordered),
        "frozen_sparse_prefix_pivots": sorted(sparse_ordered),
        "remaining_free_coordinates": sorted(set(old_free) - set(promoted_ordered)),
    }
    region_sets = {name: set(values) for name, values in regions.items()}
    pairwise_disjoint = all(
        not region_sets[left] & region_sets[right]
        for left_index, left in enumerate(regions)
        for right in list(regions)[left_index + 1 :]
    )
    full_partition = set().union(*region_sets.values()) == set(
        range(EXPECTED_COORDINATES)
    )
    new_pivots = list(map(int, dense_source["pivots"]))
    new_free = set(map(int, dense_source["free"]))
    checks = {
        "regions_pairwise_disjoint": pairwise_disjoint,
        "regions_partition_all_coordinates": full_partition,
        "new_sparse_prefix_preserved_order": new_pivots[:sparse_count]
        == sparse_ordered,
        "new_dense_tail_is_promoted_set": set(new_pivots[sparse_count:])
        == region_sets["promoted_dense_tail_pivots"],
        "new_free_is_zeroed_plus_remaining": new_free
        == region_sets["zeroed_old_dense_pivots"]
        | region_sets["remaining_free_coordinates"],
        "old_free_is_promoted_plus_remaining": set(old_free)
        == region_sets["promoted_dense_tail_pivots"]
        | region_sets["remaining_free_coordinates"],
    }
    if not all(checks.values()):
        raise AssertionError(f"region derivation failed: {checks}")
    return regions, checks


def compact_input(item: dict[str, object]) -> dict[str, object]:
    return {
        "role": item["role"],
        "characteristic": item["characteristic"],
        "path": item["path"],
        "sha256": item["sha256"],
        "byte_count": item["byte_count"],
        "receipt_path": item["receipt_path"],
        "receipt_sha256": item["receipt_sha256"],
        "receipt_byte_count": item["receipt_byte_count"],
        "receipt_status": item["receipt_status"],
        "receipt_wall_seconds": item["receipt_wall_seconds"],
        "receipt_maximum_rss_native": item["receipt_maximum_rss_native"],
    }


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    if file_sha256(PRODUCER_RECEIPT) != EXPECTED_PRODUCER_RECEIPT_SHA256:
        raise AssertionError("producer census receipt changed")
    if file_sha256(PRODUCER_SCRIPT) != EXPECTED_PRODUCER_SCRIPT_SHA256:
        raise AssertionError("producer census script changed")
    producer = json.loads(PRODUCER_RECEIPT.read_text(encoding="utf-8"))
    if (
        producer.get("status")
        != "PASS_BOUNDED_DENSE_PIVOT_SWAP_FULL_VECTOR_M70_CENSUS"
    ):
        raise AssertionError("producer census is not passing")

    cf_self_test = run_cf_self_test()
    inputs = [load_input(spec) for spec in EXPECTED_INPUTS]
    sources = [item for item in inputs if item["role"] == "source"]
    selectors = [item for item in inputs if item["role"] == "selector"]
    source_primes = [int(item["characteristic"]) for item in sources]
    selector_primes = [int(item["characteristic"]) for item in selectors]
    if source_primes != EXPECTED_SOURCE_PRIMES:
        raise AssertionError("source-prime order changed")
    if selector_primes != EXPECTED_SELECTOR_PRIMES:
        raise AssertionError("selector-prime order changed")
    signatures = {canonical_hash(item["signature"]) for item in inputs}
    if len(signatures) != 1:
        raise AssertionError("fixed-gauge problem signatures differ")
    signature_hash = next(iter(signatures))

    dense_source = sources[0]
    constructor_receipt = json.loads(
        Path(str(dense_source["receipt_path"])).read_text(encoding="utf-8")
    )
    regions, region_checks = derive_regions(dense_source, constructor_receipt)

    modulus, crt_weights = direct_crt_weights(source_primes)
    if modulus != EXPECTED_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("direct CRT modulus is not the frozen M70 modulus")
    if any(
        weight % own_prime != 1
        or any(
            weight % other_prime
            for other_prime in source_primes
            if other_prime != own_prime
        )
        for own_prime, weight in zip(source_primes, crt_weights, strict=True)
    ):
        raise AssertionError("direct CRT basis is invalid")

    outcome = collections.Counter()
    outcome_coordinates = {label: [] for label in OUTCOME_LABELS}
    outcome_label_vector: list[str] = []
    candidate_histogram = collections.Counter()
    survivor_histogram = collections.Counter()
    height_histogram = collections.Counter()
    candidate_counts: list[int] = []
    survivor_counts: list[int] = []
    combined_residues: list[str] = []
    selector_survivor_totals = [0] * len(selectors)
    selector_nonempty_counts = [0] * len(selectors)
    total_candidates = 0
    total_proper_convergents = 0
    all_source_zero_count = 0
    maximum_profile = None
    candidate_stream_hasher = hashlib.sha256()
    survivor_stream_hasher = hashlib.sha256()
    unique_candidate_hasher = hashlib.sha256()

    census_started = time.perf_counter()
    for coordinate in range(EXPECTED_COORDINATES):
        residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        all_source_zero_count += not any(residues)
        combined = direct_crt(residues, crt_weights, modulus)
        if any(combined % prime != residue for prime, residue in zip(source_primes, residues, strict=True)):
            raise AssertionError(f"CRT reduction failed at coordinate {coordinate}")
        combined_residues.append(str(combined))
        candidates, proper_count = ordinary_cf_candidates(combined, modulus)
        total_proper_convergents += proper_count
        total_candidates += len(candidates)
        candidate_counts.append(len(candidates))
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
                and numerator % prime * pow(denominator % prime, -1, prime) % prime
                == observed
            ]
            selector_survivor_totals[selector_index] += len(survivors)
            selector_nonempty_counts[selector_index] += bool(survivors)

        survivor_counts.append(len(survivors))
        survivor_histogram[len(survivors)] += 1
        survivor_stream_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in survivors:
            survivor_stream_hasher.update(
                f"{numerator}/{denominator};".encode("ascii")
            )
        survivor_stream_hasher.update(b"\n")

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
                height_histogram[product_bits] += 1
                profile = (
                    product_bits,
                    abs(numerator).bit_length(),
                    denominator.bit_length(),
                    coordinate,
                    numerator,
                    denominator,
                )
                if maximum_profile is None or profile > maximum_profile:
                    maximum_profile = profile
        outcome[label] += 1
        outcome_coordinates[label].append(coordinate)
        outcome_label_vector.append(label)
    census_seconds = time.perf_counter() - census_started

    if sum(outcome.values()) != EXPECTED_COORDINATES:
        raise AssertionError("outcome census does not cover all coordinates")
    maximum_record = None
    if maximum_profile is not None:
        product_bits, numerator_bits, denominator_bits, coordinate, numerator, denominator = maximum_profile
        maximum_record = {
            "coordinate": coordinate,
            "reduced_numerator": numerator,
            "positive_denominator": denominator,
            "twice_absolute_product": 2 * abs(numerator) * denominator,
            "twice_product_bit_length": product_bits,
            "numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }

    outcome_sets = {
        label: set(coordinates) for label, coordinates in outcome_coordinates.items()
    }
    cross_tab = {}
    for region_name, coordinates in regions.items():
        coordinate_set = set(coordinates)
        cross_tab[region_name] = {
            "coordinate_count": len(coordinates),
            "coordinate_set_sha256": canonical_hash(coordinates),
            "outcome": {
                label: len(coordinate_set & outcome_sets[label])
                for label in OUTCOME_LABELS
            },
        }
    for label in OUTCOME_LABELS:
        if sum(row["outcome"][label] for row in cross_tab.values()) != outcome[label]:
            raise AssertionError(f"cross-tab column failed: {label}")

    independent_candidate_enumeration = {
        "total_candidates_before_selectors": total_candidates,
        "total_proper_continued_fraction_convergents": total_proper_convergents,
        "all_source_residues_zero_coordinate_count": all_source_zero_count,
        "candidate_count_histogram": {
            str(key): value for key, value in sorted(candidate_histogram.items())
        },
        "candidate_count_vector_sha256": canonical_hash(candidate_counts),
        "candidate_stream_sha256": candidate_stream_hasher.hexdigest(),
        "combined_crt_residue_vector_sha256": canonical_hash(combined_residues),
    }
    selector_aggregates = [
        {
            "characteristic": selector["characteristic"],
            "survivor_count_sum_after_selector": selector_survivor_totals[index],
            "coordinates_with_a_survivor_after_selector": selector_nonempty_counts[index],
        }
        for index, selector in enumerate(selectors)
    ]
    independent_selector_filtering = {
        "aggregates": selector_aggregates,
        "final_survivor_count_histogram": {
            str(key): value for key, value in sorted(survivor_histogram.items())
        },
        "final_survivor_count_vector_sha256": canonical_hash(survivor_counts),
        "final_survivor_stream_sha256": survivor_stream_hasher.hexdigest(),
        "unique_candidate_coordinate_value_stream_sha256": unique_candidate_hasher.hexdigest(),
    }
    outcome_dict = {label: outcome[label] for label in sorted(EXPECTED_OUTCOME)}
    outcome_hashes = {
        label: canonical_hash(outcome_coordinates[label])
        for label in sorted(outcome_coordinates)
    }
    height_histogram_dict = {
        str(key): value for key, value in sorted(height_histogram.items())
    }

    producer_candidate = producer["candidate_enumeration"]
    producer_selector = producer["selector_filtering"]
    producer_checks = {
        "source_modulus_exact": str(modulus) == producer["source_modulus"],
        "source_modulus_bits_exact": modulus.bit_length()
        == producer["source_modulus_bit_length"],
        "source_primes_exact": source_primes == producer["source_characteristics"],
        "selector_primes_exact": selector_primes
        == producer["selector_characteristics"],
        "fixed_gauge_signature_exact": signature_hash
        == producer["fixed_gauge_signature_sha256"],
        "outcome_exact": outcome_dict == producer["outcome"] == EXPECTED_OUTCOME,
        "outcome_coordinate_lists_exact": all(
            outcome_coordinates[label] == producer["coordinates_by_outcome"][label]
            for label in outcome_coordinates
        ),
        "outcome_coordinate_hashes_exact": outcome_hashes
        == producer["coordinates_by_outcome_sha256"],
        "total_candidates_exact": total_candidates
        == producer_candidate["total_candidates_before_selectors"],
        "proper_cf_count_equals_producer_eea_steps": total_proper_convergents
        == producer_candidate["total_extended_euclid_steps"],
        "all_source_zero_count_exact": all_source_zero_count
        == producer_candidate["all_source_residues_zero_coordinate_count"],
        "candidate_histogram_exact": independent_candidate_enumeration[
            "candidate_count_histogram"
        ]
        == producer_candidate["candidate_count_histogram"],
        "candidate_count_vector_hash_exact": independent_candidate_enumeration[
            "candidate_count_vector_sha256"
        ]
        == producer_candidate["candidate_count_vector_sha256"],
        "candidate_stream_hash_exact": independent_candidate_enumeration[
            "candidate_stream_sha256"
        ]
        == producer_candidate["candidate_stream_sha256"],
        "combined_crt_stream_hash_exact": independent_candidate_enumeration[
            "combined_crt_residue_vector_sha256"
        ]
        == producer_candidate["combined_crt_residue_vector_sha256"],
        "selector_filtering_exact": independent_selector_filtering
        == producer_selector,
        "height_histogram_exact": height_histogram_dict
        == producer["unique_nonzero_product_bit_length_histogram"],
        "maximum_profile_exact": maximum_record
        == producer["maximum_unique_nonzero_profile"]
        == EXPECTED_MAXIMUM_PROFILE,
        "region_partition_hash_exact": canonical_hash(regions)
        == producer["dense_pivot_swap_provenance"]["region_partition_sha256"],
        "region_records_exact": {
            name: {
                "coordinate_count": len(values),
                "coordinate_set_sha256": canonical_hash(values),
            }
            for name, values in regions.items()
        }
        == producer["dense_pivot_swap_provenance"]["regions"],
        "four_region_cross_tab_exact": cross_tab
        == producer["dense_pivot_swap_provenance"]["outcome_cross_tab"],
    }

    compact_inputs = [compact_input(item) for item in inputs]
    input_checks = {
        "producer_input_manifest_exact": canonical_hash(compact_inputs)
        == producer["inputs"]["input_manifest_sha256"],
        "producer_input_byte_total_exact": sum(
            int(item["byte_count"]) + int(item["receipt_byte_count"])
            for item in compact_inputs
        )
        == producer["inputs"]["total_input_bytes"],
        "all_six_artifact_receipt_pairs_bound": len(inputs) == 6,
        "producer_receipt_hash_pinned": file_sha256(PRODUCER_RECEIPT)
        == EXPECTED_PRODUCER_RECEIPT_SHA256,
        "producer_script_hash_pinned": file_sha256(PRODUCER_SCRIPT)
        == EXPECTED_PRODUCER_SCRIPT_SHA256,
    }
    if not all(producer_checks.values()) or not all(input_checks.values()):
        raise AssertionError(
            "independent census comparison failed: "
            f"producer={producer_checks}, inputs={input_checks}"
        )

    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.third-colon-dense-pivot-swap-full-vector-m70-independent-audit.v1",
        "status": "PASS_INDEPENDENT_DENSE_PIVOT_SWAP_FULL_VECTOR_M70_CENSUS",
        "independence": {
            "language_runtime": "Python standard library only",
            "campaign_module_imports": [],
            "crt_method": (
                "symmetric direct CRT sum using independently computed "
                "M_i*(M_i^-1 mod p_i) basis weights"
            ),
            "candidate_method": (
                "ordinary simple continued fraction of r/M; test every proper "
                "convergent with n=r*q-M*p and the strict-product inequality"
            ),
            "candidate_completeness_self_test": cf_self_test,
            "producer_candidate_function_imported": False,
            "producer_script_executed": False,
            "heavy_algebra_executed": False,
        },
        "coordinate_count": EXPECTED_COORDINATES,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "source_characteristics": source_primes,
        "selector_characteristics": selector_primes,
        "direct_crt_basis_weights_sha256": canonical_hash(
            [str(value) for value in crt_weights]
        ),
        "fixed_gauge_signature_sha256": signature_hash,
        "outcome": outcome_dict,
        "outcome_label_vector_sha256": canonical_hash(outcome_label_vector),
        "coordinates_by_outcome_sha256": outcome_hashes,
        "candidate_enumeration": independent_candidate_enumeration,
        "selector_filtering": independent_selector_filtering,
        "unique_nonzero_product_bit_length_histogram": height_histogram_dict,
        "maximum_unique_nonzero_profile": maximum_record,
        "dense_pivot_swap_provenance": {
            "region_partition_sha256": canonical_hash(regions),
            "regions": {
                name: {
                    "coordinate_count": len(values),
                    "coordinate_set_sha256": canonical_hash(values),
                }
                for name, values in regions.items()
            },
            "outcome_cross_tab": cross_tab,
            "checks": region_checks,
            "old_gauge_artifact": {
                "path": str(OLD_GAUGE_ARTIFACT),
                "sha256": EXPECTED_OLD_GAUGE_ARTIFACT_SHA256,
            },
            "old_gauge_receipt": {
                "path": str(OLD_GAUGE_RECEIPT),
                "sha256": EXPECTED_OLD_GAUGE_RECEIPT_SHA256,
            },
        },
        "producer_comparison": producer_checks,
        "input_checks": input_checks,
        "inputs": {
            "producer_receipt": {
                "path": str(PRODUCER_RECEIPT),
                "sha256": EXPECTED_PRODUCER_RECEIPT_SHA256,
            },
            "producer_script_read_not_imported_or_executed": {
                "path": str(PRODUCER_SCRIPT),
                "sha256": EXPECTED_PRODUCER_SCRIPT_SHA256,
            },
            "artifacts_and_receipts": compact_inputs,
            "input_manifest_sha256": canonical_hash(compact_inputs),
        },
        "script": {
            "path": str(script_path.relative_to(CAMPAIGN)),
            "sha256": file_sha256(script_path),
        },
        "resources": {
            "census_wall_seconds": census_seconds,
            "total_wall_seconds": time.perf_counter() - started,
            "maximum_rss_native_self": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "completeness_statement": (
            "For a reduced strict-product candidate n/d, k=(r*d-n)/M gives "
            "|r/M-k/d|<1/(2*d^2); by Legendre's theorem k/d is a proper "
            "ordinary continued-fraction convergent of r/M. This audit tested "
            "every proper convergent and independently matched the formulation "
            "to literal brute force for every residue modulo every M from 2 to 99."
        ),
        "claim_boundary": (
            "A PASS independently verifies only the complete bounded strict-product "
            "candidate census at the 70-bit source modulus in this frozen finite-"
            "field-compatible dense-pivot-swap gauge. A surviving or unique "
            "candidate is not a reconstructed rational coefficient. This audit "
            "does not assemble or replay a QQ identity, validate rational "
            "multipliers, compute a colon or saturation, close the secant chart, "
            "prove nullcone containment, or establish HC4."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT),
                "outcome": outcome_dict,
                "maximum_unique_nonzero_profile": maximum_record,
                "outcome_cross_tab": cross_tab,
                "candidate_stream_sha256": independent_candidate_enumeration[
                    "candidate_stream_sha256"
                ],
                "wall_seconds": result["resources"]["total_wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
