#!/usr/bin/env sage-python
"""Apply the preregistered fixed-minor Koszul normalization to five vectors."""

from __future__ import annotations

import gc
import hashlib
import json
import platform
import resource
import signal
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIMES = (181, 173, 197, 2147483647, 2147483629)
PIVOT_HASH = "c7b305a434025cf4b9eea5aa720f38f419fbed7da121f5b2bba2e9a60c7676dd"
DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
MATCHING_HASH = "c0d2d067a4a79feeff85816301757f1264641fe14be60b974bcee1291524281a"
COMPONENT_HASH = "328c4d98a339d5fb11fbfa70a9e5207779166cd416bbf29392d685d165e5bcd2"
GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
INDEPENDENT_K_HASH = "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856"
WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 1_500_000_000

SOURCE_ARTIFACTS = {
    181: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
    173: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
    197: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
    2147483647: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
    2147483629: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
}
SOURCE_RECEIPTS = {
    prime: path.replace("artifacts/j2-", "receipts/hsop-j2-")
    for prime, path in SOURCE_ARTIFACTS.items()
}
FROZEN_HASHES = {
    "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md": "927b640211638c5610b05ab34e663f77ead79565d86ad7d28784c0f1e94f1819",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout.py": "39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py": "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json": "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json": "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json": "b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json": "f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json": "a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json": "2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90",
    "receipts/hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-m70-census.json": "78d0bd0200299c1dc8fb7df7880f479613e93cf0ccca99c4741a97883c501ad7",
    "receipts/hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-m70-independent-audit.json": "9c0f4d0dd1f5d603e66c7e5f6f933a98300e1c25805276a090c3aa6babb38964",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
}
IDENTITY_RECEIPT_HASHES = {
    181: "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c",
    173: "ddaed2462174438e89b31cfacb95ee2adf7971bf2290c58422031baab9314f44",
    197: "671df724adb16f279f9be31dfe0c87f90b0d48f02a9ea6161245f26d86c701fe",
    2147483647: "dba8ffbaf933500d5e532f9f4b19f356b20710383614b9d8b03200980e611f79",
    2147483629: "f572ebb40bbb4d590506210737347b0c6c964927ac866d9fba410621d4e354bb",
}


class SingularMinorError(RuntimeError):
    def __init__(self, prime: int, rank: int, telemetry: dict[str, object]):
        super().__init__(f"fixed 2053x2053 minor has rank {rank} at p{prime}")
        self.prime = prime
        self.rank = rank
        self.telemetry = telemetry
        self.completed_prime_telemetry = {}


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
        raise MemoryError(f"RSS cap reached during {stage}: {native_max_rss_bytes()} bytes")
    if int(usage.ru_nswap) != initial_swaps:
        raise MemoryError(f"process swap count changed during {stage}")


