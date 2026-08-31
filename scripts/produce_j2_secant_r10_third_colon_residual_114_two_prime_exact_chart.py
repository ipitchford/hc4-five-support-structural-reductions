#!/usr/bin/env sage-python
"""Produce a quarantined two-prime extension of the residual-114 chart.

Final artifact promotion is intentionally outside this process.  The gated
wrapper promotes the staged payloads only after literal external time/RSS/swap
and one-algebra-process checks pass.
"""

from __future__ import annotations

import argparse
import collections
import gc
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

import sympy as sp


FRESH_PRIMES = (2147482859, 2147482819)
OLD_SOURCE_PRIMES = (181, 2147483647, 2147483629)
SOURCE_PRIMES = OLD_SOURCE_PRIMES + FRESH_PRIMES
SELECTOR_PRIMES = (173, 197)
ALL_REDUCTION_PRIMES = SOURCE_PRIMES + SELECTOR_PRIMES
SOURCE_MODULUS = 3849441339617793628491685360024838922863
KOSZUL_COUNT = 2053
FREE_COUNT = 2167
QUOTIENT_COUNT = 114
ENTRY_COUNT = KOSZUL_COUNT * QUOTIENT_COUNT
INTERNAL_WALL_CAP_SECONDS = 175.0
RSS_CAP_BYTES = 1_000_000_000

PREREGISTRATION = (
    "research/THIRD_COLON_RESIDUAL_114_TWO_PRIME_EXACT_CHART_EXTENSION_"
    "PREREGISTRATION.md"
)
PREREGISTRATION_HASH = "cc01cb96c1738316100bc46eab2c5ce5c8e23402da7b95d2483f0fab80f0ac10"
OLD_ARTIFACT = "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
OLD_RECEIPT = "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json"
FINAL_ARTIFACT = (
    "artifacts/j2-secant-r10-third-colon-residual-114-two-prime-exact-chart.json"
)
FINAL_RECEIPT = (
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-two-prime-exact-chart.json"
)

FROZEN_FILES = {
    PREREGISTRATION: PREREGISTRATION_HASH,
    "research/THIRD_COLON_RESIDUAL_114_QUOTIENT_SCOUT_PREREGISTRATION.md": "112fb4ea3de68c84459422903e0c6f3c4c2902d364b13639f130c2a7f6cebf22",
    "scripts/scout_j2_secant_r10_third_colon_residual_114_quotient.py": "607706e89e25990ed3ed1bdd5f7d9a972c824b0bff62a33035789860f75f3b81",
    OLD_ARTIFACT: "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74",
    OLD_RECEIPT: "652af633649c32af3322b9405eac8d6e60fdaba5668817de6a11330782bc752a",
    "scripts/audit_j2_secant_r10_third_colon_residual_114_quotient_independent.py": "81ad24d01ae70a0ca2731259753d99a429bd48ae288e77105120dd800009396d",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json": "7eba0e65e40abd7eea0065ecd84c3803237fa9cc5c51391f3202b4d300b7185a",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit-external-telemetry.json": "831c4ce5bcd6fdb0451209db1a8b0cbafabeec3e605c3235836c09cd42dac91e",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py": "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
}

EXPECTED_HASHES = {
    "free": "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1",
    "pivots": "2efe83231c64aa75acef667eef372e85258daeaebfd8c8a4d5c40544302e30af",
    "complement": "d21c06344201de364b804212941a3f405c5cbe1d02e67396150db0e6afca7a17",
    "K_F": "328089ba8f77ef48133e6600af73eabc81a456b35d14bcd8026d649db925f55e",
    "B": "025fd2081fda9fe325ba3edfa68dbc488c4007429d7420f8842d3b411a3252b2",
    "C": "0c8190cc3b9cbfb0b33fef32d8e4a0ba2e40f2545ea7b50c64bfb6f8f3876058",
    "K_stream": "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856",
}

OLD_TRANSITION_HASHES = {
    181: "5aea98233b15d428dfc2b3614bb145403ed47c434d1fc6c4925ed30d47bfff57",
    173: "81aafb0e8ed3cfbfe26607b4bc7c81b3402e78134a6276f50dc8e7726aefee49",
    197: "dbfbbdb1f4fb49c2379a7f3f81c2742c95e79733cf8f59f8cc9428213973d18a",
    2147483647: "30daa3b6f58dcca0800965e80bea985dbe1470fe395bb6227961735fbf602b17",
    2147483629: "e0685b4e6c02d572c17a6f558fa17c4202bf29e5fede93b3bb9e4d3c22011a3e",
}


class RouteFailure(RuntimeError):
    def __init__(self, message: str, partial: dict | None = None):
        super().__init__(message)
        self.partial = partial


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


class CanonicalListHasher:
    def __init__(self) -> None:
        self._hash = hashlib.sha256()
        self._hash.update(b"[")
        self._first = True
        self.count = 0

    def add(self, value: object) -> None:
        if not self._first:
            self._hash.update(b",")
        self._hash.update(canonical_bytes(value))
        self._first = False
        self.count += 1

    def hexdigest(self) -> str:
        clone = self._hash.copy()
        clone.update(b"]")
        return clone.hexdigest()


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def guard(started: float, initial_swaps: int, stage: str) -> None:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    rss = native_max_rss_bytes()
    if wall >= INTERNAL_WALL_CAP_SECONDS:
        raise TimeoutError(f"internal wall cap reached during {stage}: {wall:.6f}s")
    if rss >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {rss}")
    if initial_swaps != 0 or int(usage.ru_nswap) != 0:
        raise MemoryError(f"literal process swap count is nonzero during {stage}")


