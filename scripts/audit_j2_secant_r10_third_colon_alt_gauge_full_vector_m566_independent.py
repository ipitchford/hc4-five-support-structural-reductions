#!/usr/bin/env python3
"""Independent standard-library replay of the p181-gauge M566 census.

This script deliberately imports no campaign module.  It recomputes the CRT
coordinatewise by iterative pairwise combination and obtains the complete
strict-product candidates from the ordinary continued-fraction convergents of
r/M.  In particular it does not import or call the producer's extended-Euclid
candidate enumerator.
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
CHECKPOINT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-coordinate13-adaptive-crt-"
    "alt-p181-gauge-m566-predeclared-checkpoint.json"
)
PRODUCER_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-alt-p181-gauge-full-vector-"
    "m566-census.json"
)
PRODUCER_SCRIPT = CAMPAIGN / "scripts" / (
    "audit_j2_secant_r10_third_colon_alt_gauge_full_vector_m566.py"
)
GAUGE_RECEIPT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json"
)
OUTPUT = CAMPAIGN / "receipts" / (
    "hsop-j2-secant-r10-third-colon-alt-p181-gauge-full-vector-"
    "m566-independent-audit.json"
)

EXPECTED_SOURCE_PRIMES = [
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
]
EXPECTED_SELECTORS = [173, 197, 199, 2147483549]
EXPECTED_COORDINATES = 38048
EXPECTED_MODULUS_BITS = 566
EXPECTED_OUTCOME = {
    "no_candidate": 19762,
    "unique_nonzero": 535,
    "unique_zero": 17751,
}


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


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


def load_artifact(record: dict[str, object]) -> dict[str, object]:
    path = Path(str(record["path"])).resolve()
    observed_hash = file_sha256(path)
    if observed_hash != record["sha256"]:
        raise AssertionError(f"artifact hash mismatch: {path}")
    payload = json.loads(path.read_text(encoding="ascii"))
    prime = int(payload["characteristic"])
    if prime != int(record["characteristic"]):
        raise AssertionError(f"artifact characteristic mismatch: {path}")
    if not is_prime_32(prime):
        raise AssertionError(f"nonprime artifact characteristic: {prime}")
    vector = list(map(int, payload["coordinate_vector"]))
    pivots = list(map(int, payload["pivot_unknown_indices"]))
    free = list(map(int, payload["free_unknown_indices"]))
    if payload.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise AssertionError(f"coordinate vector hash mismatch: {path}")
    if payload.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise AssertionError(f"ordered pivot hash mismatch: {path}")
    if payload.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise AssertionError(f"free-coordinate hash mismatch: {path}")
    coordinate_universe = set(range(len(vector)))
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != coordinate_universe
    ):
        raise AssertionError(f"pivot/free partition failure: {path}")
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
        "characteristic": prime,
        "vector": vector,
        "pivots": pivots,
        "free": free,
        "signature": signature,
    }


def iterative_crt_setup(primes: list[int]) -> tuple[list[tuple[int, int, int]], int]:
    modulus = 1
    stages: list[tuple[int, int, int]] = []
    for prime in primes:
        if math.gcd(modulus, prime) != 1:
            raise AssertionError("CRT moduli are not pairwise coprime")
        inverse = pow(modulus % prime, -1, prime)
        stages.append((prime, modulus, inverse))
        modulus *= prime
    return stages, modulus


def iterative_crt(residues: list[int], stages: list[tuple[int, int, int]]) -> int:
    value = 0
    for residue, (prime, modulus, inverse) in zip(residues, stages, strict=True):
        correction = (residue - value) % prime
        correction = correction * inverse % prime
        value += modulus * correction
    return value


def continued_fraction_candidates(
    residue: int, modulus: int
) -> tuple[list[tuple[int, int]], int]:
    """Enumerate strict-product candidates from proper CF convergents of r/M."""

    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0

    # Ordinary simple continued fraction of residue/modulus.
    terms: list[int] = []
    numerator, denominator = residue, modulus
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        terms.append(quotient)
        numerator, denominator = denominator, remainder

    # Standard convergent recurrence.  The last convergent is residue/modulus
    # itself and corresponds to the zero remainder, so only proper convergents
    # are candidates.
    h_minus_two, h_minus_one = 0, 1
    k_minus_two, k_minus_one = 1, 0
    candidates: set[tuple[int, int]] = set()
    proper_convergent_count = 0
    for index, term in enumerate(terms):
        h = term * h_minus_one + h_minus_two
        k = term * k_minus_one + k_minus_two
        h_minus_two, h_minus_one = h_minus_one, h
        k_minus_two, k_minus_one = k_minus_one, k
        if index + 1 == len(terms):
            break
        proper_convergent_count += 1
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
            and (
                candidate_numerator - residue * candidate_denominator
            )
            % modulus
            == 0
        ):
            candidates.add((candidate_numerator, candidate_denominator))
    return sorted(candidates), proper_convergent_count


def input_record(item: dict[str, object]) -> dict[str, object]:
    return {
        "path": item["path"],
        "sha256": item["sha256"],
        "characteristic": item["characteristic"],
    }


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    checkpoint_hash = file_sha256(CHECKPOINT)
    producer_receipt_hash = file_sha256(PRODUCER_RECEIPT)
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    producer = json.loads(PRODUCER_RECEIPT.read_text(encoding="utf-8"))

    sources = [load_artifact(record) for record in checkpoint["source_artifacts"]]
    selectors = [
        load_artifact(record) for record in checkpoint["selector_artifacts"]
    ]
    source_primes = [int(item["characteristic"]) for item in sources]
    selector_primes = [int(item["characteristic"]) for item in selectors]
    if source_primes != EXPECTED_SOURCE_PRIMES:
        raise AssertionError("the 19-source M566 prime order changed")
    if selector_primes != EXPECTED_SELECTORS:
        raise AssertionError("the selector/validator order changed")
    if set(source_primes) & set(selector_primes):
        raise AssertionError("a selector entered the source modulus")

    all_inputs = sources + selectors
    lengths = {len(item["vector"]) for item in all_inputs}
    if lengths != {EXPECTED_COORDINATES}:
        raise AssertionError(f"coordinate length mismatch: {lengths}")
    signature_hashes = {canonical_hash(item["signature"]) for item in all_inputs}
    if len(signature_hashes) != 1:
        raise AssertionError("fixed p181-gauge signatures differ")
    signature_hash = next(iter(signature_hashes))

    crt_stages, modulus = iterative_crt_setup(source_primes)
    if modulus.bit_length() != EXPECTED_MODULUS_BITS:
        raise AssertionError("source modulus is not the M566 modulus")
    if str(modulus) != checkpoint["source_modulus"]:
        raise AssertionError("independent source modulus disagrees with checkpoint")

    outcome: collections.Counter[str] = collections.Counter()
    coordinate_lists: dict[str, list[int]] = collections.defaultdict(list)
    candidate_histogram: collections.Counter[int] = collections.Counter()
    product_height_histogram: collections.Counter[int] = collections.Counter()
    selector_survivor_totals = [0] * len(selectors)
    selector_nonempty_coordinate_counts = [0] * len(selectors)
    total_cf_proper_convergents = 0
    maximum_unique_profile: tuple[int, int, int, int] | None = None
    combined_residues: list[str] = []
    unique_candidate_hasher = hashlib.sha256()
    candidate_stream_hasher = hashlib.sha256()

    for coordinate in range(EXPECTED_COORDINATES):
        source_residues = [
            int(item["vector"][coordinate]) % int(item["characteristic"])
            for item in sources
        ]
        combined = iterative_crt(source_residues, crt_stages)
        combined_residues.append(str(combined))
        candidates, proper_count = continued_fraction_candidates(combined, modulus)
        total_cf_proper_convergents += proper_count
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
                (candidate_numerator, candidate_denominator)
                for candidate_numerator, candidate_denominator in survivors
                if candidate_denominator % prime
                and candidate_numerator
                % prime
                * pow(candidate_denominator % prime, -1, prime)
                % prime
                == observed
            ]
            selector_survivor_totals[selector_index] += len(survivors)
            selector_nonempty_coordinate_counts[selector_index] += bool(survivors)

        if not survivors:
            label = "no_candidate"
        elif len(survivors) > 1:
            label = "ambiguous"
        else:
            candidate_numerator, candidate_denominator = survivors[0]
            label = "unique_zero" if candidate_numerator == 0 else "unique_nonzero"
            unique_candidate_hasher.update(
                f"{coordinate}:{candidate_numerator}/{candidate_denominator}\n".encode(
                    "ascii"
                )
            )
            if candidate_numerator:
                product_bits = (
                    2 * abs(candidate_numerator) * candidate_denominator
                ).bit_length()
                product_height_histogram[product_bits] += 1
                profile = (
                    product_bits,
                    abs(candidate_numerator).bit_length(),
                    candidate_denominator.bit_length(),
                    coordinate,
                )
                if maximum_unique_profile is None or profile > maximum_unique_profile:
                    maximum_unique_profile = profile
        outcome[label] += 1
        coordinate_lists[label].append(coordinate)

    if dict(sorted(outcome.items())) != EXPECTED_OUTCOME:
        raise AssertionError(f"independent outcome mismatch: {dict(outcome)}")
    if "ambiguous" in outcome:
        raise AssertionError("an ambiguous coordinate survived all validators")

    maximum_record = None
    if maximum_unique_profile is not None:
        product_bits, numerator_bits, denominator_bits, coordinate = maximum_unique_profile
        maximum_record = {
            "coordinate": coordinate,
            "twice_product_bit_length": product_bits,
            "numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }

    independent_histogram = {
        str(key): value for key, value in sorted(candidate_histogram.items())
    }
    independent_product_histogram = {
        str(key): value for key, value in sorted(product_height_histogram.items())
    }
    producer_checks = {
        "outcome_exact": dict(sorted(outcome.items())) == producer["outcome"],
        "coordinate_lists_exact": {
            label: coordinate_lists[label] == producer["coordinates_by_outcome"][label]
            for label in sorted(coordinate_lists)
        },
        "candidate_count_histogram_exact": independent_histogram
        == producer["candidate_count_histogram"],
        "proper_convergent_count_equals_producer_eea_steps": (
            total_cf_proper_convergents
            == int(producer["complete_eea_step_count_total"])
        ),
        "unique_nonzero_product_histogram_exact": independent_product_histogram
        == producer["unique_nonzero_product_bit_length_histogram"],
        "maximum_unique_profile_exact": maximum_record
        == producer["maximum_unique_nonzero_profile"],
        "source_modulus_exact": str(modulus) == producer["source_modulus"],
        "fixed_gauge_signature_exact": signature_hash
        == producer["fixed_gauge_signature_sha256"],
    }
    if not all(
        value
        for key, value in producer_checks.items()
        if key != "coordinate_lists_exact"
    ) or not all(producer_checks["coordinate_lists_exact"].values()):
        raise AssertionError(f"producer comparison failed: {producer_checks}")

    gauge_source = next(item for item in sources if item["characteristic"] == 181)
    gauge_receipt_hash = file_sha256(GAUGE_RECEIPT)
    gauge_receipt = json.loads(GAUGE_RECEIPT.read_text(encoding="utf-8"))
    if gauge_receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY":
        raise AssertionError("the p181 gauge receipt is not passing")
    dense_handoff = gauge_receipt["solver"]["hybrid_dense_handoff"]
    dense_count = int(dense_handoff["dense_pivot_count"])
    ordered_pivots = list(map(int, gauge_source["pivots"]))
    free_coordinates = set(map(int, gauge_source["free"]))
    dense_pivots = set(ordered_pivots[-dense_count:])
    early_sparse_pivots = set(ordered_pivots[:-dense_count])
    if (
        dense_pivots & early_sparse_pivots
        or dense_pivots & free_coordinates
        or early_sparse_pivots & free_coordinates
        or dense_pivots | early_sparse_pivots | free_coordinates
        != set(range(EXPECTED_COORDINATES))
    ):
        raise AssertionError("independent provenance regions do not partition coordinates")

    outcome_sets = {label: set(values) for label, values in coordinate_lists.items()}
    regions = {
        "early_sparse_pivots": early_sparse_pivots,
        "dense_handoff_pivots": dense_pivots,
        "free_coordinates": free_coordinates,
    }
    cross_tab = {
        region: {
            "coordinate_count": len(indices),
            "outcome": {
                label: len(indices & outcome_indices)
                for label, outcome_indices in sorted(outcome_sets.items())
            },
        }
        for region, indices in regions.items()
    }
    if cross_tab != producer["elimination_provenance"]["cross_tab"]:
        raise AssertionError("independent dense-pivot cross-tab disagrees with producer")
    if len(dense_pivots) != 581 or dense_pivots - outcome_sets["no_candidate"]:
        raise AssertionError("not all 581 dense pivots are no-candidate coordinates")
    if free_coordinates != free_coordinates & outcome_sets["unique_zero"]:
        raise AssertionError("not all frozen free coordinates are uniquely zero")

    outcome_coordinate_hashes = {
        label: canonical_hash(values)
        for label, values in sorted(coordinate_lists.items())
    }
    result = {
        "schema": "hc4.third-colon-alt-gauge-full-vector-m566-independent-audit.v1",
        "status": "PASS_INDEPENDENT_FULL_VECTOR_M566_CENSUS_REPLAY",
        "independence": {
            "language_runtime": "Python standard library only",
            "campaign_module_imports": [],
            "crt_method": "iterative pairwise CRT in the frozen source-prime order",
            "candidate_method": (
                "ordinary simple continued fraction of r/M; test every proper "
                "convergent using n=r*q-M*p and the strict product inequality"
            ),
            "producer_candidate_function_imported": False,
            "producer_script_executed": False,
            "heavy_algebra_executed": False,
        },
        "coordinate_count": EXPECTED_COORDINATES,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "source_characteristics": source_primes,
        "selector_characteristics": selector_primes,
        "fixed_gauge_signature_sha256": signature_hash,
        "outcome": dict(sorted(outcome.items())),
        "coordinates_by_outcome_sha256": outcome_coordinate_hashes,
        "candidate_count_histogram": independent_histogram,
        "complete_proper_convergent_count_total": total_cf_proper_convergents,
        "candidate_stream_sha256": candidate_stream_hasher.hexdigest(),
        "combined_crt_residue_vector_sha256": canonical_hash(combined_residues),
        "unique_candidate_coordinate_value_stream_sha256": (
            unique_candidate_hasher.hexdigest()
        ),
        "selector_filter_aggregates": [
            {
                "characteristic": selector["characteristic"],
                "survivor_count_sum_after_selector": selector_survivor_totals[index],
                "coordinates_with_a_survivor_after_selector": (
                    selector_nonempty_coordinate_counts[index]
                ),
            }
            for index, selector in enumerate(selectors)
        ],
        "unique_nonzero_product_bit_length_histogram": independent_product_histogram,
        "maximum_unique_nonzero_profile": maximum_record,
        "producer_comparison": producer_checks,
        "elimination_provenance": {
            "gauge_receipt": str(GAUGE_RECEIPT),
            "gauge_receipt_sha256": gauge_receipt_hash,
            "ordered_pivot_count": len(ordered_pivots),
            "free_coordinate_count": len(free_coordinates),
            "dense_handoff_pivot_count": dense_count,
            "early_sparse_pivot_count": len(early_sparse_pivots),
            "cross_tab": cross_tab,
            "dense_pivot_coordinates_sha256": canonical_hash(sorted(dense_pivots)),
            "early_sparse_pivot_coordinates_sha256": canonical_hash(
                sorted(early_sparse_pivots)
            ),
            "free_coordinates_sha256": canonical_hash(sorted(free_coordinates)),
            "checks": {
                "regions_partition_all_38048_coordinates": True,
                "all_581_dense_pivots_are_no_candidate": True,
                "all_2167_free_coordinates_are_unique_zero": True,
                "early_sparse_no_candidate_count_is_19181": (
                    cross_tab["early_sparse_pivots"]["outcome"]["no_candidate"]
                    == 19181
                ),
                "producer_cross_tab_exact": True,
            },
        },
        "inputs": {
            "checkpoint": {
                "path": str(CHECKPOINT),
                "sha256": checkpoint_hash,
            },
            "producer_receipt": {
                "path": str(PRODUCER_RECEIPT),
                "sha256": producer_receipt_hash,
            },
            "producer_script_read_not_imported": {
                "path": str(PRODUCER_SCRIPT),
                "sha256": file_sha256(PRODUCER_SCRIPT),
            },
            "source_artifacts": [input_record(item) for item in sources],
            "selector_artifacts": [input_record(item) for item in selectors],
        },
        "source_script": {
            "path": str(script_path),
            "sha256": file_sha256(script_path),
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native_self": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "completeness_statement": (
            "By Legendre's theorem, every reduced n/d with d>0, gcd(d,M)=1, "
            "n=r*d mod M, and 2*abs(n)*d<M occurs at a proper convergent of "
            "r/M; this audit explicitly tested every such proper convergent."
        ),
        "claim_boundary": (
            "This independently verifies a bounded coefficient-height census in "
            "one frozen p181 gauge. The 17,751 unique-zero coordinates, 535 "
            "unique-nonzero coordinates, and 19,762 no-candidate coordinates do "
            "not assemble a QQ multiplier vector, prove a QQ polynomial identity, "
            "identify a colon or saturation, close the secant chart, prove nullcone "
            "containment, or establish HC4."
        ),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(OUTPUT),
                "outcome": result["outcome"],
                "cross_tab": cross_tab,
                "wall_seconds": result["resources"]["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
