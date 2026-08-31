#!/usr/bin/env python3
"""Primary M70 census and one-way fresh audit for the p197 common minor."""

from __future__ import annotations

import collections
import hashlib
import json
import math
import platform
import resource
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SOURCE_PRIMES = (181, 2147483647, 2147483629)
SELECTOR_PRIMES = (173, 197)
AUDIT_PRIME = 2147482867
ALL_PRIMES = (181, 173, 197, 2147483647, 2147483629, AUDIT_PRIME)
SOURCE_MODULUS = 834715161561466408303
COORDINATE_COUNT = 38048
R197_HASH = "dfb318fa370a3bc01bf4013d760c8ffdfff61c695caeee2ec7151f91dd212164"
NORMALIZATION_RECEIPT = "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization.json"
NORMALIZATION_RECEIPT_HASH = "3c2f2ac3b2a0c98bb279e90a1fffe8aea68f8c8c4db85e15ced673d50648946e"
NORMALIZER_SCRIPT_HASH = "fdbed62134385b5412474cd40e70e25a69eea9c5284a6a06dc99ecc121c4d57e"
PREREG_HASH = "b203a118b302c50394a0188501e32d12cc077c85fca2b1513bed770f59a112f8"
WALL_CAP_SECONDS = 30.0
RSS_CAP_BYTES = 512_000_000
OUTCOME_LABELS = ("no_candidate", "unique_zero", "unique_nonzero", "ambiguous")
ARTIFACT_HASHES = {
    173: "385449532e894e3e745f6a7755df7c6313b41416c5d198cfe59d8bc945b25ea9",
    181: "03e8e2ea2c9530890387ecf6861c0cd254ade1ae0618af723be5c79a60f7c41e",
    197: "488b086aa9a1909484c7480e20439ab06b135c4d7ea896b12dc704814417fada",
    2147482867: "9947bcb94ea15ba67e7e67b2a6694b64896d621a584ddd5384cb9cead2e9d2bb",
    2147483629: "81d8e3699876829dd99b435cf0617c220e186c1890702128d560aacae9c440b3",
    2147483647: "9c5043ac740db09da3127aebaeeb52317bdfe334229e7833bd77452cad04d0ab",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: object) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def guard(started: float, initial_swaps: int, stage: str) -> None:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if native_max_rss_bytes() >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {native_max_rss_bytes()}")
    if int(usage.ru_nswap) != initial_swaps:
        raise MemoryError(f"process swap count changed during {stage}")


def strict_product_candidates(residue: int, modulus: int):
    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0
    old_remainder, remainder = modulus, residue
    old_coefficient, coefficient = 0, 1
    candidates = set()
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
        old_remainder, remainder = remainder, old_remainder - quotient * remainder
        old_coefficient, coefficient = coefficient, old_coefficient - quotient * coefficient
    return sorted(candidates), steps


def crt_setup(primes):
    modulus = 1
    stages = []
    for prime in primes:
        inverse = pow(modulus % prime, -1, prime)
        stages.append((prime, modulus, inverse))
        modulus *= prime
    return stages, modulus


def crt(residues, stages):
    value = 0
    for residue, (prime, modulus, inverse) in zip(residues, stages, strict=True):
        value += modulus * (((residue - value) % prime) * inverse % prime)
    return value