def write_new_json(path: Path, value: object, *, compact: bool) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite staged output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        if compact
        else json.dumps(value, indent=2, sort_keys=True) + "\n"
    )
    with path.open("x", encoding="ascii") as handle:
        handle.write(text)


def validate_frozen_lineage(campaign: Path):
    for relative, expected in FROZEN_FILES.items():
        observed = sha256_bytes((campaign / relative).read_bytes())
        if observed != expected:
            raise ValueError(f"frozen input changed: {relative}: {observed}")

    old_receipt = json.loads((campaign / OLD_RECEIPT).read_text(encoding="utf-8"))
    if (
        old_receipt.get("status")
        != "PASS_STRONG_INCOMPLETE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL"
        or old_receipt.get("interpretation", {}).get("U") != 1903
        or old_receipt.get("structural_artifact", {}).get("sha256")
        != FROZEN_FILES[OLD_ARTIFACT]
        or not all(old_receipt.get("checks", {}).values())
        or old_receipt.get("resources", {}).get("initial_process_swaps") != 0
        or old_receipt.get("resources", {}).get("final_process_swaps") != 0
    ):
        raise ValueError("completed quotient-scout receipt is not the frozen PASS")

    audit = json.loads(
        (
            campaign
            / "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json"
        ).read_text(encoding="utf-8")
    )
    telemetry = json.loads(
        (
            campaign
            / "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit-external-telemetry.json"
        ).read_text(encoding="utf-8")
    )
    if (
        audit.get("status") != "PASS_INDEPENDENT_RESIDUAL_114_QUOTIENT_AND_M70_REPLAY"
        or audit.get("resources", {}).get("initial_process_swaps") != 0
        or audit.get("resources", {}).get("final_process_swaps") != 0
        or telemetry.get("status") != "PASS_EXTERNAL_RESOURCE_GATED_INDEPENDENT_REPLAY"
        or telemetry.get("external_telemetry", {}).get("exit_status") != 0
        or telemetry.get("external_telemetry", {}).get("process_swaps") != 0
        or not all(telemetry.get("gates", {}).values())
    ):
        raise ValueError("independent quotient audit lineage is not the frozen PASS")
    return old_receipt, audit, telemetry


def validate_fresh_prime_rule() -> dict:
    first, second = FRESH_PRIMES
    primality = {str(prime): bool(sp.isprime(prime)) for prime in FRESH_PRIMES}
    predecessor = {
        "previous_prime_2147482867": int(sp.prevprime(2147482867)),
        "previous_prime_2147482859": int(sp.prevprime(first)),
    }
    if not all(primality.values()) or predecessor != {
        "previous_prime_2147482867": first,
        "previous_prime_2147482859": second,
    }:
        raise ValueError("fresh-prime rule failed exact verification")
    if 2147482867 in SOURCE_PRIMES or 2147482867 in SELECTOR_PRIMES:
        raise AssertionError("forbidden already-used audit characteristic entered roles")
    product = math.prod(SOURCE_PRIMES)
    if product != SOURCE_MODULUS or product.bit_length() != 132:
        raise ValueError("five-source modulus changed")
    return {
        "authorized_fresh_characteristics_in_order": list(FRESH_PRIMES),
        "exact_primality": primality,
        "exact_predecessor_chain": predecessor,
        "forbidden_characteristic_2147482867_used": False,
        "source_characteristics_in_order": list(SOURCE_PRIMES),
        "selector_characteristics_in_order": list(SELECTOR_PRIMES),
        "source_modulus": str(product),
        "source_modulus_bit_length": product.bit_length(),
        "adaptive_prime_choice_used": False,
    }


