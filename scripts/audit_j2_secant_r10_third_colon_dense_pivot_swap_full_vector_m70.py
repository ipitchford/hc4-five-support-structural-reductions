#!/usr/bin/env python3
"""Complete M70 height census for the dense-pivot-swap third-colon gauge.

The frozen source modulus is

    M = 181 * 2147483647 * 2147483629,

and p=173,197,199 are selectors only.  For every one of the 38,048
multiplier coordinates, this script enumerates every reduced fraction n/d
with

    d > 0, gcd(d, M) = 1, n = r*d (mod M), 2*abs(n)*d < M,

then filters those candidates against the three selectors.  It also derives
and checks the four coordinate regions created by the 581-column dense pivot
swap and reports a full outcome cross-tab for those regions.

This is deliberately a bounded modular height census.  It neither performs
nor claims rational reconstruction over QQ.
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

EXPECTED_SOURCE_PRIMES = [181, 2147483647, 2147483629]
EXPECTED_SELECTOR_PRIMES = [173, 197, 199]
EXPECTED_SOURCE_MODULUS = 834715161561466408303
EXPECTED_SOURCE_MODULUS_BITS = 70
EXPECTED_COORDINATE_COUNT = 38048
EXPECTED_PIVOT_COUNT = 35881
EXPECTED_FREE_COUNT = 2167

P181_ARTIFACT = ARTIFACTS / (
    "j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json"
)
P181_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json"
)
EXPECTED_P181_ARTIFACT_SHA256 = (
    "c3e8c2e8f5bb514a3c53944c93a1051c1264323b11624c237217fde091672c3a"
)
EXPECTED_P181_RECEIPT_SHA256 = (
    "7765fbec47517b5f90c580b008aa6f3c0352324e23e11dec479d626d781e1798"
)
EXPECTED_FREE_INDICES_SHA256 = (
    "3386466c85b77ce0ecffa5833142475c2906da9d5c8c00c87fc5132b097a163e"
)
EXPECTED_PIVOT_SET_SHA256 = (
    "12e15962e424e58435171e54c666e2ce898be55deebac38e01ece3dde14e4f2a"
)

INPUT_SPECS = [
    {
        "role": "source",
        "characteristic": 181,
        "artifact": P181_ARTIFACT,
        "receipt": P181_RECEIPT,
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_DENSE_PIVOT_SWAP",
    },
    {
        "role": "source",
        "characteristic": 2147483647,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483647.json",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483647.json",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "source",
        "characteristic": 2147483629,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483629.json",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p2147483629.json",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 173,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p173.json",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p173.json",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 197,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p197.json",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p197.json",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
    {
        "role": "selector",
        "characteristic": 199,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p199.json",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-transfer-p199.json",
        "receipt_status": "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
    },
]

DEFAULT_OUTPUT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-dense-pivot-swap-full-vector-m70-census.json"
)

OUTCOME_LABELS = (
    "no_candidate",
    "ambiguous",
    "unique_zero",
    "unique_nonzero",
)

EXPECTED_REGION_PROVENANCE = {
    "promoted_dense_tail_pivots": {
        "coordinate_count": 581,
        "coordinate_set_sha256": (
            "c4954da2bfe11858af5548be09c4ddeb12744b8f763addabb431d5e355def5e6"
        ),
    },
    "zeroed_old_dense_pivots": {
        "coordinate_count": 581,
        "coordinate_set_sha256": (
            "d87f9ff9ddb60dcc484243294483ff2db0e853de03bdef2e0315a5707c5f76e0"
        ),
    },
    "frozen_sparse_prefix_pivots": {
        "coordinate_count": 35300,
        "coordinate_set_sha256": (
            "d205f63038c2d25aaf1d3660666d81eeaded2bf141082317f4bbc626044fd11a"
        ),
        "ordered_provenance_sha256": (
            "e5c9b7644bbe1745db44c6380e8d16d9be6ec2cc8646bdbbb6b8ddafe3acdfde"
        ),
    },
    "remaining_free_coordinates": {
        "coordinate_count": 1586,
        "coordinate_set_sha256": (
            "9a45b483f9095e62f54b6fc182cc15da21673dc0b5742a1ce03f6f2170fab054"
        ),
    },
}


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


def replay_passes(receipt: dict[str, object], characteristic: int) -> bool:
    if characteristic == 181:
        replay = receipt.get("replay", {})
    else:
        replay = receipt.get("same_process_sparse_replay", {})
    return bool(
        replay.get("completed")
        and replay.get("identity_zero")
        and int(replay.get("mismatch_count", -1)) == 0
        and replay.get("first_mismatch") is None
    )


def load_input(spec: dict[str, object]) -> dict[str, object]:
    artifact_path = Path(spec["artifact"]).resolve()
    receipt_path = Path(spec["receipt"]).resolve()
    if not artifact_path.is_file():
        raise FileNotFoundError(f"pending modular artifact is absent: {artifact_path}")
    if not receipt_path.is_file():
        raise FileNotFoundError(f"pending modular receipt is absent: {receipt_path}")

    artifact_sha = file_sha256(artifact_path)
    receipt_sha = file_sha256(receipt_path)
    artifact = json.loads(artifact_path.read_text(encoding="ascii"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    characteristic = int(spec["characteristic"])

    if int(artifact["characteristic"]) != characteristic:
        raise AssertionError(f"artifact characteristic mismatch: {artifact_path}")
    if int(receipt["characteristic"]) != characteristic:
        raise AssertionError(f"receipt characteristic mismatch: {receipt_path}")
    if not is_prime_32(characteristic):
        raise AssertionError(f"nonprime characteristic: {characteristic}")
    if receipt.get("status") != spec["receipt_status"]:
        raise AssertionError(f"nonpassing modular receipt: {receipt_path}")
    if not replay_passes(receipt, characteristic):
        raise AssertionError(f"modular replay is not exact: {receipt_path}")

    certificate = receipt.get("certificate", {})
    if certificate.get("sha256") != artifact_sha:
        raise AssertionError(f"receipt does not bind artifact hash: {artifact_path}")
    if int(certificate.get("byte_count", -1)) != artifact_path.stat().st_size:
        raise AssertionError(f"receipt does not bind artifact size: {artifact_path}")
    if Path(str(certificate.get("path", ""))).resolve() != artifact_path:
        raise AssertionError(f"receipt certificate path mismatch: {receipt_path}")

    vector = list(map(int, artifact["coordinate_vector"]))
    pivots = list(map(int, artifact["pivot_unknown_indices"]))
    free = list(map(int, artifact["free_unknown_indices"]))
    if len(vector) != EXPECTED_COORDINATE_COUNT:
        raise AssertionError(f"coordinate-vector length mismatch: {artifact_path}")
    if len(pivots) != EXPECTED_PIVOT_COUNT or len(free) != EXPECTED_FREE_COUNT:
        raise AssertionError(f"pivot/free count mismatch: {artifact_path}")
    if artifact.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise AssertionError(f"coordinate-vector hash mismatch: {artifact_path}")
    if artifact.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise AssertionError(f"ordered-pivot hash mismatch: {artifact_path}")
    if artifact.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise AssertionError(f"free-coordinate hash mismatch: {artifact_path}")
    if artifact.get("free_unknown_indices_sha256") != EXPECTED_FREE_INDICES_SHA256:
        raise AssertionError(f"dense-swap free gauge changed: {artifact_path}")

    coordinate_universe = set(range(EXPECTED_COORDINATE_COUNT))
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != coordinate_universe
    ):
        raise AssertionError(f"invalid pivot/free partition: {artifact_path}")
    pivot_set_sha = canonical_hash(sorted(pivots))
    if pivot_set_sha != EXPECTED_PIVOT_SET_SHA256:
        raise AssertionError(f"dense-swap pivot set changed: {artifact_path}")

    if characteristic == 181:
        if artifact_sha != EXPECTED_P181_ARTIFACT_SHA256:
            raise AssertionError("the frozen p181 dense-swap artifact changed")
        if receipt_sha != EXPECTED_P181_RECEIPT_SHA256:
            raise AssertionError("the frozen p181 dense-swap receipt changed")
    else:
        gauge_source = artifact.get("gauge_source", {})
        if (
            int(gauge_source.get("characteristic", -1)) != 181
            or gauge_source.get("sha256") != EXPECTED_P181_ARTIFACT_SHA256
            or gauge_source.get("free_unknown_indices_sha256")
            != EXPECTED_FREE_INDICES_SHA256
            or gauge_source.get("pivot_unknown_set_sha256")
            != EXPECTED_PIVOT_SET_SHA256
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
            raise AssertionError(f"transfer gauge/solver audit failed: {receipt_path}")

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
    receipt_timings = receipt.get("timings", {})
    receipt_resources = receipt.get("resources", {})
    return {
        "role": str(spec["role"]),
        "path": str(artifact_path),
        "sha256": artifact_sha,
        "byte_count": artifact_path.stat().st_size,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_sha,
        "receipt_byte_count": receipt_path.stat().st_size,
        "receipt_status": receipt["status"],
        "receipt_wall_seconds": receipt_timings.get("wall_seconds"),
        "receipt_maximum_rss_native": receipt_resources.get(
            "maximum_rss_native"
        ),
        "characteristic": characteristic,
        "vector": vector,
        "pivots": pivots,
        "free": free,
        "signature": signature,
    }


def derive_coordinate_regions(p181: dict[str, object]) -> dict[str, list[int]]:
    constructor_hash = file_sha256(P181_RECEIPT)
    if constructor_hash != EXPECTED_P181_RECEIPT_SHA256:
        raise AssertionError("constructor receipt changed during region derivation")
    constructor = json.loads(P181_RECEIPT.read_text(encoding="utf-8"))
    old_source = constructor.get("source", {})
    old_path = Path(str(old_source.get("artifact", ""))).resolve()
    if not old_path.is_file() or file_sha256(old_path) != old_source.get(
        "artifact_sha256"
    ):
        raise AssertionError("constructor no longer binds its old-gauge artifact")
    old_artifact = json.loads(old_path.read_text(encoding="ascii"))
    old_pivots = list(map(int, old_artifact["pivot_unknown_indices"]))
    old_free = list(map(int, old_artifact["free_unknown_indices"]))
    if old_artifact.get("pivot_unknown_indices_sha256") != canonical_hash(old_pivots):
        raise AssertionError("old-gauge ordered-pivot hash mismatch")
    if old_artifact.get("free_unknown_indices_sha256") != canonical_hash(old_free):
        raise AssertionError("old-gauge free-coordinate hash mismatch")

    dimensions = constructor.get("frozen_dimensions", {})
    swap = constructor.get("dense_swap", {})
    sparse_count = int(dimensions.get("sparse_prefix_count", -1))
    dense_count = int(dimensions.get("old_dense_pivot_count", -1))
    if sparse_count != 35300 or dense_count != 581:
        raise AssertionError("constructor dense-swap dimensions changed")
    if len(old_pivots) != sparse_count + dense_count:
        raise AssertionError("old pivot list does not split at the dense handoff")

    sparse_ordered = old_pivots[:sparse_count]
    zeroed_ordered = old_pivots[sparse_count:]
    promoted_ordered = list(map(int, swap.get("selected_old_free_indices", [])))
    if len(promoted_ordered) != dense_count:
        raise AssertionError("constructor did not record 581 promoted coordinates")
    if canonical_hash(sparse_ordered) != dimensions.get("sparse_prefix_sha256"):
        raise AssertionError("constructor sparse-prefix provenance hash mismatch")
    if canonical_hash(zeroed_ordered) != swap.get(
        "zeroed_old_dense_pivot_indices_sha256"
    ):
        raise AssertionError("constructor old dense-pivot provenance hash mismatch")
    if canonical_hash(promoted_ordered) != swap.get(
        "selected_old_free_indices_sha256"
    ):
        raise AssertionError("constructor promoted-coordinate provenance hash mismatch")

    sparse = sorted(sparse_ordered)
    zeroed = sorted(zeroed_ordered)
    promoted = sorted(promoted_ordered)
    used = set(sparse) | set(zeroed) | set(promoted)
    remaining = sorted(set(range(EXPECTED_COORDINATE_COUNT)) - used)
    regions = {
        "promoted_dense_tail_pivots": promoted,
        "zeroed_old_dense_pivots": zeroed,
        "frozen_sparse_prefix_pivots": sparse,
        "remaining_free_coordinates": remaining,
    }

    region_sets = {name: set(indices) for name, indices in regions.items()}
    names = list(region_sets)
    for left_index, left_name in enumerate(names):
        for right_name in names[left_index + 1 :]:
            if region_sets[left_name] & region_sets[right_name]:
                raise AssertionError(f"coordinate regions overlap: {left_name}, {right_name}")
    if set().union(*region_sets.values()) != set(range(EXPECTED_COORDINATE_COUNT)):
        raise AssertionError("coordinate regions do not cover all coordinates")

    p181_pivots = list(map(int, p181["pivots"]))
    p181_free = set(map(int, p181["free"]))
    if p181_pivots[:sparse_count] != sparse_ordered:
        raise AssertionError("new gauge does not retain the frozen sparse prefix")
    if set(p181_pivots[sparse_count:]) != region_sets[
        "promoted_dense_tail_pivots"
    ]:
        raise AssertionError("new dense tail is not exactly the promoted set")
    if p181_free != (
        region_sets["zeroed_old_dense_pivots"]
        | region_sets["remaining_free_coordinates"]
    ):
        raise AssertionError("new free set does not split into the two requested regions")
    if set(old_free) != (
        region_sets["promoted_dense_tail_pivots"]
        | region_sets["remaining_free_coordinates"]
    ):
        raise AssertionError("old free set does not split into promoted and remaining")

    for name, indices in regions.items():
        expected = EXPECTED_REGION_PROVENANCE[name]
        if len(indices) != expected["coordinate_count"]:
            raise AssertionError(f"coordinate-region count changed: {name}")
        if canonical_hash(indices) != expected["coordinate_set_sha256"]:
            raise AssertionError(f"coordinate-region set hash changed: {name}")
    if canonical_hash(sparse_ordered) != EXPECTED_REGION_PROVENANCE[
        "frozen_sparse_prefix_pivots"
    ]["ordered_provenance_sha256"]:
        raise AssertionError("ordered sparse-prefix hash changed")
    return regions


def compact_input_record(item: dict[str, object]) -> dict[str, object]:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    started_wall = time.perf_counter()
    started_usage = resource.getrusage(resource.RUSAGE_SELF)
    load_started = time.perf_counter()
    inputs = [load_input(spec) for spec in INPUT_SPECS]
    load_seconds = time.perf_counter() - load_started

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
        raise AssertionError("dense-pivot-swap problem signatures differ")
    signature_sha = next(iter(signatures))
    p181 = next(item for item in sources if item["characteristic"] == 181)
    coordinate_regions = derive_coordinate_regions(p181)

    crt_stages, modulus = iterative_crt_setup(source_primes)
    if modulus != EXPECTED_SOURCE_MODULUS:
        raise AssertionError("source modulus left the frozen M70 gate")
    if modulus.bit_length() != EXPECTED_SOURCE_MODULUS_BITS:
        raise AssertionError("source modulus bit length is not 70")

    outcome: collections.Counter[str] = collections.Counter()
    outcome_coordinates = {label: [] for label in OUTCOME_LABELS}
    candidate_histogram: collections.Counter[int] = collections.Counter()
    survivor_histogram: collections.Counter[int] = collections.Counter()
    product_height_histogram: collections.Counter[int] = collections.Counter()
    selector_survivor_totals = [0] * len(selectors)
    selector_nonempty_coordinate_counts = [0] * len(selectors)
    candidate_count_vector: list[int] = []
    survivor_count_vector: list[int] = []
    combined_residues: list[str] = []
    total_eea_steps = 0
    total_candidates = 0
    all_source_zero_count = 0
    maximum_unique_profile: tuple[int, int, int, int, int, int] | None = None
    candidate_stream_hasher = hashlib.sha256()
    survivor_stream_hasher = hashlib.sha256()
    unique_candidate_hasher = hashlib.sha256()

    census_started = time.perf_counter()
    for coordinate in range(EXPECTED_COORDINATE_COUNT):
        source_residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        all_source_zero_count += not any(source_residues)
        combined = iterative_crt(source_residues, crt_stages)
        combined_residues.append(str(combined))
        candidates, eea_steps = complete_strict_product_candidates(
            combined, modulus
        )
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
            selector_survivor_totals[selector_index] += len(survivors)
            selector_nonempty_coordinate_counts[selector_index] += bool(survivors)

        survivor_count_vector.append(len(survivors))
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
    census_seconds = time.perf_counter() - census_started

    if sum(outcome.values()) != EXPECTED_COORDINATE_COUNT:
        raise AssertionError("outcomes do not cover all coordinates")
    outcome_sets = {
        label: set(indices) for label, indices in outcome_coordinates.items()
    }
    cross_tab = {}
    for name, indices in coordinate_regions.items():
        index_set = set(indices)
        row = {
            label: len(index_set & outcome_sets[label]) for label in OUTCOME_LABELS
        }
        if sum(row.values()) != len(indices):
            raise AssertionError(f"cross-tab row does not total: {name}")
        cross_tab[name] = {
            "coordinate_count": len(indices),
            "coordinate_set_sha256": canonical_hash(indices),
            "outcome": row,
        }
    if sum(row["coordinate_count"] for row in cross_tab.values()) != (
        EXPECTED_COORDINATE_COUNT
    ):
        raise AssertionError("cross-tab regions do not total 38,048")
    for label in OUTCOME_LABELS:
        if sum(row["outcome"][label] for row in cross_tab.values()) != outcome[label]:
            raise AssertionError(f"cross-tab column does not total: {label}")

    maximum_record = None
    if maximum_unique_profile is not None:
        (
            product_bits,
            numerator_bits,
            denominator_bits,
            coordinate,
            numerator,
            denominator,
        ) = (
            maximum_unique_profile
        )
        maximum_record = {
            "coordinate": coordinate,
            "reduced_numerator": numerator,
            "positive_denominator": denominator,
            "twice_absolute_product": 2 * abs(numerator) * denominator,
            "twice_product_bit_length": product_bits,
            "numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }

    compact_inputs = [compact_input_record(item) for item in inputs]
    finished_usage = resource.getrusage(resource.RUSAGE_SELF)
    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.third-colon-dense-pivot-swap-full-vector-m70-census.v1",
        "status": "PASS_BOUNDED_DENSE_PIVOT_SWAP_FULL_VECTOR_M70_CENSUS",
        "method": (
            "iterative CRT over the three frozen source primes; complete "
            "strict-product extended-Euclid candidate enumeration at every "
            "coordinate; sequential held-out filtering at p=173,197,199"
        ),
        "coordinate_count": EXPECTED_COORDINATE_COUNT,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "source_characteristics": source_primes,
        "selector_characteristics": selector_primes,
        "fixed_gauge_signature_sha256": signature_sha,
        "outcome": {label: outcome[label] for label in OUTCOME_LABELS},
        "coordinates_by_outcome": outcome_coordinates,
        "coordinates_by_outcome_sha256": {
            label: canonical_hash(indices)
            for label, indices in outcome_coordinates.items()
        },
        "candidate_enumeration": {
            "total_candidates_before_selectors": total_candidates,
            "total_extended_euclid_steps": total_eea_steps,
            "all_source_residues_zero_coordinate_count": all_source_zero_count,
            "candidate_count_histogram": {
                str(key): value for key, value in sorted(candidate_histogram.items())
            },
            "candidate_count_vector_sha256": canonical_hash(candidate_count_vector),
            "candidate_stream_sha256": candidate_stream_hasher.hexdigest(),
            "combined_crt_residue_vector_sha256": canonical_hash(
                combined_residues
            ),
        },
        "selector_filtering": {
            "aggregates": [
                {
                    "characteristic": selector["characteristic"],
                    "survivor_count_sum_after_selector": (
                        selector_survivor_totals[index]
                    ),
                    "coordinates_with_a_survivor_after_selector": (
                        selector_nonempty_coordinate_counts[index]
                    ),
                }
                for index, selector in enumerate(selectors)
            ],
            "final_survivor_count_histogram": {
                str(key): value for key, value in sorted(survivor_histogram.items())
            },
            "final_survivor_count_vector_sha256": canonical_hash(
                survivor_count_vector
            ),
            "final_survivor_stream_sha256": survivor_stream_hasher.hexdigest(),
            "unique_candidate_coordinate_value_stream_sha256": (
                unique_candidate_hasher.hexdigest()
            ),
        },
        "unique_nonzero_product_bit_length_histogram": {
            str(key): value
            for key, value in sorted(product_height_histogram.items())
        },
        "maximum_unique_nonzero_profile": maximum_record,
        "dense_pivot_swap_provenance": {
            "constructor_receipt": str(P181_RECEIPT),
            "constructor_receipt_sha256": EXPECTED_P181_RECEIPT_SHA256,
            "old_gauge_artifact": json.loads(
                P181_RECEIPT.read_text(encoding="utf-8")
            )["source"],
            "region_partition_sha256": canonical_hash(coordinate_regions),
            "regions": {
                name: {
                    "coordinate_count": len(indices),
                    "coordinate_set_sha256": canonical_hash(indices),
                }
                for name, indices in coordinate_regions.items()
            },
            "outcome_cross_tab": cross_tab,
            "checks": {
                "regions_pairwise_disjoint": True,
                "regions_partition_all_38048_coordinates": True,
                "new_pivots_are_frozen_prefix_plus_promoted_set": True,
                "new_free_set_is_zeroed_old_dense_plus_remaining_free": True,
                "old_free_set_is_promoted_plus_remaining_free": True,
                "frozen_region_counts_and_hashes_exact": True,
            },
        },
        "inputs": {
            "artifacts_and_receipts": compact_inputs,
            "input_manifest_sha256": canonical_hash(compact_inputs),
            "total_input_bytes": sum(
                int(item["byte_count"]) + int(item["receipt_byte_count"])
                for item in compact_inputs
            ),
        },
        "source_script": {
            "path": str(script_path),
            "sha256": file_sha256(script_path),
        },
        "resources": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "load_and_validation_wall_seconds": load_seconds,
            "census_wall_seconds": census_seconds,
            "total_wall_seconds": time.perf_counter() - started_wall,
            "user_cpu_seconds": (
                finished_usage.ru_utime - started_usage.ru_utime
            ),
            "system_cpu_seconds": (
                finished_usage.ru_stime - started_usage.ru_stime
            ),
            "maximum_rss_native_self": finished_usage.ru_maxrss,
        },
        "completeness_statement": (
            "For each coordinate, every reduced n/d with d>0, gcd(d,M)=1, "
            "n=r*d mod M, and 2*abs(n)*d<M occurs among the tested Euclidean "
            "convergents by Legendre's theorem. The candidate-stream hash "
            "commits to every enumerated candidate in coordinate order."
        ),
        "claim_boundary": (
            "This is a complete bounded strict-product height census at the "
            "70-bit source modulus in one finite-field-compatible dense-pivot-"
            "swap gauge. A surviving candidate, including a unique candidate, "
            "is not a reconstructed rational coefficient. This script does "
            "not assemble or replay a QQ multiplier identity and proves no QQ "
            "colon, saturation, secant, nullcone, or quartic Hessian statement."
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
                "source_modulus_bit_length": modulus.bit_length(),
                "coordinate_count": EXPECTED_COORDINATE_COUNT,
                "outcome": result["outcome"],
                "outcome_cross_tab": cross_tab,
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
