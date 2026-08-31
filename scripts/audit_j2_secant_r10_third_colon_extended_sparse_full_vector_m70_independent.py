#!/usr/bin/env python3
"""Independent direct-CRT/ordinary-CF audit of extended-sparse M70.

Exactly p=181,2147483647,2147483629 enter the source modulus, and exactly
p=173,197 are held-out selectors.  The frozen producer is neither imported
nor executed.  This standard-library audit recomputes every coordinate and
binds the complete candidate, selector-survivor, and outcome streams.
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
PRODUCER_SCRIPT = CAMPAIGN / "scripts" / (
    "audit_j2_secant_r10_third_colon_extended_sparse_full_vector_m70.py"
)
PRODUCER_RECEIPT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-m70-census.json"
)
OUTPUT = RECEIPTS / (
    "hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-"
    "m70-independent-audit.json"
)

EXPECTED_PRODUCER_SCRIPT_SHA256 = (
    "7d4f32ebcf4397529bc31c1f3aed82adf23a397140608d1fb80835ec368e9b12"
)
EXPECTED_PRODUCER_RECEIPT_SHA256 = (
    "78d0bd0200299c1dc8fb7df7880f479613e93cf0ccca99c4741a97883c501ad7"
)
EXPECTED_SOURCE_PRIMES = [181, 2147483647, 2147483629]
EXPECTED_SELECTOR_PRIMES = [173, 197]
EXPECTED_MODULUS = 834715161561466408303
EXPECTED_COORDINATES = 38_048
EXPECTED_PIVOTS = 35_881
EXPECTED_FREE = 2_167
EXPECTED_FREE_HASH = (
    "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
)
EXPECTED_PIVOT_SET_HASH = (
    "2e59d83eba84cab80823a8277b2b40f1af518a02e7ae5de595baed358de01a1c"
)
EXPECTED_P181_ARTIFACT_SHA256 = (
    "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b"
)
EXPECTED_P181_ORDERED_PIVOT_HASH = (
    "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d"
)
EXPECTED_SIGNATURE_HASH = (
    "037a2643ba69679d180e67c6dcaab7fdb13e772a18357bfef086f52427f34373"
)
EXPECTED_OUTCOME = {
    "no_candidate": 17_758,
    "ambiguous": 0,
    "unique_zero": 18_998,
    "unique_nonzero": 1_292,
}
EXPECTED_MAXIMUM_PROFILE = {
    "coordinate": 12950,
    "denominator_bit_length": 2,
    "numerator_bit_length": 68,
    "positive_denominator": 2,
    "reduced_numerator": 157000558186433927001,
    "twice_absolute_product": 628002232745735708004,
    "twice_product_bit_length": 70,
}
INPUT_SPECS = [
    {
        "role": "source",
        "characteristic": 181,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
        "artifact_sha256": EXPECTED_P181_ARTIFACT_SHA256,
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
        "receipt_sha256": "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c",
    },
    {
        "role": "source",
        "characteristic": 2147483647,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "artifact_sha256": "a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "receipt_sha256": "dba8ffbaf933500d5e532f9f4b19f356b20710383614b9d8b03200980e611f79",
    },
    {
        "role": "source",
        "characteristic": 2147483629,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "artifact_sha256": "2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "receipt_sha256": "f572ebb40bbb4d590506210737347b0c6c964927ac866d9fba410621d4e354bb",
    },
    {
        "role": "selector",
        "characteristic": 173,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "artifact_sha256": "b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "receipt_sha256": "ddaed2462174438e89b31cfacb95ee2adf7971bf2290c58422031baab9314f44",
    },
    {
        "role": "selector",
        "characteristic": 197,
        "artifact": ARTIFACTS
        / "j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "artifact_sha256": "f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272",
        "receipt": RECEIPTS
        / "hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "receipt_sha256": "671df724adb16f279f9be31dfe0c87f90b0d48f02a9ea6161245f26d86c701fe",
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
    if not is_prime_32(prime):
        raise AssertionError(f"nonprime characteristic: {prime}")
    if int(artifact.get("characteristic", -1)) != prime:
        raise AssertionError(f"artifact characteristic mismatch: {artifact_path}")
    if int(receipt.get("characteristic", -1)) != prime:
        raise AssertionError(f"receipt characteristic mismatch: {receipt_path}")
    replay = receipt.get("same_process_sparse_replay", {})
    certificate = receipt.get("certificate", {})
    if (
        receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        or not replay.get("completed")
        or not replay.get("identity_zero")
        or int(replay.get("mismatch_count", -1)) != 0
        or replay.get("first_mismatch") is not None
        or certificate.get("sha256") != artifact_hash
        or int(certificate.get("byte_count", -1)) != artifact_path.stat().st_size
        or Path(str(certificate.get("path", ""))).resolve() != artifact_path
    ):
        raise AssertionError(f"receipt binding/replay failed: {receipt_path}")

    vector = list(map(int, artifact["coordinate_vector"]))
    pivots = list(map(int, artifact["pivot_unknown_indices"]))
    free = list(map(int, artifact["free_unknown_indices"]))
    if (
        len(vector) != EXPECTED_COORDINATES
        or len(pivots) != EXPECTED_PIVOTS
        or len(free) != EXPECTED_FREE
        or any(value < 0 or value >= prime for value in vector)
        or canonical_hash(vector) != artifact["coordinate_vector_sha256"]
        or canonical_hash(pivots) != artifact["pivot_unknown_indices_sha256"]
        or canonical_hash(free) != artifact["free_unknown_indices_sha256"]
        or artifact["free_unknown_indices_sha256"] != EXPECTED_FREE_HASH
        or canonical_hash(sorted(pivots)) != EXPECTED_PIVOT_SET_HASH
        or len(set(pivots)) != EXPECTED_PIVOTS
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != set(range(EXPECTED_COORDINATES))
    ):
        raise AssertionError(f"coordinate/gauge profile failed: {artifact_path}")
    gauge = receipt.get("gauge", {})
    solver = receipt.get("solver", {})
    if (
        not gauge.get("coverage_verified")
        or gauge.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH
        or int(solver.get("pivot_count", -1)) != EXPECTED_PIVOTS
        or int(solver.get("free_unknown_count", -1)) != EXPECTED_FREE
        or not solver.get("completed")
        or not solver.get("consistent")
        or solver.get("timed_out")
    ):
        raise AssertionError(f"fixed-free solve profile failed: {receipt_path}")
    if prime == 181:
        if (
            artifact.get("gauge_source") is not None
            or artifact["pivot_unknown_indices_sha256"]
            != EXPECTED_P181_ORDERED_PIVOT_HASH
        ):
            raise AssertionError("p181 extended-sparse gauge changed")
    else:
        source = artifact.get("gauge_source", {})
        if (
            int(source.get("characteristic", -1)) != 181
            or source.get("sha256") != EXPECTED_P181_ARTIFACT_SHA256
            or source.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH
            or source.get("pivot_unknown_set_sha256") != EXPECTED_PIVOT_SET_HASH
            or source.get("policy")
            != "freeze source free-coordinate set; adapt pivot order"
        ):
            raise AssertionError(f"transfer gauge source changed: {artifact_path}")

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
    signature["pivot_unknown_set_sha256"] = canonical_hash(sorted(pivots))
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
        "receipt_wall_seconds": receipt.get("timings", {}).get("wall_seconds"),
        "receipt_maximum_rss_native": receipt.get("resources", {}).get(
            "maximum_rss_native"
        ),
        "vector": vector,
        "signature": signature,
    }


def compact_input(item: dict[str, object]) -> dict[str, object]:
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


def direct_crt_basis(primes: list[int]) -> tuple[int, list[int]]:
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


def continued_fraction_candidates(
    residue: int, modulus: int
) -> tuple[list[tuple[int, int]], int]:
    """Enumerate strict-product candidates from proper ordinary convergents."""

    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0
    terms = []
    numerator, denominator = residue, modulus
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        terms.append(quotient)
        numerator, denominator = denominator, remainder

    h_minus_two, h_minus_one = 0, 1
    k_minus_two, k_minus_one = 1, 0
    candidates = set()
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
    candidates = set()
    for denominator in range(1, modulus + 1):
        if math.gcd(denominator, modulus) != 1:
            continue
        least = residue * denominator % modulus
        for numerator in {least, least - modulus}:
            if (
                math.gcd(abs(numerator), denominator) == 1
                and 2 * abs(numerator) * denominator < modulus
                and (numerator - residue * denominator) % modulus == 0
            ):
                candidates.add((numerator, denominator))
    return sorted(candidates)


def candidate_enumerator_self_test() -> dict[str, object]:
    tested = 0
    transcript = hashlib.sha256()
    for modulus in range(2, 100):
        for residue in range(modulus):
            tested += 1
            observed, _count = continued_fraction_candidates(residue, modulus)
            expected = brute_force_candidates(residue, modulus)
            if observed != expected:
                raise AssertionError(
                    f"candidate self-test failed at M={modulus}, r={residue}"
                )
            transcript.update(f"{modulus}:{residue}:{observed}\n".encode("ascii"))
    return {
        "status": "PASS",
        "modulus_range_inclusive": [2, 99],
        "residue_modulus_pairs_tested": tested,
        "comparison": "ordinary-CF candidate set equals literal brute-force set",
        "transcript_sha256": transcript.hexdigest(),
    }


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    if file_sha256(PRODUCER_SCRIPT) != EXPECTED_PRODUCER_SCRIPT_SHA256:
        raise AssertionError("producer script changed")
    if file_sha256(PRODUCER_RECEIPT) != EXPECTED_PRODUCER_RECEIPT_SHA256:
        raise AssertionError("producer receipt changed")
    producer = json.loads(PRODUCER_RECEIPT.read_text(encoding="utf-8"))
    if producer.get("status") != "PASS_BOUNDED_EXTENDED_SPARSE_FULL_VECTOR_M70_CENSUS":
        raise AssertionError("producer census is not passing")

    self_test = candidate_enumerator_self_test()
    inputs = [load_input(spec) for spec in INPUT_SPECS]
    sources = [item for item in inputs if item["role"] == "source"]
    selectors = [item for item in inputs if item["role"] == "selector"]
    source_primes = [int(item["characteristic"]) for item in sources]
    selector_primes = [int(item["characteristic"]) for item in selectors]
    if source_primes != EXPECTED_SOURCE_PRIMES:
        raise AssertionError("source primes differ from exact assignment")
    if selector_primes != EXPECTED_SELECTOR_PRIMES:
        raise AssertionError("selector primes differ from exact assignment")
    if set(source_primes) & set(selector_primes):
        raise AssertionError("a selector entered the source modulus")
    signatures = {canonical_hash(item["signature"]) for item in inputs}
    if signatures != {EXPECTED_SIGNATURE_HASH}:
        raise AssertionError("fixed extended-sparse signatures differ")

    modulus, crt_weights = direct_crt_basis(source_primes)
    if modulus != EXPECTED_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("direct CRT did not recover the exact M70 modulus")
    if any(
        weight % own != 1
        or any(weight % other for other in source_primes if other != own)
        for own, weight in zip(source_primes, crt_weights, strict=True)
    ):
        raise AssertionError("direct CRT basis failed its reduction identities")

    outcome = collections.Counter()
    outcome_coordinates = {label: [] for label in OUTCOME_LABELS}
    outcome_labels = []
    candidate_histogram = collections.Counter()
    final_survivor_histogram = collections.Counter()
    height_histogram = collections.Counter()
    candidate_counts = []
    stage_counts = [[] for _ in selectors]
    stage_totals = [0] * len(selectors)
    stage_nonempty = [0] * len(selectors)
    combined_residues = []
    final_nonempty_records = []
    total_candidates = 0
    total_proper_convergents = 0
    all_source_zero_count = 0
    maximum_profile = None
    candidate_hasher = hashlib.sha256()
    stage_hashers = [hashlib.sha256() for _ in selectors]
    outcome_hasher = hashlib.sha256()
    unique_hasher = hashlib.sha256()

    census_started = time.perf_counter()
    for coordinate in range(EXPECTED_COORDINATES):
        residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        all_source_zero_count += int(not any(residues))
        combined = direct_crt(residues, crt_weights, modulus)
        if any(combined % prime != residue for prime, residue in zip(source_primes, residues, strict=True)):
            raise AssertionError(f"direct CRT reduction failed at {coordinate}")
        combined_residues.append(str(combined))
        candidates, proper_count = continued_fraction_candidates(combined, modulus)
        total_proper_convergents += proper_count
        total_candidates += len(candidates)
        candidate_counts.append(len(candidates))
        candidate_histogram[len(candidates)] += 1
        candidate_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in candidates:
            candidate_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        candidate_hasher.update(b"\n")

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
            stage_counts[selector_index].append(len(survivors))
            stage_totals[selector_index] += len(survivors)
            stage_nonempty[selector_index] += int(bool(survivors))
            stage_hashers[selector_index].update(f"{coordinate}:".encode("ascii"))
            for numerator, denominator in survivors:
                stage_hashers[selector_index].update(
                    f"{numerator}/{denominator};".encode("ascii")
                )
            stage_hashers[selector_index].update(b"\n")

        final_survivor_histogram[len(survivors)] += 1
        if survivors:
            final_nonempty_records.append(
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
            unique_hasher.update(
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
        outcome_labels.append(label)
        outcome_hasher.update(f"{coordinate}:{label}\n".encode("ascii"))
    census_seconds = time.perf_counter() - census_started

    if sum(outcome.values()) != EXPECTED_COORDINATES:
        raise AssertionError("coordinate outcomes do not cover all coordinates")
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

    normalized_outcome = {label: outcome[label] for label in OUTCOME_LABELS}
    coordinate_hashes = {
        label: canonical_hash(values) for label, values in outcome_coordinates.items()
    }
    candidate_summary = {
        "total_candidates_before_selectors": total_candidates,
        "total_proper_continued_fraction_convergents": total_proper_convergents,
        "all_source_residues_zero_coordinate_count": all_source_zero_count,
        "candidate_count_histogram": {
            str(key): value for key, value in sorted(candidate_histogram.items())
        },
        "candidate_count_vector_sha256": canonical_hash(candidate_counts),
        "complete_candidate_text_stream_sha256": candidate_hasher.hexdigest(),
        "combined_crt_residue_vector_sha256": canonical_hash(combined_residues),
    }
    full_stage_records = []
    compact_stage_records = []
    for index, selector in enumerate(selectors):
        full_record = {
            "characteristic": selector["characteristic"],
            "survivor_count_sum_after_selector": stage_totals[index],
            "coordinates_with_a_survivor_after_selector": stage_nonempty[index],
            "survivor_count_vector": stage_counts[index],
            "survivor_count_vector_sha256": canonical_hash(stage_counts[index]),
            "survivor_candidate_stream_sha256": stage_hashers[index].hexdigest(),
        }
        full_stage_records.append(full_record)
        compact_stage_records.append(
            {key: value for key, value in full_record.items() if key != "survivor_count_vector"}
        )
    selector_summary = {
        "stages": compact_stage_records,
        "final_survivor_count_histogram": {
            str(key): value for key, value in sorted(final_survivor_histogram.items())
        },
        "unique_candidate_coordinate_value_stream_sha256": unique_hasher.hexdigest(),
    }
    height_histogram_dict = {
        str(key): value for key, value in sorted(height_histogram.items())
    }
    producer_candidate = producer["candidate_enumeration"]
    producer_full = producer["full_outcome_streams"]
    producer_checks = {
        "source_primes_exact": source_primes == producer["source_characteristics"],
        "selector_primes_exact": selector_primes == producer["selector_characteristics"],
        "source_modulus_exact": str(modulus) == producer["source_modulus"],
        "source_modulus_bits_exact": modulus.bit_length()
        == producer["source_modulus_bit_length"],
        "fixed_gauge_signature_exact": EXPECTED_SIGNATURE_HASH
        == producer["fixed_gauge_signature_sha256"],
        "outcome_exact": normalized_outcome == producer["outcome"] == EXPECTED_OUTCOME,
        "outcome_label_vector_exact": outcome_labels
        == producer_full["outcome_label_vector"],
        "outcome_label_vector_hash_exact": canonical_hash(outcome_labels)
        == producer_full["outcome_label_vector_sha256"],
        "outcome_text_stream_hash_exact": outcome_hasher.hexdigest()
        == producer_full["outcome_text_stream_sha256"],
        "outcome_coordinate_lists_exact": outcome_coordinates
        == producer_full["coordinates_by_outcome"],
        "outcome_coordinate_hashes_exact": coordinate_hashes
        == producer_full["coordinates_by_outcome_sha256"],
        "nonempty_survivor_records_exact": final_nonempty_records
        == producer_full["nonempty_final_survivor_records"],
        "nonempty_survivor_records_hash_exact": canonical_hash(final_nonempty_records)
        == producer_full["nonempty_final_survivor_records_sha256"],
        "candidate_total_exact": total_candidates
        == producer_candidate["total_candidates_before_selectors"],
        "proper_cf_count_equals_producer_eea_steps": total_proper_convergents
        == producer_candidate["total_extended_euclid_steps"],
        "all_source_zero_count_exact": all_source_zero_count
        == producer_candidate["all_source_residues_zero_coordinate_count"],
        "candidate_histogram_exact": candidate_summary["candidate_count_histogram"]
        == producer_candidate["candidate_count_histogram"],
        "candidate_count_vector_exact": candidate_counts
        == producer_candidate["candidate_count_vector"],
        "candidate_count_vector_hash_exact": candidate_summary[
            "candidate_count_vector_sha256"
        ]
        == producer_candidate["candidate_count_vector_sha256"],
        "candidate_text_stream_hash_exact": candidate_summary[
            "complete_candidate_text_stream_sha256"
        ]
        == producer_candidate["complete_candidate_text_stream_sha256"],
        "combined_crt_stream_hash_exact": candidate_summary[
            "combined_crt_residue_vector_sha256"
        ]
        == producer_candidate["combined_crt_residue_vector_sha256"],
        "selector_stage_records_exact": full_stage_records
        == producer["selector_filtering"]["stages"],
        "final_survivor_histogram_exact": selector_summary[
            "final_survivor_count_histogram"
        ]
        == producer["selector_filtering"]["final_survivor_count_histogram"],
        "unique_candidate_stream_hash_exact": selector_summary[
            "unique_candidate_coordinate_value_stream_sha256"
        ]
        == producer["selector_filtering"][
            "unique_candidate_coordinate_value_stream_sha256"
        ],
        "height_histogram_exact": height_histogram_dict
        == producer["unique_nonzero_product_bit_length_histogram"],
        "maximum_profile_exact": maximum_record
        == producer["maximum_unique_nonzero_profile"]
        == EXPECTED_MAXIMUM_PROFILE,
    }
    compact_inputs = [compact_input(item) for item in inputs]
    input_checks = {
        "exactly_three_sources_and_two_selectors": len(sources) == 3
        and len(selectors) == 2,
        "no_extra_modular_characteristics": source_primes + selector_primes
        == [181, 2147483647, 2147483629, 173, 197],
        "input_manifest_exact": canonical_hash(compact_inputs)
        == producer["inputs"]["input_manifest_sha256"],
        "input_byte_total_exact": sum(
            int(item["byte_count"]) + int(item["receipt_byte_count"])
            for item in compact_inputs
        )
        == producer["inputs"]["total_input_bytes"],
        "all_input_receipts_exact": all(
            producer["inputs"]["checks"].values()
        ),
    }
    if not all(producer_checks.values()) or not all(input_checks.values()):
        raise AssertionError(
            f"independent comparison failed: {producer_checks}, {input_checks}"
        )

    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.third-colon-extended-sparse-full-vector-m70-independent-audit.v1",
        "status": "PASS_INDEPENDENT_EXTENDED_SPARSE_FULL_VECTOR_M70_CENSUS",
        "independence": {
            "language_runtime": "Python standard library only",
            "campaign_module_imports": [],
            "producer_imported": False,
            "producer_executed": False,
            "heavy_algebra_executed": False,
            "crt_method": (
                "symmetric direct CRT using M_i*(M_i^-1 mod p_i) basis weights"
            ),
            "candidate_method": (
                "all proper convergents of the ordinary continued fraction of "
                "r/M, tested via n=r*q-M*p and the strict-product condition"
            ),
            "candidate_enumerator_self_test": self_test,
        },
        "coordinate_count": EXPECTED_COORDINATES,
        "source_characteristics": source_primes,
        "selector_characteristics": selector_primes,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "direct_crt_basis_weights_sha256": canonical_hash(
            [str(value) for value in crt_weights]
        ),
        "fixed_gauge_signature_sha256": EXPECTED_SIGNATURE_HASH,
        "outcome": normalized_outcome,
        "full_outcome_stream_hashes": {
            "outcome_label_vector_sha256": canonical_hash(outcome_labels),
            "outcome_text_stream_sha256": outcome_hasher.hexdigest(),
            "coordinates_by_outcome_sha256": coordinate_hashes,
            "nonempty_final_survivor_records_sha256": canonical_hash(
                final_nonempty_records
            ),
            "nonempty_final_survivor_record_count": len(final_nonempty_records),
        },
        "candidate_enumeration": candidate_summary,
        "selector_filtering": selector_summary,
        "unique_nonzero_product_bit_length_histogram": height_histogram_dict,
        "maximum_unique_nonzero_profile": maximum_record,
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
            "For each reduced strict-product candidate n/d, the integer "
            "k=(r*d-n)/M satisfies |r/M-k/d|<1/(2*d^2); Legendre's theorem "
            "therefore places k/d among the proper ordinary continued-fraction "
            "convergents tested here. The enumerator also matched literal brute "
            "force for every residue modulo every M from 2 through 99."
        ),
        "claim_boundary": (
            "A PASS independently verifies only the complete bounded strict-"
            "product candidate census at this single 70-bit source modulus in "
            "the frozen finite-field-compatible extended-sparse p181 gauge. A "
            "surviving or unique candidate is not a reconstructed rational "
            "coefficient. No QQ multiplier identity is assembled or replayed, "
            "and no QQ colon, saturation, secant, nullcone, quartic Hessian, or "
            "HC4 statement is proved."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT),
                "outcome": normalized_outcome,
                "candidate_stream_sha256": candidate_summary[
                    "complete_candidate_text_stream_sha256"
                ],
                "selector_stage_stream_sha256": [
                    item["survivor_candidate_stream_sha256"]
                    for item in compact_stage_records
                ],
                "maximum_unique_nonzero_profile": maximum_record,
                "wall_seconds": result["resources"]["total_wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