def reconstruct_integer_chart(campaign: Path, started: float, initial_swaps: int):
    sys.path.insert(0, str(campaign / "scripts"))
    import scout_j2_secant_r10_third_colon_residual_114_quotient as legacy

    legacy.WALL_CAP_SECONDS = INTERNAL_WALL_CAP_SECONDS
    legacy.RSS_CAP_BYTES = RSS_CAP_BYTES
    artifact = json.loads((campaign / OLD_ARTIFACT).read_text(encoding="utf-8"))
    if artifact.get("status") != "PASS_FIVE_FIBRE_COMMON_RESIDUAL_114_QUOTIENT_CHART":
        raise ValueError("frozen structural artifact status changed")
    if not all(artifact.get("checks", {}).values()):
        raise ValueError("frozen structural artifact contains a failed check")

    free = list(map(int, artifact.get("ordered_free_absolute_coordinates", [])))
    if len(free) != FREE_COUNT or canonical_hash(free) != EXPECTED_HASHES["free"]:
        raise ValueError("frozen free-coordinate list changed")
    integer_koszul = legacy.reconstruct_koszul(campaign, started, initial_swaps)
    restricted, _absolute_to_local = legacy.restrict_koszul(integer_koszul, free)
    pivots, pivot_telemetry = legacy.select_lexicographic_p181_pivots(
        restricted, started, initial_swaps
    )
    complement = sorted(set(range(FREE_COUNT)) - set(pivots))
    b_rows, c_rows = legacy.split_integer_matrices(restricted, pivots, complement)

    restricted_decimal = [
        [[column, str(value)] for column, value in row] for row in restricted
    ]
    b_decimal = [[[column, str(value)] for column, value in row] for row in b_rows]
    c_decimal = [[[column, str(value)] for column, value in row] for row in c_rows]
    observed_hashes = {
        "free": canonical_hash(free),
        "pivots": canonical_hash(pivots),
        "complement": canonical_hash(complement),
        "K_F": canonical_hash(restricted_decimal),
        "B": canonical_hash(b_decimal),
        "C": canonical_hash(c_decimal),
        "K_stream": artifact.get("hashes", {}).get(
            "integer_koszul_content_invariant_stream_sha256"
        ),
    }
    if observed_hashes != EXPECTED_HASHES:
        raise ValueError(f"integer chart hash mismatch: {observed_hashes}")
    if (
        restricted_decimal != artifact.get("restricted_K_F_sparse_integer_rows")
        or b_decimal != artifact.get("B_sparse_integer_rows")
        or c_decimal != artifact.get("C_sparse_integer_rows")
        or pivots != artifact.get("ordered_pivot_local_coordinates_discovery_order")
        or complement != artifact.get("ordered_complement_local_coordinates_increasing")
    ):
        raise ValueError("rebuilt integer chart payload differs from frozen artifact")

    transitions = {}
    transition_bindings = {}
    for prime in OLD_TRANSITION_HASHES:
        record = artifact.get("prime_records", {}).get(str(prime), {})
        matrix = [list(map(int, row)) for row in record.get("transition_matrix_row_major", [])]
        if (
            len(matrix) != KOSZUL_COUNT
            or any(len(row) != QUOTIENT_COUNT for row in matrix)
            or canonical_hash(matrix) != OLD_TRANSITION_HASHES[prime]
            or record.get("rank") != KOSZUL_COUNT
            or record.get("BT_equals_C_replay", {}).get("mismatch_count") != 0
            or record.get("koszul_quotient_annihilation_replay", {}).get("mismatch_count")
            != 0
        ):
            raise ValueError(f"frozen transition payload changed at p{prime}")
        transitions[prime] = matrix
        transition_bindings[str(prime)] = {
            "role": "old_source" if prime in OLD_SOURCE_PRIMES else "confirmatory_selector",
            "row_major_sha256": OLD_TRANSITION_HASHES[prime],
            "nonzero_count": sum(value != 0 for row in matrix for value in row),
            "source": OLD_ARTIFACT,
        }
    guard(started, initial_swaps, "integer chart reconstruction")
    return legacy, artifact, restricted, pivots, complement, b_rows, c_rows, transitions, {
        "observed_hashes": observed_hashes,
        "dimensions": {
            "K_F_shape": [KOSZUL_COUNT, FREE_COUNT],
            "K_F_nonzero_count": sum(map(len, restricted)),
            "B_shape": [KOSZUL_COUNT, KOSZUL_COUNT],
            "B_nonzero_count": sum(map(len, b_rows)),
            "C_shape": [KOSZUL_COUNT, QUOTIENT_COUNT],
            "C_nonzero_count": sum(map(len, c_rows)),
        },
        "p181_pivot_reconstruction": pivot_telemetry,
        "old_transition_bindings": transition_bindings,
    }


def solve_fresh_fibres(
    legacy,
    b_rows,
    c_rows,
    restricted,
    pivots,
    complement,
    transitions,
    started,
    initial_swaps,
):
    records = {}
    for prime in FRESH_PRIMES:
        matrix, telemetry = legacy.solve_transition(
            prime,
            b_rows,
            c_rows,
            restricted,
            pivots,
            complement,
            started,
            initial_swaps,
        )
        if (
            telemetry.get("rank") != KOSZUL_COUNT
            or telemetry.get("row_or_column_swap_count") != 0
            or telemetry.get("adaptive_minor_repair_used")
            or telemetry.get("BT_equals_C_replay", {}).get("mismatch_count") != 0
            or telemetry.get("koszul_quotient_annihilation_replay", {}).get(
                "mismatch_count"
            )
            != 0
        ):
            raise RouteFailure(f"fresh fixed-B fibre failed at p{prime}")
        transitions[prime] = matrix
        records[str(prime)] = {
            **telemetry,
            "transition_matrix_row_major": matrix,
            "characteristic": prime,
            "role": "fresh_CRT_source_fixed_before_outcome",
        }
        gc.collect()
        guard(started, initial_swaps, f"fresh fixed-B fibre p{prime}")
    return records


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