def reconstruct_k(campaign: Path, ind, started: float, initial_swaps: int):
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading, _open = homogeneous_saturation_system()
    cubic_terms = []
    cubic_expressions = []
    for equation in equations:
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        cubic_terms.append([
            (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
            for exponents, coefficient in polynomial.terms()
        ])
        cubic_expressions.append(sp.expand(equation))
    h_terms, h_expression = ind.artifact_terms(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4,
    )
    h2_terms, h2_expression = ind.artifact_terms(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 3,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = cubic_expressions + [h_expression, h2_expression]
    generator_degrees = [3] * 17 + [4, 4]
    generator_characters = []
    for terms in generator_terms:
        characters = {ind.character(exponents) for exponents, _ in terms}
        if len(characters) != 1:
            raise ValueError("generator character changed")
        generator_characters.append(next(iter(characters)))
    if ind.expression_hash(generator_expressions) != GENERATOR_HASH:
        raise ValueError("generator stream changed")

    pools = {}
    for degree in (4, 5):
        for monomial in ind.exponent_tuples(len(variables), degree):
            pools.setdefault((degree, ind.character(monomial)), []).append(monomial)
    descriptors = []
    for index, (degree, character) in enumerate(zip(generator_degrees, generator_characters, strict=True)):
        descriptors.extend(
            (index, monomial)
            for monomial in pools[(8 - degree, (3 - character) % 12)]
        )
    if len(descriptors) != 38048 or canonical_hash(descriptors) != DESCRIPTOR_HASH:
        raise ValueError("descriptor stream changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}

    columns = []
    stream_hasher = hashlib.sha256()
    pair_counts = Counter()
    for left in range(19):
        for right in range(left + 1, 19):
            residual_degree = 8 - generator_degrees[left] - generator_degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (3 - generator_characters[left] - generator_characters[right]) % 12
            for residual in ind.exponent_tuples(18, residual_degree):
                if ind.character(residual) != residual_character:
                    continue
                column = ind.primitive_column(left, right, residual, generator_terms, descriptor_index)
                columns.append(column)
                ind.framed_update(stream_hasher, [[coordinate, str(value)] for coordinate, value in column])
                pair_counts[(generator_degrees[left], generator_degrees[right])] += 1
        guard(started, initial_swaps, "Koszul reconstruction")
    if len(columns) != 2053 or sum(map(len, columns)) != 154939:
        raise ValueError("Koszul dimensions changed")
    if pair_counts != Counter({(3, 3): 1993, (3, 4): 60}):
        raise ValueError("Koszul pair census changed")
    if stream_hasher.hexdigest() != INDEPENDENT_K_HASH:
        raise ValueError("independent canonical Koszul stream changed")
    return columns, descriptors


def graph_and_pivots(columns, ind):
    adjacency = [[coordinate for coordinate, _ in column] for column in columns]
    matching_size, matching, rounds, scans = ind.hopcroft_karp(adjacency)
    if matching_size != 2053 or canonical_hash(matching) != MATCHING_HASH:
        raise ValueError("matching changed")
    degrees = Counter(coordinate for row in adjacency for coordinate in row)
    active = sorted(degrees)
    active_index = {coordinate: index for index, coordinate in enumerate(active)}
    union = ind.UnionFind(len(columns) + len(active))
    for row_index, row in enumerate(adjacency):
        for coordinate in row:
            union.union(row_index, len(columns) + active_index[coordinate])
    components = {}
    for row_index in range(len(columns)):
        components.setdefault(union.find(row_index), [0, 0])[0] += 1
    for coordinate in active:
        components.setdefault(union.find(len(columns) + active_index[coordinate]), [0, 0])[1] += 1
    profiles = sorted(components.values(), reverse=True)
    if canonical_hash(profiles) != COMPONENT_HASH:
        raise ValueError("component profile changed")

    basis = {}
    pivots = []
    reductions = 0
    maximum_support = 0
    for row_index, integer_row in enumerate(columns):
        work = {coordinate: value % 181 for coordinate, value in integer_row if value % 181}
        for pivot in pivots:
            factor = work.get(pivot, 0)
            if not factor:
                continue
            reductions += 1
            for coordinate, value in basis[pivot].items():
                updated = (work.get(coordinate, 0) - factor * value) % 181
                if updated:
                    work[coordinate] = updated
                else:
                    work.pop(coordinate, None)
        if not work:
            raise ValueError("rank at 181 dropped during pivot reconstruction")
        preferred = matching[row_index]
        pivot = preferred if preferred in work else min(work, key=lambda coordinate: (degrees[coordinate], coordinate))
        inverse = pow(work[pivot], -1, 181)
        basis[pivot] = {coordinate: value * inverse % 181 for coordinate, value in work.items()}
        pivots.append(pivot)
        maximum_support = max(maximum_support, len(work))
    if canonical_hash(pivots) != PIVOT_HASH:
        raise ValueError("fixed pivot sequence changed")
    return pivots, {
        "matching_size": matching_size,
        "matching_round_count": rounds,
        "matching_edge_scan_count": scans,
        "component_profiles": profiles,
        "active_coordinate_count": len(active),
        "p181_pivot_reduction_count": reductions,
        "p181_maximum_working_support": maximum_support,
    }


def load_sources(campaign: Path):
    payloads = {}
    receipt_bindings = {}
    reference = None
    common_keys = (
        "character_modulus", "character_weights", "generator_character_weights",
        "generator_count", "generator_degrees", "generator_stream_sha256",
        "monomial_stream_sha256", "multiplier_degrees", "normal_cubic_generator_count",
        "row_descriptor_sha256", "target_character_weight", "target_sha256", "variable_names",
        "free_unknown_indices_sha256",
    )
    for prime in PRIMES:
        artifact_path = campaign / SOURCE_ARTIFACTS[prime]
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if int(payload.get("characteristic", -1)) != prime or len(payload.get("coordinate_vector", [])) != 38048:
            raise ValueError(f"malformed source artifact at p{prime}")
        vector = list(map(int, payload["coordinate_vector"]))
        if any(value < 0 or value >= prime for value in vector):
            raise ValueError(f"noncanonical source residue at p{prime}")
        if canonical_hash(vector) != payload.get("coordinate_vector_sha256"):
            raise ValueError(f"source vector hash mismatch at p{prime}")
        support = {int(item["unknown_index"]): int(item["coefficient"]) for item in payload["solution_support"]}
        if len(support) != len(payload["solution_support"]) or support != {index: value for index, value in enumerate(vector) if value}:
            raise ValueError(f"source support mismatch at p{prime}")
        profile = {key: payload.get(key) for key in common_keys}
        if reference is None:
            reference = profile
        elif profile != reference:
            raise ValueError(f"problem stream or source gauge changed at p{prime}")
        if prime != 181 and payload.get("gauge_source", {}).get("sha256") != FROZEN_HASHES[SOURCE_ARTIFACTS[181]]:
            raise ValueError(f"transfer gauge source mismatch at p{prime}")
        receipt_path = campaign / SOURCE_RECEIPTS[prime]
        observed_receipt_hash = sha256_bytes(receipt_path.read_bytes())
        if observed_receipt_hash != IDENTITY_RECEIPT_HASHES[prime]:
            raise ValueError(f"identity receipt changed at p{prime}")
        identity_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        replay = identity_receipt.get("same_process_sparse_replay", {})
        if identity_receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY" or not replay.get("identity_zero"):
            raise ValueError(f"source identity is not certified at p{prime}")
        if identity_receipt.get("certificate", {}).get("sha256") != FROZEN_HASHES[SOURCE_ARTIFACTS[prime]]:
            raise ValueError(f"source receipt/artifact mismatch at p{prime}")
        payloads[prime] = payload
        receipt_bindings[str(SOURCE_RECEIPTS[prime])] = observed_receipt_hash
    return payloads, receipt_bindings


def minor_rows(columns, pivots):
    position = {coordinate: index for index, coordinate in enumerate(pivots)}
    rows = [[] for _ in pivots]  # rows of K[:,R]^T; variables are Koszul rows
    for variable, column in enumerate(columns):
        for coordinate, value in column:
            row = position.get(coordinate)
            if row is not None:
                rows[row].append((variable, value))
    return rows


def sparse_rank_only(integer_rows, prime, started, initial_swaps):
    """Compute the exact rank, allowing skipped pivot columns."""

    size = len(integer_rows)
    rows = [
        {column: value % prime for column, value in row if value % prime}
        for row in integer_rows
    ]
    rank = 0
    swaps = 0
    updates = 0
    skipped_columns = []
    maximum_nnz = sum(map(len, rows))
    maximum_row = max(map(len, rows))
    for column in range(size):
        candidates = [row for row in range(rank, size) if rows[row].get(column, 0)]
        if not candidates:
            skipped_columns.append(column)
            continue
        pivot_index = min(candidates, key=lambda row: (len(rows[row]), row))
        if pivot_index != rank:
            rows[rank], rows[pivot_index] = rows[pivot_index], rows[rank]
            swaps += 1
        pivot_value = rows[rank][column]
        inverse = pow(pivot_value, -1, prime)
        pivot_row = {
            key: value * inverse % prime
            for key, value in rows[rank].items()
            if key >= column
        }
        rows[rank] = pivot_row
        for row_index in range(rank + 1, size):
            factor = rows[row_index].pop(column, 0)
            if not factor:
                continue
            row = rows[row_index]
            for key, value in pivot_row.items():
                if key == column:
                    continue
                updated = (row.get(key, 0) - factor * value) % prime
                if updated:
                    row[key] = updated
                else:
                    row.pop(key, None)
                updates += 1
        rank += 1
        if column % 64 == 0:
            maximum_nnz = max(maximum_nnz, sum(map(len, rows)))
            maximum_row = max(maximum_row, max(map(len, rows)))
            guard(started, initial_swaps, f"exact singular-rank completion p{prime}")
    return rank, {
        "rank_algorithm": "independent sparse Gaussian elimination with skipped pivot columns",
        "rank_row_swap_count": swaps,
        "rank_coefficient_update_count": updates,
        "skipped_pivot_columns": skipped_columns,
        "rank_maximum_sampled_nonzero_count": maximum_nnz,
        "rank_maximum_sampled_row_length": maximum_row,
    }


def solve_sparse_square(integer_rows, rhs_values, prime, started, initial_swaps):
    size = len(integer_rows)
    rows = [
        {column: value % prime for column, value in row if value % prime}
        for row in integer_rows
    ]
    rhs = [value % prime for value in rhs_values]
    initial_nnz = sum(map(len, rows))
    maximum_nnz = initial_nnz
    maximum_row = max(map(len, rows))
    updates = 0
    swaps = 0
    determinant = 1
    for column in range(size):
        candidates = [row for row in range(column, size) if rows[row].get(column, 0)]
        if not candidates:
            exact_rank, rank_telemetry = sparse_rank_only(
                integer_rows, prime, started, initial_swaps
            )
            raise SingularMinorError(
                prime,
                exact_rank,
                {
                    "algorithm": "independent sparse Gaussian elimination of K[:,R]^T with row swaps; exact rank completed with column skipping",
                    "rank": exact_rank,
                    "singular": True,
                    "first_missing_pivot_column": column,
                    "row_swap_count": swaps,
                    "coefficient_update_count": updates,
                    "initial_nonzero_count": initial_nnz,
                    "current_nonzero_count": sum(map(len, rows)),
                    "maximum_sampled_nonzero_count": maximum_nnz,
                    "maximum_sampled_row_length": maximum_row,
                    **rank_telemetry,
                },
            )
        pivot_row_index = min(candidates, key=lambda row: (len(rows[row]), row))
        if pivot_row_index != column:
            rows[column], rows[pivot_row_index] = rows[pivot_row_index], rows[column]
            rhs[column], rhs[pivot_row_index] = rhs[pivot_row_index], rhs[column]
            swaps += 1
            determinant = -determinant
        pivot_value = rows[column][column]
        determinant = determinant * pivot_value % prime
        inverse = pow(pivot_value, -1, prime)
        rows[column] = {key: value * inverse % prime for key, value in rows[column].items() if key >= column}
        rhs[column] = rhs[column] * inverse % prime
        pivot_row = rows[column]
        for row_index in range(column + 1, size):
            factor = rows[row_index].pop(column, 0)
            if not factor:
                continue
            row = rows[row_index]
            for key, value in pivot_row.items():
                if key == column:
                    continue
                updated = (row.get(key, 0) - factor * value) % prime
                if updated:
                    row[key] = updated
                else:
                    row.pop(key, None)
                updates += 1
            rhs[row_index] = (rhs[row_index] - factor * rhs[column]) % prime
        if column % 64 == 0:
            current_nnz = sum(map(len, rows))
            maximum_nnz = max(maximum_nnz, current_nnz)
            maximum_row = max(maximum_row, max(map(len, rows)))
            guard(started, initial_swaps, f"minor elimination p{prime}")
    solution = [0] * size
    for row_index in range(size - 1, -1, -1):
        value = rhs[row_index]
        for column, coefficient in rows[row_index].items():
            if column > row_index:
                value = (value - coefficient * solution[column]) % prime
        solution[row_index] = value
    if any(
        sum(coefficient * solution[column] for column, coefficient in row) % prime != target % prime
        for row, target in zip(integer_rows, rhs_values, strict=True)
    ):
        raise AssertionError(f"minor solution replay failed at p{prime}")
    return solution, size, {
        "rank": size,
        "singular": False,
        "determinant_mod_p": determinant % prime,
        "row_swap_count": swaps,
        "coefficient_update_count": updates,
        "initial_nonzero_count": initial_nnz,
        "maximum_sampled_nonzero_count": maximum_nnz,
        "maximum_sampled_row_length": maximum_row,
        "algorithm": "independent sparse Gaussian elimination of K[:,R]^T with row swaps",
    }


def normalize_one(prime, source, columns, pivots, integer_minor_rows, started, initial_swaps):
    stage_started = time.perf_counter()
    source_vector = list(map(int, source["coordinate_vector"]))
    rhs = [(-source_vector[coordinate]) % prime for coordinate in pivots]
    coefficients, rank, solve = solve_sparse_square(
        integer_minor_rows, rhs, prime, started, initial_swaps
    )
    if rank != 2053 or not solve["determinant_mod_p"]:
        raise ValueError(f"fixed minor singular at p{prime}")
    combination = [0] * 38048
    combination_updates = 0
    for coefficient, column in zip(coefficients, columns, strict=True):
        if not coefficient:
            continue
        for coordinate, value in column:
            combination[coordinate] = (combination[coordinate] + coefficient * value) % prime
            combination_updates += 1
    normalized = [(source_value + delta) % prime for source_value, delta in zip(source_vector, combination, strict=True)]
    if any(normalized[coordinate] for coordinate in pivots):
        raise AssertionError(f"selected coordinate did not normalize to zero at p{prime}")
    observed_difference = [(new - old) % prime for new, old in zip(normalized, source_vector, strict=True)]
    if observed_difference != combination:
        raise AssertionError(f"Koszul-combination difference mismatch at p{prime}")
    guard(started, initial_swaps, f"vector normalization p{prime}")
    artifact = {
        "schema": "hc4.third-colon-koszul-fixed-minor-normalized-vector.v1",
        "status": "PASS_FIXED_MINOR_KOSZUL_NORMALIZATION",
        "characteristic": prime,
        "claim_boundary": (
            "This artifact proves only a modular gauge projection of one already-certified modular identity along the separately exact rational Koszul subspace. It is not a QQ multiplier reconstruction, QQ target-membership proof, colon or saturation computation, secant closure, nullcone containment, or HC4 proof."
        ),
        "source": {
            "path": SOURCE_ARTIFACTS[prime],
            "sha256": FROZEN_HASHES[SOURCE_ARTIFACTS[prime]],
            "coordinate_vector_sha256": source["coordinate_vector_sha256"],
            "identity_receipt_path": SOURCE_RECEIPTS[prime],
            "identity_receipt_sha256": IDENTITY_RECEIPT_HASHES[prime],
        },
        "fixed_minor": {
            "row_count": 2053,
            "coordinate_count": 2053,
            "pivot_coordinates": pivots,
            "pivot_coordinates_sha256": PIVOT_HASH,
            "rank": rank,
            **solve,
        },
        "koszul_coefficient_vector": coefficients,
        "koszul_coefficient_vector_sha256": canonical_hash(coefficients),
        "koszul_coefficient_support_count": sum(value != 0 for value in coefficients),
        "normalized_coordinate_vector": normalized,
        "normalized_coordinate_vector_sha256": canonical_hash(normalized),
        "normalized_support_count": sum(value != 0 for value in normalized),
        "difference_vector_sha256": canonical_hash(observed_difference),
        "checks": {
            "all_selected_coordinates_zero": True,
            "difference_equals_recorded_koszul_combination": True,
            "source_identity_receipt_passed": True,
            "integer_koszul_rows_have_separately_certified_zero_image": True,
            "transformed_identity_follows_by_linearity": True,
            "combination_update_count": combination_updates,
        },
        "wall_seconds": time.perf_counter() - stage_started,
    }
    return artifact


def run(campaign: Path, started: float, initial_swaps: int):
    for relative, expected in FROZEN_HASHES.items():
        if sha256_bytes((campaign / relative).read_bytes()) != expected:
            raise ValueError(f"frozen input changed: {relative}")
    sys.path.insert(0, str(campaign / "scripts"))
    import audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit as ind

    inputs_started = time.perf_counter()
    sources, receipt_bindings = load_sources(campaign)
    columns, descriptors = reconstruct_k(campaign, ind, started, initial_swaps)
    pivots, graph = graph_and_pivots(columns, ind)
    integer_minor_rows = minor_rows(columns, pivots)
    if len(integer_minor_rows) != 2053:
        raise ValueError("fixed minor dimensions changed")
    input_seconds = time.perf_counter() - inputs_started
    guard(started, initial_swaps, "fixed-minor construction")

    artifact_payloads = {}
    prime_telemetry = {}
    for prime in PRIMES:
        try:
            artifact = normalize_one(
                prime, sources[prime], columns, pivots, integer_minor_rows, started, initial_swaps
            )
        except SingularMinorError as error:
            error.completed_prime_telemetry = dict(prime_telemetry)
            raise
        artifact_payloads[prime] = artifact
        prime_telemetry[str(prime)] = {
            "rank": artifact["fixed_minor"]["rank"],
            "determinant_mod_p": artifact["fixed_minor"]["determinant_mod_p"],
            "row_swap_count": artifact["fixed_minor"]["row_swap_count"],
            "koszul_coefficient_support_count": artifact["koszul_coefficient_support_count"],
            "normalized_support_count": artifact["normalized_support_count"],
            "source_vector_sha256": artifact["source"]["coordinate_vector_sha256"],
            "coefficient_vector_sha256": artifact["koszul_coefficient_vector_sha256"],
            "normalized_vector_sha256": artifact["normalized_coordinate_vector_sha256"],
            "difference_vector_sha256": artifact["difference_vector_sha256"],
            "wall_seconds": artifact["wall_seconds"],
        }
        gc.collect()
        guard(started, initial_swaps, f"completed p{prime}")

    artifact_bindings = {}
    for prime in PRIMES:
        relative = f"artifacts/j2-secant-r10-third-colon-koszul-fixed-minor-normalized-p{prime}.json"
        path = campaign / relative
        path.write_text(json.dumps(artifact_payloads[prime], indent=2, sort_keys=True) + "\n", encoding="ascii")
        artifact_bindings[str(prime)] = {
            "path": relative,
            "sha256": sha256_bytes(path.read_bytes()),
            "byte_count": path.stat().st_size,
        }
    guard(started, initial_swaps, "artifact freeze")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    final_swaps = int(usage.ru_nswap)
    receipt = {
        "schema": "hc4.third-colon-koszul-fixed-minor-normalization.v1",
        "status": "PASS_FIVE_PRIME_FIXED_MINOR_KOSZUL_NORMALIZATION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "bounded exact modular fixed-minor normalization only",
        "claim_boundary": (
            "A PASS proves a coherent modular projection of five already-certified modular identities along a separately verified rational Koszul subspace, using one fixed coordinate minor. It does not reconstruct rational multipliers, test QQ target membership, compute a colon or saturation, run the M70 census, add primes or CRT information, close the secant chart, establish nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md",
            "preregistration_sha256": FROZEN_HASHES["research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md"],
            "characteristics_in_frozen_order": list(PRIMES),
            "additional_primes_used": [],
            "m70_census_performed": False,
        },
        "dimensions": {
            "koszul_row_count": len(columns),
            "multiplier_coordinate_count": len(descriptors),
            "koszul_nonzero_count": sum(map(len, columns)),
            "fixed_minor_shape": [2053, 2053],
            "fixed_minor_nonzero_count": sum(map(len, integer_minor_rows)),
        },
        "hashes": {
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "frozen_inputs": FROZEN_HASHES,
            "source_identity_receipts": receipt_bindings,
            "descriptor_stream_sha256": DESCRIPTOR_HASH,
            "matching_vector_sha256": MATCHING_HASH,
            "component_profiles_sha256": COMPONENT_HASH,
            "independent_koszul_stream_sha256": INDEPENDENT_K_HASH,
            "pivot_coordinates_sha256": canonical_hash(pivots),
            "fixed_integer_minor_sha256": canonical_hash(integer_minor_rows),
            "normalized_artifacts": artifact_bindings,
        },
        "structural_replay": graph,
        "prime_telemetry": prime_telemetry,
        "checks": {
            "all_five_minor_ranks_equal_2053": all(item["rank"] == 2053 for item in prime_telemetry.values()),
            "all_five_determinants_nonzero": all(item["determinant_mod_p"] for item in prime_telemetry.values()),
            "all_10265_selected_coordinates_zero": True,
            "all_five_differences_equal_recorded_koszul_combinations": True,
            "all_source_identities_separately_certified": True,
            "all_integer_koszul_rows_separately_certified_exact": True,
            "transformed_identities_follow_by_linearity": True,
            "zero_process_swap_gate": final_swaps == initial_swaps,
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
            "input_koszul_minor_build_seconds": input_seconds,
            "total_wall_seconds": time.perf_counter() - started,
        },
    }
    return receipt


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization.json"
    signal.signal(signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("180-second alarm")))
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        receipt = run(campaign, started, initial_swaps)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": receipt["status"], "output": str(output), "wall_seconds": receipt["timings"]["total_wall_seconds"]}, sort_keys=True))
        return 0
    except Exception as error:
        singular_witness = None
        if isinstance(error, SingularMinorError):
            singular_witness = {
                "characteristic": error.prime,
                "shape": [2053, 2053],
                "pivot_coordinates_sha256": PIVOT_HASH,
                **error.telemetry,
            }
        completed_prime_telemetry = (
            error.completed_prime_telemetry
            if isinstance(error, SingularMinorError)
            else {}
        )
        failed_prime_index = (
            PRIMES.index(error.prime)
            if isinstance(error, SingularMinorError)
            else -1
        )
        failure = {
            "schema": "hc4.third-colon-koszul-fixed-minor-normalization.v1",
            "status": (
                "FAIL_CLOSED_FIXED_MINOR_SINGULAR"
                if singular_witness is not None
                else "FAIL_CLOSED_FIXED_MINOR_NORMALIZATION"
            ),
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": (
                "This fail-closed receipt licenses no normalized vector, rational reconstruction, QQ membership, colon, saturation, secant, nullcone, or HC4 conclusion. A singular fixed minor stops only this preregistered normalization route; it does not show that the source modular identity or rational target membership is false."
            ),
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "preregistration": {
                "path": "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md",
                "sha256": FROZEN_HASHES["research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md"],
            },
            "frozen_input_hashes": FROZEN_HASHES,
            "singular_minor_witness": singular_witness,
            "completed_prime_telemetry_before_stop": completed_prime_telemetry,
            "untested_primes_due_to_fail_closed_stop": (
                list(PRIMES[failed_prime_index + 1 :])
                if failed_prime_index >= 0
                else []
            ),
            "structural_hashes": {
                "descriptor_stream_sha256": DESCRIPTOR_HASH,
                "matching_vector_sha256": MATCHING_HASH,
                "component_profiles_sha256": COMPONENT_HASH,
                "independent_koszul_stream_sha256": INDEPENDENT_K_HASH,
                "pivot_coordinates_sha256": PIVOT_HASH,
            },
            "normalized_artifacts_written": False,
            "m70_census_performed": False,
            "additional_primes_used": [],
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
