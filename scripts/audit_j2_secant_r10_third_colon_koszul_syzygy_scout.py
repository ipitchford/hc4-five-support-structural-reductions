#!/usr/bin/env sage-python
"""Exact bounded Koszul-syzygy scout for the third-colon Macaulay block.

The script constructs only the multiplier-module vectors.  It does not rebuild
the 85,651-row Macaulay matrix, compute a colon, or attempt a quotient lift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import sys
import time
from collections import defaultdict, deque
from fractions import Fraction
from pathlib import Path

import sympy as sp
from sage.all import GF, Matrix

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    load_third_quartic,
)
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
    exact_exponent_tuples,
)
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


P = 181
TARGET_DEGREE = 8
TARGET_CHARACTER = 3
EXPECTED_UNKNOWN_COUNT = 38048
EXPECTED_CUBIC_CUBIC = 1993
EXPECTED_CUBIC_QUARTIC = 60
EXPECTED_COLUMN_COUNT = 2053
EXPECTED_NONZERO_COUNT = 154939
WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 2_000_000_000

sys.setrecursionlimit(10_000)

FROZEN_HASHES = {
    "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py":
        "c0e1557c1a18d85af997e24c739d799d58c7d0b655d0662a0215f30e9b42ae74",
    "scripts/certify_j2_secant_r10_z12_macaulay.py":
        "fd49512f605cb257d62aea850fe795d61db04ca23df9504910f157cfe1436d26",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py":
        "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
    "scripts/certify_j2_secant_r10_colon_identity_liftstd.py":
        "e946e9e4b5ad1f7e7b62b688c03502f4331c463cd691e66b4f207d4b2b96f34c",
    "scripts/certify_j2_secant_r10_second_colon_identity_sparse_macaulay.py":
        "ea20fb8719bb583c424f0cc4e2730b46c7f38e130558fa7e6d2422865fb1af6b",
    "artifacts/j2-secant-r10-third-colon-identity-alt-gauge-p181.json":
        "26be0a64574c3cdbe6f7d0c323f9a5e4beb9b8df8e568f9daa054744160bc0a1",
    "receipts/hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json":
        "fe32cc53e81cf50e6c34881c5c61605938178a366986fae6ce872670aa9ddc6a",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json":
        "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json":
        "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json":
        "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "research/THIRD_COLON_KOSZUL_SYZYGY_SCOUT_PREREGISTRATION.md":
        "52d9a3df54fe09f3f65277765e8c0c0e85d42cbd34b2b6cf29e1ec3f11d83755",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def as_fraction(value) -> Fraction:
    rational = sp.Rational(value)
    return Fraction(int(rational.p), int(rational.q))


def polynomial_terms(expression, variables) -> list[tuple[tuple[int, ...], Fraction]]:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return [
        (tuple(map(int, exponents)), as_fraction(coefficient))
        for exponents, coefficient in polynomial.terms()
    ]


def add_exponents(left, right):
    return tuple(a + b for a, b in zip(left, right, strict=True))


def primitive_integer_column(entries: dict[int, Fraction]) -> tuple[tuple[int, int], ...]:
    entries = {index: value for index, value in entries.items() if value}
    require(bool(entries), "empty Koszul column")
    denominator_lcm = 1
    for value in entries.values():
        denominator_lcm = math.lcm(denominator_lcm, value.denominator)
    integers = {
        index: value.numerator * (denominator_lcm // value.denominator)
        for index, value in entries.items()
    }
    content = 0
    for value in integers.values():
        content = math.gcd(content, abs(value))
    require(content > 0, "zero primitive content")
    integers = {index: value // content for index, value in integers.items()}
    first_index = min(integers)
    if integers[first_index] < 0:
        integers = {index: -value for index, value in integers.items()}
    return tuple(sorted(integers.items()))


def exact_convolution_zero(
    column: tuple[tuple[int, int], ...],
    descriptors,
    terms_by_generator,
) -> tuple[bool, int]:
    remainder: dict[tuple[int, ...], Fraction] = {}
    update_count = 0
    for coordinate, integer_coefficient in column:
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in terms_by_generator[generator_index]:
            product = add_exponents(multiplier, exponents)
            value = remainder.get(product, Fraction(0)) + integer_coefficient * coefficient
            if value:
                remainder[product] = value
            elif product in remainder:
                del remainder[product]
            update_count += 1
    return not remainder, update_count


def maximum_matching(adjacency: list[tuple[int, ...]]) -> tuple[int, list[int], dict[int, int]]:
    """Deterministic Hopcroft--Karp matching from columns to coordinates."""

    pair_left = [-1] * len(adjacency)
    pair_right: dict[int, int] = {}
    distance = [0] * len(adjacency)
    infinity = len(adjacency) + 1

    def bfs() -> bool:
        queue = deque()
        found = False
        for left in range(len(adjacency)):
            if pair_left[left] == -1:
                distance[left] = 0
                queue.append(left)
            else:
                distance[left] = infinity
        while queue:
            left = queue.popleft()
            for right in adjacency[left]:
                mate = pair_right.get(right, -1)
                if mate == -1:
                    found = True
                elif distance[mate] == infinity:
                    distance[mate] = distance[left] + 1
                    queue.append(mate)
        return found

    def dfs(left: int) -> bool:
        for right in adjacency[left]:
            mate = pair_right.get(right, -1)
            if mate == -1 or (
                distance[mate] == distance[left] + 1 and dfs(mate)
            ):
                pair_left[left] = right
                pair_right[right] = left
                return True
        distance[left] = infinity
        return False

    size = 0
    while bfs():
        for left in range(len(adjacency)):
            if pair_left[left] == -1 and dfs(left):
                size += 1
    return size, pair_left, pair_right


def component_profile(adjacency: list[tuple[int, ...]]) -> dict[str, object]:
    """Connected-component census of the column/coordinate support graph."""

    coordinate_to_columns: dict[int, list[int]] = defaultdict(list)
    for column_index, coordinates in enumerate(adjacency):
        for coordinate in coordinates:
            coordinate_to_columns[coordinate].append(column_index)
    unseen = set(range(len(adjacency)))
    records = []
    while unseen:
        seed = min(unseen)
        columns = {seed}
        coordinates = set()
        queue = deque([seed])
        unseen.remove(seed)
        while queue:
            column = queue.popleft()
            for coordinate in adjacency[column]:
                if coordinate in coordinates:
                    continue
                coordinates.add(coordinate)
                for neighbour in coordinate_to_columns[coordinate]:
                    if neighbour in unseen:
                        unseen.remove(neighbour)
                        columns.add(neighbour)
                        queue.append(neighbour)
        records.append((len(columns), len(coordinates)))
    records.sort(reverse=True)
    return {
        "component_count": len(records),
        "component_size_pairs": [list(item) for item in records],
        "component_size_pairs_sha256": canonical_hash(records),
        "largest_column_count": records[0][0] if records else 0,
        "largest_coordinate_count": records[0][1] if records else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json"
        ),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    stage_timings: dict[str, float] = {}
    result: dict[str, object]
    try:
        for relative_path, expected_hash in FROZEN_HASHES.items():
            path = campaign / relative_path
            require(path.is_file(), f"missing frozen input: {relative_path}")
            require(
                sha256_path(path) == expected_hash,
                f"frozen input hash mismatch: {relative_path}",
            )

        build_started = time.perf_counter()
        equations, variables, _, _open_factor = homogeneous_saturation_system()
        first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
        second_quartic, second_metadata = load_second_quartic(campaign, variables)
        _third_quartic, third_metadata = load_third_quartic(campaign, variables)
        generators = list(equations) + [first_quartic, second_quartic]
        degrees = [3] * len(equations) + [4, 4]
        require(len(equations) == 17 and len(generators) == 19, "generator count changed")
        terms_by_generator = [polynomial_terms(item, variables) for item in generators]
        generator_characters = []
        support_losses = []
        for generator_index, (terms, degree) in enumerate(
            zip(terms_by_generator, degrees, strict=True)
        ):
            require({sum(exponents) for exponents, _ in terms} == {degree}, "degree changed")
            characters = {character_weight(exponents) for exponents, _ in terms}
            require(len(characters) == 1, "generator character changed")
            generator_characters.append(next(iter(characters)))
            for exponents, coefficient in terms:
                require(coefficient.denominator % P, "p181 denominator loss")
                if coefficient.numerator % P == 0:
                    support_losses.append([generator_index, list(exponents)])
        require(not support_losses, "p181 generator support loss")

        pools: dict[tuple[int, int], list[tuple[int, ...]]] = defaultdict(list)
        for degree in range(6):
            for monomial in exact_exponent_tuples(len(variables), degree):
                pools[(degree, character_weight(monomial))].append(monomial)
        descriptors = []
        for generator_index, (degree, generator_character) in enumerate(
            zip(degrees, generator_characters, strict=True)
        ):
            multiplier_degree = TARGET_DEGREE - degree
            multiplier_character = (TARGET_CHARACTER - generator_character) % CHARACTER_MODULUS
            for multiplier in pools[(multiplier_degree, multiplier_character)]:
                descriptors.append((generator_index, multiplier))
        require(len(descriptors) == EXPECTED_UNKNOWN_COUNT, "descriptor count changed")
        descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}
        require(len(descriptor_index) == len(descriptors), "duplicate descriptor")
        stage_timings["input_and_descriptor_build_seconds"] = time.perf_counter() - build_started

        enumerate_started = time.perf_counter()
        columns = []
        column_metadata = []
        type_counts = {"cubic_cubic": 0, "cubic_quartic": 0, "quartic_quartic": 0}
        for left in range(len(generators)):
            for right in range(left + 1, len(generators)):
                shared_degree = TARGET_DEGREE - degrees[left] - degrees[right]
                if shared_degree < 0:
                    continue
                shared_character = (
                    TARGET_CHARACTER
                    - generator_characters[left]
                    - generator_characters[right]
                ) % CHARACTER_MODULUS
                shared_monomials = pools.get((shared_degree, shared_character), [])
                pair_type = (
                    "cubic_cubic"
                    if degrees[left] == degrees[right] == 3
                    else "quartic_quartic"
                    if degrees[left] == degrees[right] == 4
                    else "cubic_quartic"
                )
                for shared in shared_monomials:
                    entries: dict[int, Fraction] = {}
                    for exponents, coefficient in terms_by_generator[right]:
                        coordinate = descriptor_index[(left, add_exponents(shared, exponents))]
                        entries[coordinate] = entries.get(coordinate, Fraction(0)) + coefficient
                    for exponents, coefficient in terms_by_generator[left]:
                        coordinate = descriptor_index[(right, add_exponents(shared, exponents))]
                        entries[coordinate] = entries.get(coordinate, Fraction(0)) - coefficient
                    column = primitive_integer_column(entries)
                    columns.append(column)
                    column_metadata.append([left, right, list(shared), pair_type])
                    type_counts[pair_type] += 1
        require(type_counts["cubic_cubic"] == EXPECTED_CUBIC_CUBIC, "cubic-cubic count")
        require(type_counts["cubic_quartic"] == EXPECTED_CUBIC_QUARTIC, "cubic-quartic count")
        require(type_counts["quartic_quartic"] == 0, "quartic-quartic count")
        require(len(columns) == EXPECTED_COLUMN_COUNT, "Koszul column count")
        nonzero_count = sum(map(len, columns))
        require(nonzero_count == EXPECTED_NONZERO_COUNT, "Koszul nonzero count")
        stage_timings["column_enumeration_seconds"] = time.perf_counter() - enumerate_started

        convolution_started = time.perf_counter()
        convolution_updates = 0
        for column in columns:
            zero, updates = exact_convolution_zero(column, descriptors, terms_by_generator)
            require(zero, "nonzero exact Koszul convolution")
            convolution_updates += updates
        stage_timings["exact_convolution_seconds"] = time.perf_counter() - convolution_started

        graph_started = time.perf_counter()
        adjacency = [tuple(coordinate for coordinate, _ in column) for column in columns]
        components = component_profile(adjacency)
        matching_size, matched_coordinates, _matched_columns = maximum_matching(adjacency)
        require(matching_size == EXPECTED_COLUMN_COUNT, "support matching is not full")
        stage_timings["graph_seconds"] = time.perf_counter() - graph_started

        rank_started = time.perf_counter()
        matrix_entries = {
            (column_index, coordinate): coefficient % P
            for column_index, column in enumerate(columns)
            for coordinate, coefficient in column
            if coefficient % P
        }
        require(len(matrix_entries) == nonzero_count, "p181 Koszul support loss")
        matrix = Matrix(
            GF(P),
            EXPECTED_COLUMN_COUNT,
            EXPECTED_UNKNOWN_COUNT,
            matrix_entries,
            sparse=True,
        )
        modular_rank = int(matrix.rank())
        stage_timings["modular_rank_seconds"] = time.perf_counter() - rank_started
        require(modular_rank == EXPECTED_COLUMN_COUNT, "p181 Koszul rank is not full")

        total_wall = time.perf_counter() - started
        usage = resource.getrusage(resource.RUSAGE_SELF)
        require(total_wall <= WALL_CAP_SECONDS, "wall cap exceeded")
        require(usage.ru_maxrss <= RSS_CAP_BYTES, "RSS cap exceeded")
        column_records = [
            {
                "metadata": metadata,
                "entries": [[coordinate, coefficient] for coordinate, coefficient in column],
            }
            for metadata, column in zip(column_metadata, columns, strict=True)
        ]
        result = {
            "schema": "hc4.third-colon-koszul-syzygy-scout.v1",
            "status": "PASS_EXACT_2053_KOSZUL_SYZYGIES_INDEPENDENT_OVER_QQ",
            "assurance": "exact integer syzygies plus finite-field independence witness",
            "characteristic": P,
            "dimensions": {
                "multiplier_coordinate_count": EXPECTED_UNKNOWN_COUNT,
                "koszul_column_count": len(columns),
                "koszul_nonzero_count": nonzero_count,
                "cubic_cubic_column_count": type_counts["cubic_cubic"],
                "cubic_quartic_column_count": type_counts["cubic_quartic"],
                "quartic_quartic_column_count": type_counts["quartic_quartic"],
                "modular_rank": modular_rank,
                "p181_kernel_quotient_dimension": 2167 - modular_rank,
                "QQ_kernel_quotient_dimension_upper_bound": 2167 - modular_rank,
            },
            "exact_checks": {
                "all_primitive_integer_columns": True,
                "all_exact_convolutions_zero": True,
                "convolution_update_count": convolution_updates,
                "p181_support_preserved": True,
                "matching_size": matching_size,
                "rank_mod_181": modular_rank,
                "rank_over_QQ_equals_column_count": True,
            },
            "support_graph": components,
            "hashes": {
                "descriptor_stream_sha256": canonical_hash(descriptors),
                "column_metadata_sha256": canonical_hash(column_metadata),
                "primitive_column_stream_sha256": canonical_hash(column_records),
                "matched_coordinate_vector_sha256": canonical_hash(matched_coordinates),
                "frozen_inputs": FROZEN_HASHES,
                "source_sha256": sha256_path(script_path),
            },
            "quartic_metadata": {
                "first": first_metadata,
                "second": second_metadata,
                "third": third_metadata,
            },
            "timings": {**stage_timings, "total_wall_seconds": total_wall},
            "resources": {
                "maximum_rss_native": usage.ru_maxrss,
                "user_cpu_seconds": usage.ru_utime,
                "system_cpu_seconds": usage.ru_stime,
                "wall_cap_seconds": WALL_CAP_SECONDS,
                "rss_cap_bytes": RSS_CAP_BYTES,
            },
            "claim_boundary": (
                "A PASS proves only that the displayed 2,053 primitive integer "
                "vectors are exact rational syzygies and are independent over QQ, "
                "witnessed by full rank modulo 181. It does not prove target "
                "membership over QQ, reconstruct rational multipliers, compute a "
                "colon or saturation, close the secant chart, prove nullcone "
                "containment, or establish HC4."
            ),
        }
    except Exception as exc:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result = {
            "schema": "hc4.third-colon-koszul-syzygy-scout.v1",
            "status": "FAIL_CLOSED_KOSZUL_SYZYGY_SCOUT",
            "assurance": "failed bounded scout; no mathematical conclusion",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "timings": {**stage_timings, "total_wall_seconds": time.perf_counter() - started},
            "resources": {
                "maximum_rss_native": usage.ru_maxrss,
                "user_cpu_seconds": usage.ru_utime,
                "system_cpu_seconds": usage.ru_stime,
                "wall_cap_seconds": WALL_CAP_SECONDS,
                "rss_cap_bytes": RSS_CAP_BYTES,
            },
            "hashes": {
                "frozen_inputs": FROZEN_HASHES,
                "source_sha256": sha256_path(script_path),
            },
            "claim_boundary": "The scout failed closed; no syzygy, rank, membership, colon, saturation, secant, nullcone, or HC4 claim follows.",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