def reconstruct_all_entries(legacy, transitions, started, initial_swaps):
    stages, modulus = crt_setup(SOURCE_PRIMES)
    if modulus != SOURCE_MODULUS:
        raise AssertionError("132-bit source modulus changed")
    counts = collections.Counter()
    candidate_histogram = collections.Counter()
    survivor_histogram = collections.Counter()
    eea_histogram = collections.Counter()
    selector_survivor_totals = collections.Counter()
    total_candidates = 0
    total_steps = 0
    max_steps = 0
    pairs = []
    denominators = []
    support = []

    residue_stream = CanonicalListHasher()
    candidate_stream = CanonicalListHasher()
    candidate_count_stream = CanonicalListHasher()
    eea_stream = CanonicalListHasher()
    survivor_stream = CanonicalListHasher()
    outcome_stream = CanonicalListHasher()
    height_stream = CanonicalListHasher()
    no_candidate_stream = CanonicalListHasher()
    ambiguous_stream = CanonicalListHasher()
    denominator_failure_stream = CanonicalListHasher()
    noncanonical_fraction_stream = CanonicalListHasher()

    for row_index in range(KOSZUL_COUNT):
        for quotient_column in range(QUOTIENT_COUNT):
            entry_index = row_index * QUOTIENT_COUNT + quotient_column
            residues = [
                transitions[prime][row_index][quotient_column] for prime in SOURCE_PRIMES
            ]
            combined = crt(residues, stages)
            candidates, steps = legacy.strict_product_candidates(combined, modulus)
            residue_stream.add(str(combined))
            candidate_stream.add(
                [entry_index, [[str(n), str(d)] for n, d in candidates]]
            )
            candidate_count_stream.add(len(candidates))
            eea_stream.add(steps)
            candidate_histogram[len(candidates)] += 1
            eea_histogram[steps] += 1
            total_candidates += len(candidates)
            total_steps += steps
            max_steps = max(max_steps, steps)

            survivors = candidates
            for selector in SELECTOR_PRIMES:
                observed = transitions[selector][row_index][quotient_column]
                selected = []
                for numerator, denominator in survivors:
                    if denominator % selector == 0:
                        denominator_failure_stream.add(
                            [entry_index, selector, str(numerator), str(denominator)]
                        )
                        continue
                    reduced = (
                        numerator % selector
                        * pow(denominator % selector, -1, selector)
                        % selector
                    )
                    if reduced == observed:
                        selected.append((numerator, denominator))
                survivors = selected
                selector_survivor_totals[selector] += len(survivors)

            survivor_stream.add(
                [entry_index, [[str(n), str(d)] for n, d in survivors]]
            )
            survivor_histogram[len(survivors)] += 1
            if not survivors:
                label = "no_candidate"
                no_candidate_stream.add(entry_index)
                pairs.append(None)
            elif len(survivors) != 1:
                label = "ambiguous"
                ambiguous_stream.add(
                    [entry_index, [[str(n), str(d)] for n, d in survivors]]
                )
                pairs.append(None)
            else:
                numerator, denominator = survivors[0]
                canonical = (
                    denominator > 0
                    and math.gcd(abs(numerator), denominator) == 1
                    and math.gcd(denominator, modulus) == 1
                    and (numerator != 0 or denominator == 1)
                )
                if not canonical:
                    noncanonical_fraction_stream.add(
                        [entry_index, str(numerator), str(denominator)]
                    )
                    label = "noncanonical_fraction"
                    pairs.append(None)
                else:
                    label = "unique_zero" if numerator == 0 else "unique_nonzero"
                    pairs.append((numerator, denominator))
                    denominators.append(denominator)
                    if numerator:
                        support.append(entry_index)
                    product = 2 * abs(numerator) * denominator
                    height_stream.add(
                        [
                            entry_index,
                            abs(numerator).bit_length(),
                            denominator.bit_length(),
                            product.bit_length(),
                            str(product),
                        ]
                    )
            counts[label] += 1
            outcome_stream.add([entry_index, label])
        if row_index % 64 == 0:
            guard(started, initial_swaps, "complete 132-bit reconstruction")

    normalized_counts = {
        key: counts[key]
        for key in (
            "no_candidate",
            "ambiguous",
            "noncanonical_fraction",
            "unique_zero",
            "unique_nonzero",
        )
    }
    census = {
        "entry_count": ENTRY_COUNT,
        "entry_order": "row-major over 2053 rows then 114 quotient columns",
        "source_characteristics_in_order": list(SOURCE_PRIMES),
        "selector_characteristics_in_order": list(SELECTOR_PRIMES),
        "selectors_are_confirmatory_and_not_held_out": True,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "outcome": normalized_counts,
        "U_no_candidate_plus_ambiguous": counts["no_candidate"] + counts["ambiguous"],
        "enumeration": {
            "total_preselector_candidates": total_candidates,
            "total_extended_euclid_steps": total_steps,
            "maximum_extended_euclid_steps_per_entry": max_steps,
            "candidate_count_histogram": {
                str(key): value for key, value in sorted(candidate_histogram.items())
            },
            "survivor_count_histogram": {
                str(key): value for key, value in sorted(survivor_histogram.items())
            },
            "extended_euclid_step_histogram": {
                str(key): value for key, value in sorted(eea_histogram.items())
            },
            "selector_survivor_totals": {
                str(prime): selector_survivor_totals[prime] for prime in SELECTOR_PRIMES
            },
        },
        "hashes": {
            "combined_CRT_residue_stream_sha256": residue_stream.hexdigest(),
            "complete_preselector_candidate_stream_sha256": candidate_stream.hexdigest(),
            "candidate_count_stream_sha256": candidate_count_stream.hexdigest(),
            "extended_euclid_step_stream_sha256": eea_stream.hexdigest(),
            "complete_surviving_candidate_stream_sha256": survivor_stream.hexdigest(),
            "complete_outcome_stream_sha256": outcome_stream.hexdigest(),
            "complete_height_stream_sha256": height_stream.hexdigest(),
            "no_candidate_failure_stream_sha256": no_candidate_stream.hexdigest(),
            "ambiguous_failure_stream_sha256": ambiguous_stream.hexdigest(),
            "denominator_failure_stream_sha256": denominator_failure_stream.hexdigest(),
            "noncanonical_fraction_failure_stream_sha256": noncanonical_fraction_stream.hexdigest(),
        },
        "failure_stream_record_counts": {
            "no_candidate": no_candidate_stream.count,
            "ambiguous": ambiguous_stream.count,
            "denominator_failure": denominator_failure_stream.count,
            "noncanonical_fraction": noncanonical_fraction_stream.count,
        },
    }
    if (
        sum(normalized_counts.values()) != ENTRY_COUNT
        or normalized_counts["no_candidate"] != 0
        or normalized_counts["ambiguous"] != 0
        or normalized_counts["noncanonical_fraction"] != 0
        or normalized_counts["unique_zero"] + normalized_counts["unique_nonzero"]
        != ENTRY_COUNT
        or denominator_failure_stream.count != 0
        or any(pair is None for pair in pairs)
    ):
        raise RouteFailure("complete 132-bit reconstruction did not attain U=0", census)
    return pairs, denominators, support, census


