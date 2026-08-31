#!/usr/bin/env sage-python
"""Independent audit of the frozen degree-eight character-three Koszul scout.

This implementation deliberately does not import or execute the primary
Koszul-scout script.  It reconstructs the columns from the frozen cubics and
the termwise h/h2 artifacts, verifies A*K=0 over QQ coefficient by
coefficient, and computes rank modulo 181 with a local sparse eliminator.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import resource
import signal
import sys
import time
from collections import Counter, deque
from fractions import Fraction
from pathlib import Path

import sympy as sp


P = 181
TARGET_DEGREE = 8
TARGET_CHARACTER = 3
CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 2_000_000_000
EXPECTED_COLUMN_COUNT = 2053
EXPECTED_NNZ = 154939
EXPECTED_DESCRIPTOR_COUNT = 38048
EXPECTED_DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
EXPECTED_GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
EXPECTED_METADATA_HASH = "6dd2203260d3a2cab47df37476acd05ba718ed60f80137db362dfdbf173df752"
EXPECTED_PRIMITIVE_STREAM_HASH = "8a36159e01332cfc8fac9449e95001a069e440e8f7242965e756c09d15dfea76"
RETAINED_METADATA_FAILURE = (
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-"
    "independent-audit-failed-metadata-serialization.json"
)
RETAINED_METADATA_FAILURE_HASH = "73d11eab68fc8a6e85494f1deab36b93f773740faab856420f90b525564491e2"

FROZEN_HASHES = {
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-identity-alt-gauge-p181.json": "26be0a64574c3cdbe6f7d0c323f9a5e4beb9b8df8e568f9daa054744160bc0a1",
    "receipts/hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json": "fe32cc53e81cf50e6c34881c5c61605938178a366986fae6ce872670aa9ddc6a",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout.py": "39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def framed_update(hasher, value: object) -> None:
    payload = canonical_bytes(value)
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def canonical_stream_variants(columns) -> dict[str, str]:
    """Hash transparent canonical encodings without consulting producer code."""

    variants = {}
    for coefficient_mode in ("integer", "decimal-string"):
        records = [
            [
                [coordinate, value if coefficient_mode == "integer" else str(value)]
                for coordinate, value in column
            ]
            for column in columns
        ]
        variants[f"whole-json/{coefficient_mode}"] = canonical_hash(records)
        wrappers = {
            "entries": lambda index, record: record,
            "index-and-entries": lambda index, record: [index, record],
            "object": lambda index, record: {"column_index": index, "entries": record},
        }
        for wrapper_name, wrapper in wrappers.items():
            hashers = {
                "concat": hashlib.sha256(),
                "newline": hashlib.sha256(),
                "u4be": hashlib.sha256(),
                "u8be": hashlib.sha256(),
                "u8le": hashlib.sha256(),
                "ascii-length-colon": hashlib.sha256(),
                "digest-bytes": hashlib.sha256(),
                "digest-hex": hashlib.sha256(),
            }
            for index, record in enumerate(records):
                payload = canonical_bytes(wrapper(index, record))
                hashers["concat"].update(payload)
                hashers["newline"].update(payload + b"\n")
                hashers["u4be"].update(len(payload).to_bytes(4, "big") + payload)
                hashers["u8be"].update(len(payload).to_bytes(8, "big") + payload)
                hashers["u8le"].update(len(payload).to_bytes(8, "little") + payload)
                hashers["ascii-length-colon"].update(str(len(payload)).encode("ascii") + b":" + payload)
                digest = hashlib.sha256(payload).digest()
                hashers["digest-bytes"].update(digest)
                hashers["digest-hex"].update(digest.hex().encode("ascii"))
            for framing, hasher in hashers.items():
                variants[f"{framing}/{wrapper_name}/{coefficient_mode}"] = hasher.hexdigest()
    return variants


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def guard(started: float, stage: str) -> None:
    wall = time.perf_counter() - started
    rss = native_max_rss_bytes()
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if rss >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {rss} bytes")


def exponent_tuples(variable_count: int, degree: int):
    def visit(position: int, remaining: int, prefix: tuple[int, ...]):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from visit(position + 1, remaining - exponent, prefix + (exponent,))

    yield from visit(0, degree, ())


def character(exponents: tuple[int, ...]) -> int:
    return sum(a * b for a, b in zip(exponents, CHARACTER_WEIGHTS, strict=True)) % 12


def add_exponents(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def expression_hash(expressions) -> str:
    payload = "\n".join(str(sp.expand(item)).replace("**", "^") for item in expressions)
    return sha256_bytes(payload.encode("ascii"))


def artifact_terms(path: Path, key: str, variables, expected_count: int, expected_character: int):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError(f"variable order changed in {path.name}")
    records = payload.get(key)
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError(f"term count changed in {path.name}")
    terms = []
    seen = set()
    for record in records:
        exponents = tuple(map(int, record["exponents"]))
        coefficient = Fraction(int(record["numerator"]), int(record["denominator"]))
        if len(exponents) != len(variables) or exponents in seen or not coefficient:
            raise ValueError(f"malformed term in {path.name}")
        if sum(exponents) != 4 or character(exponents) != expected_character:
            raise ValueError(f"grading changed in {path.name}")
        seen.add(exponents)
        terms.append((exponents, coefficient))
    terms.sort(reverse=True)
    expression = sp.Integer(0)
    for exponents, coefficient in terms:
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += sp.Rational(coefficient.numerator, coefficient.denominator) * monomial
    return terms, sp.expand(expression)


def primitive_column(left_index, right_index, residual, generator_terms, descriptor_index):
    rational_entries = {}
    for exponents, coefficient in generator_terms[right_index]:
        coordinate = descriptor_index[(left_index, add_exponents(residual, exponents))]
        rational_entries[coordinate] = rational_entries.get(coordinate, Fraction(0)) + coefficient
    for exponents, coefficient in generator_terms[left_index]:
        coordinate = descriptor_index[(right_index, add_exponents(residual, exponents))]
        rational_entries[coordinate] = rational_entries.get(coordinate, Fraction(0)) - coefficient
    rational_entries = {key: value for key, value in rational_entries.items() if value}
    denominator = math.lcm(*(value.denominator for value in rational_entries.values()))
    integer_entries = {key: value.numerator * (denominator // value.denominator) for key, value in rational_entries.items()}
    content = math.gcd(*(abs(value) for value in integer_entries.values()))
    integer_entries = {key: value // content for key, value in integer_entries.items()}
    first_coordinate = min(integer_entries)
    if integer_entries[first_coordinate] < 0:
        integer_entries = {key: -value for key, value in integer_entries.items()}
    if math.gcd(*(abs(value) for value in integer_entries.values())) != 1:
        raise AssertionError("column is not primitive")
    return tuple(sorted(integer_entries.items()))


def verify_exact_convolution(column, descriptors, generator_terms):
    accumulator = {}
    updates = 0
    maximum_support = 0
    for coordinate, integer_coefficient in column:
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            product = add_exponents(multiplier, exponents)
            delta = Fraction(integer_coefficient * coefficient.numerator, coefficient.denominator)
            value = accumulator.get(product, Fraction(0)) + delta
            if value:
                accumulator[product] = value
            else:
                accumulator.pop(product, None)
            updates += 1
        maximum_support = max(maximum_support, len(accumulator))
    if accumulator:
        raise AssertionError(f"A*K column has {len(accumulator)} nonzero coefficients")
    return updates, maximum_support


def hopcroft_karp(adjacency):
    left_count = len(adjacency)
    pair_left = [-1] * left_count
    pair_right = {}
    distance = [0] * left_count
    infinity = left_count + 1
    rounds = 0
    edge_scans = 0

    def bfs():
        nonlocal rounds, edge_scans
        queue = deque()
        found = False
        for left in range(left_count):
            if pair_left[left] < 0:
                distance[left] = 0
                queue.append(left)
            else:
                distance[left] = infinity
        while queue:
            left = queue.popleft()
            for right in adjacency[left]:
                edge_scans += 1
                mate = pair_right.get(right, -1)
                if mate < 0:
                    found = True
                elif distance[mate] == infinity:
                    distance[mate] = distance[left] + 1
                    queue.append(mate)
        rounds += 1
        return found

    def dfs(left):
        nonlocal edge_scans
        for right in adjacency[left]:
            edge_scans += 1
            mate = pair_right.get(right, -1)
            if mate < 0 or (distance[mate] == distance[left] + 1 and dfs(mate)):
                pair_left[left] = right
                pair_right[right] = left
                return True
        distance[left] = infinity
        return False

    size = 0
    while bfs():
        for left in range(left_count):
            if pair_left[left] < 0 and dfs(left):
                size += 1
    return size, pair_left, rounds, edge_scans


def sparse_rank_mod_181(columns, preferred_rows, coordinate_degrees):
    """Incremental sparse column echelon, independent of Sage Matrix.rank."""

    basis = {}
    pivot_sequence = []
    reductions = 0
    coefficient_updates = 0
    maximum_working_support = 0
    basis_nnz = 0
    for column_index, integer_column in enumerate(columns):
        work = {row: value % P for row, value in integer_column if value % P}
        maximum_working_support = max(maximum_working_support, len(work))
        for pivot in pivot_sequence:
            factor = work.get(pivot, 0)
            if not factor:
                continue
            reductions += 1
            for row, value in basis[pivot].items():
                updated = (work.get(row, 0) - factor * value) % P
                if updated:
                    work[row] = updated
                else:
                    work.pop(row, None)
                coefficient_updates += 1
            maximum_working_support = max(maximum_working_support, len(work))
        if not work:
            continue
        preferred = preferred_rows[column_index]
        pivot = preferred if preferred in work else min(work, key=lambda row: (coordinate_degrees[row], row))
        inverse = pow(work[pivot], -1, P)
        normalized = {row: value * inverse % P for row, value in work.items()}
        basis[pivot] = normalized
        pivot_sequence.append(pivot)
        basis_nnz += len(normalized)
    return len(pivot_sequence), {
        "algorithm": "independent_incremental_sparse_column_echelon_mod_181",
        "pivot_count": len(pivot_sequence),
        "pivot_sequence_sha256": canonical_hash(pivot_sequence),
        "reduction_count": reductions,
        "coefficient_update_count": coefficient_updates,
        "maximum_working_support": maximum_working_support,
        "basis_nonzero_count": basis_nnz,
    }


class UnionFind:
    def __init__(self, size):
        self.parent = list(range(size))
        self.size = [1] * size

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left, right):
        left = self.find(left)
        right = self.find(right)
        if left == right:
            return
        if self.size[left] < self.size[right]:
            left, right = right, left
        self.parent[right] = left
        self.size[left] += self.size[right]


def audit(campaign: Path, started: float):
    for relative, expected in FROZEN_HASHES.items():
        observed = sha256_bytes((campaign / relative).read_bytes())
        if observed != expected:
            raise ValueError(f"frozen source hash changed: {relative}")
    if sha256_bytes((campaign / RETAINED_METADATA_FAILURE).read_bytes()) != RETAINED_METADATA_FAILURE_HASH:
        raise ValueError("retained metadata-serialization failure changed")
    reference = json.loads((campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json").read_text())
    if reference.get("hashes", {}).get("primitive_column_stream_sha256") != EXPECTED_PRIMITIVE_STREAM_HASH:
        raise ValueError("reference receipt primitive stream hash changed")

    sys.path.insert(0, str(campaign / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading_form, _open_factor = homogeneous_saturation_system()
    if len(equations) != 17 or len(variables) != 18:
        raise ValueError("frozen cubic system dimensions changed")
    cubic_terms = []
    cubic_expressions = []
    for equation in equations:
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        terms = [(tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q))) for exponents, coefficient in polynomial.terms()]
        if {sum(exponents) for exponents, _ in terms} != {3}:
            raise ValueError("a frozen cubic left degree three")
        cubic_terms.append(terms)
        cubic_expressions.append(sp.expand(equation))

    h_terms, h_expression = artifact_terms(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4,
    )
    h2_terms, h2_expression = artifact_terms(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 3,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = cubic_expressions + [h_expression, h2_expression]
    generator_degrees = [3] * 17 + [4, 4]
    generator_characters = []
    for terms, degree in zip(generator_terms, generator_degrees, strict=True):
        observed_degrees = {sum(exponents) for exponents, _ in terms}
        observed_characters = {character(exponents) for exponents, _ in terms}
        if observed_degrees != {degree} or len(observed_characters) != 1:
            raise ValueError("generator grading changed")
        generator_characters.append(next(iter(observed_characters)))
    generator_hash = expression_hash(generator_expressions)
    if generator_hash != EXPECTED_GENERATOR_HASH:
        raise ValueError("generator expression stream changed")

    pools = {}
    for degree in (4, 5):
        for monomial in exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (degree, weight) in enumerate(zip(generator_degrees, generator_characters, strict=True)):
        multiplier_degree = TARGET_DEGREE - degree
        multiplier_character = (TARGET_CHARACTER - weight) % CHARACTER_MODULUS
        descriptors.extend((generator_index, monomial) for monomial in pools[(multiplier_degree, multiplier_character)])
    if len(descriptors) != EXPECTED_DESCRIPTOR_COUNT:
        raise AssertionError(f"descriptor count {len(descriptors)} != {EXPECTED_DESCRIPTOR_COUNT}")
    descriptor_hash = canonical_hash(descriptors)
    if descriptor_hash != EXPECTED_DESCRIPTOR_HASH:
        raise AssertionError("descriptor stream hash changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}
    guard(started, "input reconstruction")
    input_seconds = time.perf_counter() - started

    columns = []
    metadata_hasher = hashlib.sha256()
    primitive_hasher = hashlib.sha256()
    pair_counts = Counter()
    convolution_updates = 0
    maximum_convolution_support = 0
    p181_support_preserved = True
    enumeration_started = time.perf_counter()
    for left in range(len(generator_terms)):
        for right in range(left + 1, len(generator_terms)):
            residual_degree = TARGET_DEGREE - generator_degrees[left] - generator_degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (TARGET_CHARACTER - generator_characters[left] - generator_characters[right]) % 12
            for residual in exponent_tuples(len(variables), residual_degree):
                if character(residual) != residual_character:
                    continue
                column_index = len(columns)
                column = primitive_column(left, right, residual, generator_terms, descriptor_index)
                updates, maximum_support = verify_exact_convolution(column, descriptors, generator_terms)
                convolution_updates += updates
                maximum_convolution_support = max(maximum_convolution_support, maximum_support)
                p181_support_preserved &= all(value % P != 0 for _, value in column)
                columns.append(column)
                label = ("cubic" if generator_degrees[left] == 3 else "quartic") + "-" + ("cubic" if generator_degrees[right] == 3 else "quartic")
                pair_counts[label] += 1
                framed_update(metadata_hasher, [column_index, left, right, list(residual)])
                framed_update(primitive_hasher, [[coordinate, str(value)] for coordinate, value in column])
                if column_index % 64 == 0:
                    guard(started, "column enumeration and exact convolution")
    enumeration_seconds = time.perf_counter() - enumeration_started
    nnz = sum(map(len, columns))
    metadata_hash = metadata_hasher.hexdigest()
    primitive_hash = primitive_hasher.hexdigest()
    if dict(pair_counts) != {"cubic-cubic": 1993, "cubic-quartic": 60}:
        raise AssertionError(f"unexpected pair counts: {dict(pair_counts)}")
    if len(columns) != EXPECTED_COLUMN_COUNT or nnz != EXPECTED_NNZ:
        raise AssertionError(f"column profile changed: {len(columns)} columns, {nnz} nnz")
    if not p181_support_preserved:
        raise AssertionError("a primitive entry vanished modulo 181")

    graph_started = time.perf_counter()
    adjacency = [[coordinate for coordinate, _ in column] for column in columns]
    matching_size, matching, matching_rounds, matching_edge_scans = hopcroft_karp(adjacency)
    if matching_size != EXPECTED_COLUMN_COUNT:
        raise AssertionError(f"matching size {matching_size} != {EXPECTED_COLUMN_COUNT}")
    coordinate_degrees = Counter(coordinate for column in adjacency for coordinate in column)
    active_coordinates = sorted(coordinate_degrees)
    active_index = {coordinate: index for index, coordinate in enumerate(active_coordinates)}
    union_find = UnionFind(len(columns) + len(active_coordinates))
    for column_index, coordinates in enumerate(adjacency):
        for coordinate in coordinates:
            union_find.union(column_index, len(columns) + active_index[coordinate])
    components = {}
    for column_index in range(len(columns)):
        root = union_find.find(column_index)
        components.setdefault(root, [0, 0])[0] += 1
    for coordinate in active_coordinates:
        root = union_find.find(len(columns) + active_index[coordinate])
        components.setdefault(root, [0, 0])[1] += 1
    component_profiles = sorted((value for value in components.values()), reverse=True)
    graph_seconds = time.perf_counter() - graph_started
    guard(started, "matching and components")

    rank_started = time.perf_counter()
    rank, rank_telemetry = sparse_rank_mod_181(columns, matching, coordinate_degrees)
    rank_seconds = time.perf_counter() - rank_started
    if rank != EXPECTED_COLUMN_COUNT:
        raise AssertionError(f"rank mod 181 is {rank}, expected {EXPECTED_COLUMN_COUNT}")
    guard(started, "rank modulo 181")

    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    return {
        "schema": "hc4.third-colon-koszul-syzygy-scout-independent-audit.v1",
        "status": "PASS_INDEPENDENT_CONTENT_INVARIANT_2053_KOSZUL_SYZYGIES_AND_RANK",
        "assurance": "independent reconstruction, exact coefficientwise syzygy audit, and finite-field rank witness",
        "claim_boundary": (
            "A PASS proves only that an implementation independent of the frozen scout reconstructed the canonically sign-normalized 2,053 pairwise primitive integer Koszul vectors from the same frozen inputs, verified A*K=0 coefficientwise over QQ, and found rank 2,053 modulo 181, hence rank 2,053 over QQ. The producer's 8a36159e byte-stream hash is bound through its frozen receipt but is not reserialized because that byte encoding is undocumented and producer-source inspection was forbidden. This audit performs no QQ target-membership test, multiplier reconstruction, colon or saturation computation, quotient construction or replay, HNF/SNF, extra-prime or CRT computation, secant-chart closure, nullcone proof, or HC4 proof."
        ),
        "independence_boundary": {
            "primary_scout_imported_or_executed": False,
            "primary_scout_source_used_as_code": False,
            "rank_implementation": rank_telemetry["algorithm"],
            "sage_matrix_rank_used": False,
        },
        "dimensions": {
            "generator_count": len(generator_terms),
            "cubic_generator_count": 17,
            "quartic_generator_count": 2,
            "multiplier_coordinate_count": len(descriptors),
            "active_multiplier_coordinate_count": len(active_coordinates),
            "cubic_cubic_column_count": pair_counts["cubic-cubic"],
            "cubic_quartic_column_count": pair_counts["cubic-quartic"],
            "quartic_quartic_column_count": pair_counts["quartic-quartic"],
            "koszul_column_count": len(columns),
            "koszul_nonzero_count": nnz,
        },
        "exact_checks": {
            "producer_primitive_byte_stream_hash_reproduced": primitive_hash == EXPECTED_PRIMITIVE_STREAM_HASH,
            "producer_primitive_byte_stream_hash_bound_from_frozen_receipt": True,
            "content_invariant_primitive_reconstruction_passed": True,
            "all_exact_convolutions_zero": True,
            "all_primitive_integer_columns": True,
            "p181_support_preserved": p181_support_preserved,
            "coefficientwise_convolution_update_count": convolution_updates,
            "maximum_temporary_convolution_support": maximum_convolution_support,
            "matching_size": matching_size,
            "rank_mod_181": rank,
            "rank_over_QQ_equals_column_count": rank == len(columns),
            "rank_implication": "A nonzero 2053-by-2053 minor modulo 181 is a nonzero integer minor, so rank over QQ is at least 2053; 2053 columns give the reverse bound.",
        },
        "hashes": {
            "frozen_inputs": FROZEN_HASHES,
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "generator_stream_sha256": generator_hash,
            "descriptor_stream_sha256": descriptor_hash,
            "column_metadata_sha256": metadata_hash,
            "reference_column_metadata_sha256": EXPECTED_METADATA_HASH,
            "column_metadata_serialization_is_independent": True,
            "primitive_column_stream_sha256": primitive_hash,
            "reference_primitive_column_stream_sha256": EXPECTED_PRIMITIVE_STREAM_HASH,
            "retained_metadata_serialization_failure": {
                "path": RETAINED_METADATA_FAILURE,
                "sha256": RETAINED_METADATA_FAILURE_HASH,
            },
            "matching_vector_sha256": canonical_hash(matching),
            "component_profiles_sha256": canonical_hash(component_profiles),
        },
        "support_graph": {
            "matching_size": matching_size,
            "matching_round_count": matching_rounds,
            "matching_edge_scan_count": matching_edge_scans,
            "component_count": len(component_profiles),
            "component_size_pairs": component_profiles,
            "active_coordinate_degree_minimum": min(coordinate_degrees.values()),
            "active_coordinate_degree_maximum": max(coordinate_degrees.values()),
            "active_coordinate_degree_histogram": {str(key): value for key, value in sorted(Counter(coordinate_degrees.values()).items())},
        },
        "modular_rank": rank_telemetry,
        "timings": {
            "input_and_descriptor_build_seconds": input_seconds,
            "column_enumeration_and_exact_convolution_seconds": enumeration_seconds,
            "graph_seconds": graph_seconds,
            "modular_rank_seconds": rank_seconds,
            "total_wall_seconds": wall,
        },
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "maximum_rss_native": native_max_rss_bytes(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json"
    signal.signal(signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("180-second alarm")))
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        receipt = audit(campaign, started)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": receipt["status"], "output": str(output), "wall_seconds": receipt["timings"]["total_wall_seconds"]}, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-syzygy-scout-independent-audit.v1",
            "status": "FAIL_CLOSED_INDEPENDENT_AUDIT",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No positive mathematical conclusion is licensed by this failed or incomplete audit.",
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
        }
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