def load_inputs(campaign: Path):
    prereg = campaign / "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md"
    normalizer_script = campaign / "scripts/normalize_j2_secant_r10_third_colon_koszul_p197_common_minor.py"
    receipt_path = campaign / NORMALIZATION_RECEIPT
    if sha256_bytes(prereg.read_bytes()) != PREREG_HASH:
        raise ValueError("preregistration changed")
    if sha256_bytes(normalizer_script.read_bytes()) != NORMALIZER_SCRIPT_HASH:
        raise ValueError("normalizer source changed")
    if sha256_bytes(receipt_path.read_bytes()) != NORMALIZATION_RECEIPT_HASH:
        raise ValueError("normalization receipt changed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("status") != "PASS_SIX_PRIME_P197_COMMON_MINOR_NORMALIZATION"
        or receipt.get("hashes", {}).get("ordered_R197_sha256") != R197_HASH
        or not all(bool(value) for value in receipt.get("checks", {}).values())
        or int(receipt.get("resources", {}).get("process_swap_delta", -1)) != 0
    ):
        raise ValueError("normalization receipt is not a passing bound input")
    artifacts = {}
    bindings = {}
    for prime in ALL_PRIMES:
        relative = f"artifacts/j2-secant-r10-third-colon-koszul-p197-common-minor-normalized-p{prime}.json"
        path = campaign / relative
        observed_hash = sha256_bytes(path.read_bytes())
        manifest = receipt["hashes"]["normalized_artifacts"][str(prime)]
        if observed_hash != ARTIFACT_HASHES[prime] or manifest.get("sha256") != observed_hash:
            raise ValueError(f"normalized artifact changed at p{prime}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        role = "fresh_audit_only" if prime == AUDIT_PRIME else "primary"
        vector = list(map(int, payload.get("normalized_coordinate_vector", [])))
        if (
            payload.get("status") != "PASS_P197_COMMON_MINOR_NORMALIZED_MODULAR_IDENTITY"
            or int(payload.get("characteristic", -1)) != prime
            or payload.get("role") != role
            or payload.get("common_minor", {}).get("ordered_coordinates_sha256") != R197_HASH
            or int(payload.get("common_minor", {}).get("rank", -1)) != 2053
            or not int(payload.get("common_minor", {}).get("determinant_mod_p", 0))
            or len(vector) != COORDINATE_COUNT
            or canonical_hash(vector) != payload.get("normalized_coordinate_vector_sha256")
            or not all(bool(value) for value in payload.get("checks", {}).values())
        ):
            raise ValueError(f"malformed normalized artifact at p{prime}")
        artifacts[prime] = vector
        bindings[str(prime)] = {
            "role": role,
            "path": relative,
            "sha256": observed_hash,
            "normalized_coordinate_vector_sha256": payload["normalized_coordinate_vector_sha256"],
        }
    return artifacts, bindings, receipt


def classify_primary(vectors, started, initial_swaps):
    stages, modulus = crt_setup(SOURCE_PRIMES)
    if modulus != SOURCE_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("primary M70 modulus changed")
    counts = collections.Counter()
    coordinates_by_outcome = {label: [] for label in OUTCOME_LABELS}
    labels = []
    candidate_count_vector = []
    eea_step_count_vector = []
    selector_count_vectors = [[] for _ in SELECTOR_PRIMES]
    candidate_histogram = collections.Counter()
    survivor_histogram = collections.Counter()
    product_height_histogram = collections.Counter()
    combined_residues = []
    survivor_records = []
    unique_height_records = []
    survivors_by_coordinate = []
    candidate_hasher = hashlib.sha256()
    selector_hashers = [hashlib.sha256() for _ in SELECTOR_PRIMES]
    outcome_hasher = hashlib.sha256()
    survivor_hasher = hashlib.sha256()
    total_candidates = total_steps = 0
    maximum_profile = None
    for coordinate in range(COORDINATE_COUNT):
        source_residues = [vectors[prime][coordinate] for prime in SOURCE_PRIMES]
        combined = crt(source_residues, stages)
        combined_residues.append(str(combined))
        candidates, steps = strict_product_candidates(combined, modulus)
        total_candidates += len(candidates)
        total_steps += steps
        candidate_count_vector.append(len(candidates))
        eea_step_count_vector.append(steps)
        candidate_histogram[len(candidates)] += 1
        candidate_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in candidates:
            candidate_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        candidate_hasher.update(b"\n")
        survivors = candidates
        for selector_index, prime in enumerate(SELECTOR_PRIMES):
            observed = vectors[prime][coordinate]
            survivors = [
                (numerator, denominator)
                for numerator, denominator in survivors
                if denominator % prime
                and numerator % prime * pow(denominator % prime, -1, prime) % prime == observed
            ]
            selector_count_vectors[selector_index].append(len(survivors))
            selector_hashers[selector_index].update(f"{coordinate}:".encode("ascii"))
            for numerator, denominator in survivors:
                selector_hashers[selector_index].update(f"{numerator}/{denominator};".encode("ascii"))
            selector_hashers[selector_index].update(b"\n")
        survivors_by_coordinate.append(tuple(survivors))
        survivor_histogram[len(survivors)] += 1
        if survivors:
            survivor_records.append({
                "coordinate": coordinate,
                "candidates": [[str(numerator), str(denominator)] for numerator, denominator in survivors],
            })
        survivor_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in survivors:
            survivor_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        survivor_hasher.update(b"\n")
        if not survivors:
            label = "no_candidate"
        elif len(survivors) > 1:
            label = "ambiguous"
        else:
            numerator, denominator = survivors[0]
            label = "unique_zero" if numerator == 0 else "unique_nonzero"
            product = 2 * abs(numerator) * denominator
            profile = {
                "coordinate": coordinate,
                "numerator": str(numerator),
                "positive_denominator": str(denominator),
                "twice_absolute_product": str(product),
                "twice_product_bit_length": product.bit_length(),
                "absolute_numerator_bit_length": abs(numerator).bit_length(),
                "denominator_bit_length": denominator.bit_length(),
            }
            unique_height_records.append(profile)
            product_height_histogram[product.bit_length()] += 1
            ranking = (product.bit_length(), abs(numerator).bit_length(), denominator.bit_length(), coordinate)
            if maximum_profile is None or ranking > maximum_profile[0]:
                maximum_profile = (ranking, profile)
        counts[label] += 1
        coordinates_by_outcome[label].append(coordinate)
        labels.append(label)
        outcome_hasher.update(f"{coordinate}:{label}\n".encode("ascii"))
        if coordinate % 2048 == 0:
            guard(started, initial_swaps, "primary M70 census")
    normalized_counts = {label: counts[label] for label in OUTCOME_LABELS}
    if sum(normalized_counts.values()) != COORDINATE_COUNT:
        raise AssertionError("primary outcomes do not cover all coordinates")
    primary = {
        "source_characteristics": list(SOURCE_PRIMES),
        "selector_characteristics": list(SELECTOR_PRIMES),
        "selector_assurance": "confirmatory primary selectors; p173 and p197 are not fully held out",
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "outcome": normalized_counts,
        "U_no_candidate_plus_ambiguous": counts["no_candidate"] + counts["ambiguous"],
        "outcome_label_vector": labels,
        "coordinates_by_outcome": coordinates_by_outcome,
        "nonempty_survivor_records": survivor_records,
        "unique_candidate_height_records": unique_height_records,
        "maximum_unique_candidate_height_profile": None if maximum_profile is None else maximum_profile[1],
        "candidate_enumeration": {
            "total_candidates_before_selectors": total_candidates,
            "total_extended_euclid_steps": total_steps,
            "candidate_count_vector": candidate_count_vector,
            "extended_euclid_step_count_vector": eea_step_count_vector,
            "candidate_count_histogram": {str(key): value for key, value in sorted(candidate_histogram.items())},
            "final_survivor_count_histogram": {str(key): value for key, value in sorted(survivor_histogram.items())},
            "unique_candidate_product_bit_length_histogram": {str(key): value for key, value in sorted(product_height_histogram.items())},
        },
        "hashes": {
            "combined_crt_residue_vector_sha256": canonical_hash(combined_residues),
            "candidate_count_vector_sha256": canonical_hash(candidate_count_vector),
            "extended_euclid_step_count_vector_sha256": canonical_hash(eea_step_count_vector),
            "complete_candidate_text_stream_sha256": candidate_hasher.hexdigest(),
            "selector_survivor_count_vector_sha256": {
                str(prime): canonical_hash(selector_count_vectors[index])
                for index, prime in enumerate(SELECTOR_PRIMES)
            },
            "selector_survivor_text_stream_sha256": {
                str(prime): selector_hashers[index].hexdigest()
                for index, prime in enumerate(SELECTOR_PRIMES)
            },
            "final_survivor_text_stream_sha256": survivor_hasher.hexdigest(),
            "nonempty_survivor_records_sha256": canonical_hash(survivor_records),
            "outcome_label_vector_sha256": canonical_hash(labels),
            "outcome_text_stream_sha256": outcome_hasher.hexdigest(),
            "coordinates_by_outcome_sha256": {
                label: canonical_hash(values) for label, values in coordinates_by_outcome.items()
            },
            "unique_candidate_height_records_sha256": canonical_hash(unique_height_records),
        },
    }
    commitment = {
        "outcome": primary["outcome"],
        "U": primary["U_no_candidate_plus_ambiguous"],
        "hashes": primary["hashes"],
    }
    return primary, survivors_by_coordinate, canonical_hash(commitment)


def apply_fresh_audit(primary, survivors_by_coordinate, audit_vector, commitment_before):
    decision_hasher = hashlib.sha256()
    survivor_hasher = hashlib.sha256()
    tested = rejected = survived = denominator_failures = 0
    coordinates_with_primary_survivors = 0
    unique_rejected_coordinates = []
    ambiguous_reduced = collections.Counter()
    audit_survivor_records = []
    for coordinate, candidates in enumerate(survivors_by_coordinate):
        if candidates:
            coordinates_with_primary_survivors += 1
        audit_survivors = []
        observed = audit_vector[coordinate]
        for numerator, denominator in candidates:
            tested += 1
            if denominator % AUDIT_PRIME == 0:
                decision = "reject_denominator_zero"
                denominator_failures += 1
                rejected += 1
            elif numerator % AUDIT_PRIME * pow(denominator % AUDIT_PRIME, -1, AUDIT_PRIME) % AUDIT_PRIME != observed:
                decision = "reject_residue_mismatch"
                rejected += 1
            else:
                decision = "survive"
                survived += 1
                audit_survivors.append((numerator, denominator))
            decision_hasher.update(f"{coordinate}:{numerator}/{denominator}:{decision}\n".encode("ascii"))
        if len(candidates) == 1 and not audit_survivors:
            unique_rejected_coordinates.append(coordinate)
        if len(candidates) > 1:
            category = "zero" if not audit_survivors else "one" if len(audit_survivors) == 1 else "multiple"
            ambiguous_reduced[category] += 1
        survivor_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in audit_survivors:
            survivor_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        survivor_hasher.update(b"\n")
        if audit_survivors:
            audit_survivor_records.append({
                "coordinate": coordinate,
                "candidates": [[str(numerator), str(denominator)] for numerator, denominator in audit_survivors],
            })
    commitment_after = canonical_hash({
        "outcome": primary["outcome"],
        "U": primary["U_no_candidate_plus_ambiguous"],
        "hashes": primary["hashes"],
    })
    if commitment_after != commitment_before:
        raise AssertionError("fresh audit altered the primary stream")
    return {
        "characteristic": AUDIT_PRIME,
        "role": "fresh one-way audit-only falsifier",
        "coordinates_with_primary_survivors": coordinates_with_primary_survivors,
        "candidates_tested": tested,
        "candidates_rejected": rejected,
        "candidates_surviving": survived,
        "primary_unique_candidates_rejected": len(unique_rejected_coordinates),
        "primary_unique_candidate_rejected_coordinates": unique_rejected_coordinates,
        "ambiguous_sets_reduced_to_zero": ambiguous_reduced["zero"],
        "ambiguous_sets_reduced_to_one": ambiguous_reduced["one"],
        "ambiguous_sets_remaining_multiple": ambiguous_reduced["multiple"],
        "audit_denominator_failures": denominator_failures,
        "audit_survivor_records": audit_survivor_records,
        "audit_decision_text_stream_sha256": decision_hasher.hexdigest(),
        "audit_survivor_text_stream_sha256": survivor_hasher.hexdigest(),
        "audit_survivor_records_sha256": canonical_hash(audit_survivor_records),
        "primary_commitment_before_audit_sha256": commitment_before,
        "primary_commitment_after_audit_sha256": commitment_after,
        "primary_counts_or_U_changed": False,
        "primary_no_candidate_rescued": False,
    }


def route_interpretation(primary, audit):
    value = int(primary["U_no_candidate_plus_ambiguous"])
    unique_rejected = int(audit["primary_unique_candidates_rejected"])
    if unique_rejected:
        status = "FRESH_AUDIT_FALSIFIED_PRIMARY_CANDIDATE"
    else:
        status = "PASS_PRIMARY_M70_AND_FRESH_AUDIT"
    if value == 0 and not unique_rejected:
        band = "decisive"
        next_route = "freeze; separate preregistration required for QQ assembly and replay"
    elif value <= 8879:
        band = "strong_but_incomplete"
        next_route = "move to exact-solve design; no automatic prime extension"
    elif value <= 14206:
        band = "intermediate"
        next_route = "move to residual-114 or direct p-adic/exact solve; add no primes"
    else:
        band = "route_stop"
        next_route = "add no primes and do not modify R or introduce a third gauge"
    if unique_rejected:
        next_route = "forbid QQ assembly; audit falsified at least one primary unique candidate"
    return status, {"U": value, "band": band, "next_route": next_route}


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-m70-census.json"
    signal.signal(signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("30-second alarm")))
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        load_started = time.perf_counter()
        vectors, bindings, normalization = load_inputs(campaign)
        load_seconds = time.perf_counter() - load_started
        guard(started, initial_swaps, "input load")
        primary_started = time.perf_counter()
        primary, survivors, primary_commitment = classify_primary(vectors, started, initial_swaps)
        primary_seconds = time.perf_counter() - primary_started
        audit_started = time.perf_counter()
        audit = apply_fresh_audit(primary, survivors, vectors[AUDIT_PRIME], primary_commitment)
        audit_seconds = time.perf_counter() - audit_started
        status, interpretation = route_interpretation(primary, audit)
        guard(started, initial_swaps, "fresh audit")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        final_swaps = int(usage.ru_nswap)
        receipt = {
            "schema": "hc4.third-colon-koszul-p197-common-minor-m70-census.v1",
            "status": status,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "assurance": "complete primary strict-product M70 census plus separate one-way fresh audit falsification",
            "claim_boundary": (
                "This receipt reports a bounded coordinatewise modular-height census and an audit-only falsification. It does not assemble a QQ multiplier, prove QQ membership, compute a colon or saturation, establish residual dimension 114, close a secant chart, prove nullcone containment, or prove HC4. Finite-modulus candidates are not rational coefficients."
            ),
            "retrospective_feasibility_disclosure": normalization["retrospective_feasibility_disclosure"],
            "method": {
                "primary_sources": list(SOURCE_PRIMES),
                "primary_selectors": list(SELECTOR_PRIMES),
                "primary_selector_assurance": "confirmatory and not fully held out",
                "fresh_audit_selector": AUDIT_PRIME,
                "fresh_audit_is_one_way": True,
                "fresh_audit_can_change_primary_counts_or_U": False,
                "candidate_assembly_performed": False,
                "additional_minor_gauge_or_prime_used": False,
            },
            "normalization_input": {
                "receipt_path": NORMALIZATION_RECEIPT,
                "receipt_sha256": NORMALIZATION_RECEIPT_HASH,
                "producer_script_sha256": NORMALIZER_SCRIPT_HASH,
                "ordered_R197_sha256": R197_HASH,
                "normalized_artifacts": bindings,
            },
            "primary_census": primary,
            "fresh_audit": audit,
            "interpretation": interpretation,
            "checks": {
                "all_38048_primary_coordinates_classified": sum(primary["outcome"].values()) == COORDINATE_COUNT,
                "primary_outcome_stream_frozen_before_audit": True,
                "primary_commitment_unchanged_by_audit": audit["primary_commitment_before_audit_sha256"] == audit["primary_commitment_after_audit_sha256"],
                "fresh_audit_did_not_rescue_no_candidate": not audit["primary_no_candidate_rescued"],
                "no_QQ_multiplier_assembled": True,
                "zero_process_swap_gate": final_swaps == initial_swaps,
            },
            "source_script": {
                "path": str(script_path.relative_to(campaign)),
                "sha256": sha256_bytes(script_path.read_bytes()),
                "imports_normalizer_or_previous_census": False,
            },
            "resources": {
                "wall_cap_seconds": WALL_CAP_SECONDS,
                "rss_cap_bytes": RSS_CAP_BYTES,
                "initial_process_swaps": initial_swaps,
                "final_process_swaps": final_swaps,
                "process_swap_delta": final_swaps - initial_swaps,
                "maximum_rss_native": native_max_rss_bytes(),
                "user_cpu_seconds": usage.ru_utime,
                "system_cpu_seconds": usage.ru_stime,
            },
            "timings": {
                "load_validation_seconds": load_seconds,
                "primary_census_seconds": primary_seconds,
                "fresh_audit_seconds": audit_seconds,
                "total_wall_seconds": time.perf_counter() - started,
            },
        }
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": status, "output": str(output), "outcome": primary["outcome"], "U": interpretation["U"], "fresh_audit_unique_rejections": audit["primary_unique_candidates_rejected"], "wall_seconds": receipt["timings"]["total_wall_seconds"]}, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-p197-common-minor-m70-census.v1",
            "status": "FAIL_CLOSED_P197_COMMON_MINOR_M70_CENSUS",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No primary census, audit, rational reconstruction, QQ identity, colon, saturation, secant, nullcone, or HC4 conclusion is licensed by this failed run.",
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swap_delta": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap) - initial_swaps,
        }
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