def assemble_primitive_chart(pairs, denominators, support, b_rows, c_rows, started, initial_swaps):
    global_denominator = 1
    for index, denominator in enumerate(denominators):
        global_denominator = math.lcm(global_denominator, denominator)
        if index % 512 == 0:
            guard(started, initial_swaps, "global denominator LCM")
    if global_denominator <= 0:
        raise AssertionError("global denominator is not positive")

    numerator_matrix = []
    pair_matrix_strings = []
    flat_pair_strings = []
    denominator_strings = []
    content = 0
    observed_support = []
    for row_index in range(KOSZUL_COUNT):
        numerator_row = []
        pair_row = []
        for quotient_column in range(QUOTIENT_COUNT):
            entry_index = row_index * QUOTIENT_COUNT + quotient_column
            numerator, denominator = pairs[entry_index]
            scaled = numerator * (global_denominator // denominator)
            numerator_row.append(scaled)
            pair = [str(numerator), str(denominator)]
            pair_row.append(pair)
            flat_pair_strings.append(pair)
            denominator_strings.append(str(denominator))
            if scaled:
                content = math.gcd(content, abs(scaled))
                observed_support.append(entry_index)
        numerator_matrix.append(numerator_row)
        pair_matrix_strings.append(pair_row)
    if observed_support != support:
        raise AssertionError("global numerator support changed")
    primitive_gcd = math.gcd(global_denominator, content)
    if primitive_gcd != 1:
        raise RouteFailure(
            f"global (N,D) is not primitive: gcd={primitive_gcd}",
            {
                "global_denominator": str(global_denominator),
                "numerator_content": str(content),
                "primitive_gcd": str(primitive_gcd),
            },
        )

    exact_replay = CanonicalListHasher()
    exact_failure = CanonicalListHasher()
    mismatch_count = 0
    coefficient_updates = 0
    for row_index, (b_row, c_row) in enumerate(zip(b_rows, c_rows, strict=True)):
        accumulator = {}
        for transition_row, coefficient in b_row:
            for quotient_column, numerator in enumerate(numerator_matrix[transition_row]):
                if numerator:
                    accumulator[quotient_column] = (
                        accumulator.get(quotient_column, 0) + coefficient * numerator
                    )
                    coefficient_updates += 1
        expected = {
            quotient_column: global_denominator * coefficient
            for quotient_column, coefficient in c_row
        }
        residual = []
        for quotient_column in range(QUOTIENT_COUNT):
            value = accumulator.get(quotient_column, 0) - expected.get(
                quotient_column, 0
            )
            residual.append(str(value))
            if value:
                mismatch_count += 1
                exact_failure.add([row_index, quotient_column, str(value)])
        exact_replay.add([row_index, residual])
        if row_index % 64 == 0:
            guard(started, initial_swaps, "exact integer B*N=D*C replay")
    if mismatch_count:
        raise RouteFailure(
            f"exact integer B*N=D*C replay has {mismatch_count} mismatches",
            {
                "mismatch_count": mismatch_count,
                "failure_stream_sha256": exact_failure.hexdigest(),
            },
        )

    numerator_strings = [[str(value) for value in row] for row in numerator_matrix]
    chart = {
        "canonical_rational_pairs_row_major": pair_matrix_strings,
        "global_denominator_D": str(global_denominator),
        "integer_numerator_matrix_N_row_major": numerator_strings,
        "nonzero_support_entry_indices": support,
        "nonzero_support_count": len(support),
        "numerator_content": str(content),
        "primitive_gcd_D_content_N": str(primitive_gcd),
        "hashes": {
            "denominator_stream_sha256": canonical_hash(denominator_strings),
            "canonical_rational_pair_stream_sha256": canonical_hash(flat_pair_strings),
            "integer_numerator_matrix_N_sha256": canonical_hash(numerator_strings),
            "nonzero_support_sha256": canonical_hash(support),
            "primitive_N_D_pair_sha256": canonical_hash(
                {"D": str(global_denominator), "N": numerator_strings}
            ),
            "exact_BN_equals_DC_replay_stream_sha256": exact_replay.hexdigest(),
            "exact_replay_failure_stream_sha256": exact_failure.hexdigest(),
        },
        "exact_integer_replay": {
            "identity": "B*N = D*C",
            "scalar_comparison_count": ENTRY_COUNT,
            "coefficient_update_count": coefficient_updates,
            "mismatch_count": mismatch_count,
            "replay_stream_sha256": exact_replay.hexdigest(),
            "failure_stream_record_count": exact_failure.count,
            "failure_stream_sha256": exact_failure.hexdigest(),
        },
    }
    return chart, numerator_matrix, global_denominator


def verify_seven_reductions(
    numerator_matrix, global_denominator, transitions, started, initial_swaps
):
    records = {}
    failure_stream = CanonicalListHasher()
    for prime in ALL_REDUCTION_PRIMES:
        denominator_residue = global_denominator % prime
        if denominator_residue == 0:
            failure_stream.add([prime, "nonunit_global_denominator"])
            raise RouteFailure(
                f"global denominator is nonunit modulo {prime}",
                {
                    "seven_reduction_failure_stream_sha256": failure_stream.hexdigest(),
                    "failed_characteristic": prime,
                },
            )
        inverse = pow(denominator_residue, -1, prime)
        reduced = []
        mismatches = 0
        mismatch_stream = CanonicalListHasher()
        for row_index in range(KOSZUL_COUNT):
            row = []
            for quotient_column in range(QUOTIENT_COUNT):
                value = numerator_matrix[row_index][quotient_column] % prime * inverse % prime
                row.append(value)
                expected = transitions[prime][row_index][quotient_column]
                if value != expected:
                    mismatches += 1
                    mismatch_stream.add(
                        [row_index, quotient_column, value, expected]
                    )
            reduced.append(row)
        reduced_hash = canonical_hash(reduced)
        stored_hash = canonical_hash(transitions[prime])
        if mismatches or reduced_hash != stored_hash:
            failure_stream.add(
                [prime, mismatches, reduced_hash, stored_hash, mismatch_stream.hexdigest()]
            )
            raise RouteFailure(
                f"primitive chart reduction mismatch modulo {prime}",
                {
                    "seven_reduction_failure_stream_sha256": failure_stream.hexdigest(),
                    "failed_characteristic": prime,
                    "mismatch_count": mismatches,
                },
            )
        records[str(prime)] = {
            "characteristic": prime,
            "role": "CRT_source" if prime in SOURCE_PRIMES else "confirmatory_selector",
            "global_denominator_is_unit": True,
            "global_denominator_residue": denominator_residue,
            "scalar_comparison_count": ENTRY_COUNT,
            "mismatch_count": 0,
            "reduced_N_over_D_row_major_sha256": reduced_hash,
            "stored_transition_row_major_sha256": stored_hash,
            "mismatch_stream_record_count": 0,
            "mismatch_stream_sha256": mismatch_stream.hexdigest(),
        }
        del reduced
        gc.collect()
        guard(started, initial_swaps, f"exact chart reduction modulo {prime}")
    return records, {
        "failure_stream_record_count": failure_stream.count,
        "failure_stream_sha256": failure_stream.hexdigest(),
    }


def run(campaign: Path, script_path: Path, started: float, initial_swaps: int):
    lineage_started = time.perf_counter()
    _old_receipt, _audit, _audit_telemetry = validate_frozen_lineage(campaign)
    prime_rule = validate_fresh_prime_rule()
    guard(started, initial_swaps, "frozen lineage and prime rule")
    lineage_seconds = time.perf_counter() - lineage_started

    chart_started = time.perf_counter()
    (
        legacy,
        old_artifact,
        restricted,
        pivots,
        complement,
        b_rows,
        c_rows,
        transitions,
        integer_chart,
    ) = reconstruct_integer_chart(campaign, started, initial_swaps)
    integer_chart_seconds = time.perf_counter() - chart_started

    phase1_started = time.perf_counter()
    fresh_records = solve_fresh_fibres(
        legacy,
        b_rows,
        c_rows,
        restricted,
        pivots,
        complement,
        transitions,
        started,
        initial_swaps,
    )
    phase1_seconds = time.perf_counter() - phase1_started

    phase2_started = time.perf_counter()
    pairs, denominators, support, census = reconstruct_all_entries(
        legacy, transitions, started, initial_swaps
    )
    phase2_seconds = time.perf_counter() - phase2_started

    phase3_started = time.perf_counter()
    rational_chart, numerator_matrix, global_denominator = assemble_primitive_chart(
        pairs, denominators, support, b_rows, c_rows, started, initial_swaps
    )
    reductions, reduction_failure = verify_seven_reductions(
        numerator_matrix, global_denominator, transitions, started, initial_swaps
    )
    phase3_seconds = time.perf_counter() - phase3_started
    guard(started, initial_swaps, "all three phases before staged serialization")

    fresh_transition_hashes = {
        str(prime): canonical_hash(transitions[prime]) for prime in FRESH_PRIMES
    }
    all_transition_hashes = {
        str(prime): canonical_hash(transitions[prime]) for prime in ALL_REDUCTION_PRIMES
    }
    usage = resource.getrusage(resource.RUSAGE_SELF)
    artifact = {
        "schema": "hc4.third-colon-residual-114-two-prime-exact-chart.v1",
        "status": "PASS_QUARANTINED_RESIDUAL_114_TWO_PRIME_EXACT_RATIONAL_CHART",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "promotion_state": "quarantined_pending_external_resource_gate",
        "assurance": "complete exact rational transition chart for the frozen integer Koszul quotient only",
        "claim_boundary": (
            "This quarantined artifact gives the exact rational transition matrix B^-1*C only for the frozen quotient of the 2167-coordinate space by the 2053 verified Koszul rows. It does not prove Macaulay-kernel quotient dimension 114, construct residual kernel syzygies, access or reconstruct a target multiplier, prove QQ target membership, compute a colon or saturation, close a secant chart, establish nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": PREREGISTRATION,
            "preregistration_sha256": PREREGISTRATION_HASH,
            "fresh_prime_rule": prime_rule,
            "no_adaptive_prime_minor_pivot_gauge_or_role_change": True,
            "target_multiplier_accessed": False,
            "final_promotion_requires_external_wrapper": True,
        },
        "frozen_lineage_file_sha256": FROZEN_FILES,
        "integer_chart_reconstruction": integer_chart,
        "fresh_modular_fibres": fresh_records,
        "complete_132_bit_reconstruction": census,
        "exact_rational_chart": rational_chart,
        "seven_fibre_reductions": reductions,
        "seven_fibre_reduction_failure_stream": reduction_failure,
        "hashes": {
            "source_script_sha256": sha256_bytes(script_path.read_bytes()),
            "fresh_transition_row_major_sha256": fresh_transition_hashes,
            "all_seven_transition_row_major_sha256": all_transition_hashes,
            "global_denominator_sha256": canonical_hash(
                rational_chart["global_denominator_D"]
            ),
            "canonical_rational_pair_stream_sha256": rational_chart["hashes"][
                "canonical_rational_pair_stream_sha256"
            ],
            "integer_numerator_matrix_N_sha256": rational_chart["hashes"][
                "integer_numerator_matrix_N_sha256"
            ],
            "primitive_N_D_pair_sha256": rational_chart["hashes"][
                "primitive_N_D_pair_sha256"
            ],
        },
        "checks": {
            "fresh_B_ranks_equal_2053": all(
                record["rank"] == KOSZUL_COUNT for record in fresh_records.values()
            ),
            "fresh_BT_equals_C_and_annihilation_replays_pass": all(
                record["BT_equals_C_replay"]["mismatch_count"] == 0
                and record["koszul_quotient_annihilation_replay"]["mismatch_count"]
                == 0
                for record in fresh_records.values()
            ),
            "all_234042_entries_unique_and_canonical": census["outcome"][
                "unique_zero"
            ]
            + census["outcome"]["unique_nonzero"]
            == ENTRY_COUNT
            and census["U_no_candidate_plus_ambiguous"] == 0,
            "global_N_D_primitive": rational_chart["primitive_gcd_D_content_N"]
            == "1",
            "exact_BN_equals_DC_replay_pass": rational_chart[
                "exact_integer_replay"
            ]["mismatch_count"]
            == 0,
            "all_seven_reductions_pass": all(
                record["mismatch_count"] == 0
                and record["global_denominator_is_unit"]
                for record in reductions.values()
            ),
            "target_multiplier_not_accessed": True,
            "literal_internal_initial_and_final_swaps_zero": initial_swaps == 0
            and int(usage.ru_nswap) == 0,
        },
        "internal_resources_before_staged_serialization": {
            "internal_wall_cap_seconds": INTERNAL_WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "initial_process_swaps": initial_swaps,
            "current_process_swaps": int(usage.ru_nswap),
            "maximum_rss_native": native_max_rss_bytes(),
            "elapsed_wall_seconds": time.perf_counter() - started,
        },
    }
    if not all(artifact["checks"].values()):
        raise RouteFailure("one or more final exact-chart checks failed")
    return artifact, {
        "lineage_and_prime_rule_seconds": lineage_seconds,
        "integer_chart_reconstruction_seconds": integer_chart_seconds,
        "phase_1_two_fresh_fibres_seconds": phase1_seconds,
        "phase_2_complete_reconstruction_seconds": phase2_seconds,
        "phase_3_exact_chart_and_reductions_seconds": phase3_seconds,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-output", required=True)
    parser.add_argument("--receipt-output", required=True)
    parser.add_argument("--failure-output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    artifact_output = Path(args.artifact_output).resolve()
    receipt_output = Path(args.receipt_output).resolve()
    failure_output = Path(args.failure_output).resolve()
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(
            TimeoutError("175-second internal quarantine alarm")
        ),
    )
    signal.setitimer(signal.ITIMER_REAL, INTERNAL_WALL_CAP_SECONDS)
    partial = None
    try:
        if initial_swaps != 0:
            raise MemoryError("initial process swap count is not literal zero")
        if artifact_output.exists() or receipt_output.exists() or failure_output.exists():
            raise FileExistsError("one or more quarantine outputs already exist")
        artifact, timings = run(campaign, script_path, started, initial_swaps)
        guard(started, initial_swaps, "pre-artifact quarantine gate")
        write_new_json(artifact_output, artifact, compact=True)
        artifact_hash = sha256_bytes(artifact_output.read_bytes())
        guard(started, initial_swaps, "post-artifact quarantine gate")
        usage = resource.getrusage(resource.RUSAGE_SELF)
        receipt = {
            "schema": "hc4.third-colon-residual-114-two-prime-exact-chart-receipt.v1",
            "status": "PASS_QUARANTINED_RESIDUAL_114_TWO_PRIME_EXACT_RATIONAL_CHART",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "promotion_state": "quarantined_pending_external_resource_gate",
            "claim_boundary": artifact["claim_boundary"],
            "preregistration": {
                "path": PREREGISTRATION,
                "sha256": PREREGISTRATION_HASH,
            },
            "source_script": {
                "path": str(script_path.relative_to(campaign)),
                "sha256": sha256_bytes(script_path.read_bytes()),
                "imports_or_executes_residual_114_independent_audit": False,
            },
            "declared_final_outputs": {
                "artifact_path": FINAL_ARTIFACT,
                "receipt_path": FINAL_RECEIPT,
            },
            "quarantined_artifact": {
                "sha256": artifact_hash,
                "byte_count": artifact_output.stat().st_size,
            },
            "frozen_lineage_file_sha256": FROZEN_FILES,
            "integer_chart_reconstruction": artifact["integer_chart_reconstruction"],
            "fresh_modular_fibre_telemetry": {
                prime: {
                    key: value
                    for key, value in record.items()
                    if key != "transition_matrix_row_major"
                }
                for prime, record in artifact["fresh_modular_fibres"].items()
            },
            "complete_132_bit_reconstruction": artifact[
                "complete_132_bit_reconstruction"
            ],
            "exact_rational_chart_summary": {
                key: value
                for key, value in artifact["exact_rational_chart"].items()
                if key
                not in {
                    "canonical_rational_pairs_row_major",
                    "integer_numerator_matrix_N_row_major",
                }
            },
            "seven_fibre_reductions": artifact["seven_fibre_reductions"],
            "seven_fibre_reduction_failure_stream": artifact[
                "seven_fibre_reduction_failure_stream"
            ],
            "artifact_hashes": artifact["hashes"],
            "checks": artifact["checks"],
            "internal_resources": {
                "internal_wall_cap_seconds": INTERNAL_WALL_CAP_SECONDS,
                "rss_cap_bytes": RSS_CAP_BYTES,
                "initial_process_swaps": initial_swaps,
                "final_process_swaps": int(usage.ru_nswap),
                "process_swap_delta": int(usage.ru_nswap) - initial_swaps,
                "maximum_rss_native": native_max_rss_bytes(),
                "user_cpu_seconds": usage.ru_utime,
                "system_cpu_seconds": usage.ru_stime,
            },
            "timings": {
                **timings,
                "total_before_receipt_serialization_seconds": time.perf_counter()
                - started,
            },
            "external_gate_pending": {
                "wall_seconds_maximum": 180.0,
                "maximum_rss_bytes": RSS_CAP_BYTES,
                "literal_process_swaps_required": 0,
                "algebra_process_count_required": 1,
                "wrapper_must_promote_artifact_last": True,
            },
        }
        write_new_json(receipt_output, receipt, compact=False)
        guard(started, initial_swaps, "post-receipt quarantine gate")
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "artifact_sha256": artifact_hash,
                    "U": receipt["complete_132_bit_reconstruction"][
                        "U_no_candidate_plus_ambiguous"
                    ],
                    "wall_seconds": time.perf_counter() - started,
                    "maximum_rss_native": native_max_rss_bytes(),
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        if isinstance(error, RouteFailure):
            partial = error.partial
        failure = {
            "schema": "hc4.third-colon-residual-114-two-prime-exact-chart-producer-failure.v1",
            "status": "FAIL_CLOSED_QUARANTINED_RESIDUAL_114_TWO_PRIME_EXACT_CHART",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
            "partial_fail_closed_telemetry": partial,
            "claim_boundary": (
                "No exact rational quotient chart, target multiplier, QQ membership, colon, saturation, secant-chart, nullcone, or HC4 conclusion is licensed by this failed quarantined producer."
            ),
            "preregistration_sha256": PREREGISTRATION_HASH,
            "source_script_sha256": sha256_bytes(script_path.read_bytes()),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "initial_process_swaps": initial_swaps,
            "current_process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
        }
        try:
            write_new_json(failure_output, failure, compact=False)
        except Exception as write_error:
            print(f"failure receipt write also failed: {write_error}", file=sys.stderr)
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
