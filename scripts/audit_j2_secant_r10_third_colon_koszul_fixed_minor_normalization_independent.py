#!/usr/bin/env sage-python
"""Independent audit of the fixed-minor Koszul normalization.

The normalizer producer is deliberately neither imported nor executed.  This
script reconstructs the degree-eight, character-three Macaulay descriptors and
the 2,053 primitive integer Koszul syzygies from the frozen rational
generators.  It then reconstructs the p=181 pivot-coordinate set, checks the
same square minor at all five preregistered primes, and independently validates
the producer's five transformed vectors and Koszul coefficient vectors.

The producer-output adapter is intentionally small and fail closed.  It accepts
only the frozen schema documented by ``extract_producer_records`` below; a
schema change must be reviewed rather than guessed from vector dimensions.
"""

from __future__ import annotations

import argparse
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


PRIMES = (181, 173, 197, 2147483647, 2147483629)
TARGET_DEGREE = 8
TARGET_CHARACTER = 3
CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 1_500_000_000
EXPECTED_COORDINATE_COUNT = 38048
EXPECTED_COLUMN_COUNT = 2053
EXPECTED_NNZ = 154939
EXPECTED_ACTIVE_COORDINATES = 28853
EXPECTED_DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
EXPECTED_GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
EXPECTED_TARGET_HASH = "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
EXPECTED_MATCHING_HASH = "c0d2d067a4a79feeff85816301757f1264641fe14be60b974bcee1291524281a"
EXPECTED_COMPONENT_HASH = "328c4d98a339d5fb11fbfa70a9e5207779166cd416bbf29392d685d165e5bcd2"
EXPECTED_PIVOT_HASH = "c7b305a434025cf4b9eea5aa720f38f419fbed7da121f5b2bba2e9a60c7676dd"
EXPECTED_FINAL_PRODUCER_SCRIPT_HASH = "fceb3a0a12ae5473bf48f72d2c37e864c6569897052c6d0f60235b0a4fe6a08f"
EXPECTED_FINAL_PRODUCER_RECEIPT_HASH = "0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1"

FROZEN_INPUT_HASHES = {
    "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md": "927b640211638c5610b05ab34e663f77ead79565d86ad7d28784c0f1e94f1819",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json": "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
}

SOURCE_FILES = {
    181: (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
        "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b",
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
        "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c",
    ),
    173: (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c",
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
        "ddaed2462174438e89b31cfacb95ee2adf7971bf2290c58422031baab9314f44",
    ),
    197: (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272",
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
        "671df724adb16f279f9be31dfe0c87f90b0d48f02a9ea6161245f26d86c701fe",
    ),
    2147483647: (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad",
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
        "dba8ffbaf933500d5e532f9f4b19f356b20710383614b9d8b03200980e611f79",
    ),
    2147483629: (
        "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90",
        "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
        "f572ebb40bbb4d590506210737347b0c6c964927ac866d9fba410621d4e354bb",
    ),
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")


def canonical_hash(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def expression_hash(expressions) -> str:
    payload = "\n".join(str(sp.expand(item)).replace("**", "^") for item in expressions)
    return sha256_bytes(payload.encode("ascii"))


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def process_swaps() -> int:
    return int(getattr(resource.getrusage(resource.RUSAGE_SELF), "ru_nswap", 0))


def guard(started: float, stage: str) -> None:
    wall = time.perf_counter() - started
    rss = native_max_rss_bytes()
    swaps = process_swaps()
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if rss >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {rss} bytes")
    if swaps:
        raise MemoryError(f"process swaps observed during {stage}: {swaps}")


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


def rational_terms(expression, variables):
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return [
        (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
        for exponents, coefficient in polynomial.terms()
    ]


def load_term_artifact(
    path: Path,
    key: str,
    variables,
    expected_count: int,
    expected_degree: int,
    expected_character: int,
):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError(f"variable order changed in {path.name}")
    records = payload.get(key)
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError(f"term count changed in {path.name}")
    terms = []
    seen = set()
    expression = sp.Integer(0)
    for record in records:
        exponents = tuple(map(int, record["exponents"]))
        coefficient = Fraction(int(record["numerator"]), int(record["denominator"]))
        if (
            len(exponents) != len(variables)
            or exponents in seen
            or not coefficient
            or sum(exponents) != expected_degree
            or character(exponents) != expected_character
        ):
            raise ValueError(f"malformed or off-grade term in {path.name}")
        seen.add(exponents)
        terms.append((exponents, coefficient))
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += sp.Rational(coefficient.numerator, coefficient.denominator) * monomial
    terms.sort(reverse=True)
    return terms, sp.expand(expression)


def primitive_koszul_row(left, right, residual, generator_terms, descriptor_index):
    entries = {}
    for exponents, coefficient in generator_terms[right]:
        coordinate = descriptor_index[(left, add_exponents(residual, exponents))]
        entries[coordinate] = entries.get(coordinate, Fraction(0)) + coefficient
    for exponents, coefficient in generator_terms[left]:
        coordinate = descriptor_index[(right, add_exponents(residual, exponents))]
        entries[coordinate] = entries.get(coordinate, Fraction(0)) - coefficient
    entries = {coordinate: value for coordinate, value in entries.items() if value}
    denominator = math.lcm(*(value.denominator for value in entries.values()))
    integral = {
        coordinate: value.numerator * (denominator // value.denominator)
        for coordinate, value in entries.items()
    }
    content = math.gcd(*(abs(value) for value in integral.values()))
    integral = {coordinate: value // content for coordinate, value in integral.items()}
    if integral[min(integral)] < 0:
        integral = {coordinate: -value for coordinate, value in integral.items()}
    if math.gcd(*(abs(value) for value in integral.values())) != 1:
        raise AssertionError("Koszul row is not primitive")
    return tuple(sorted(integral.items()))


def exact_macaulay_image(vector, descriptors, generator_terms):
    accumulator = {}
    for coordinate, scalar in enumerate(vector):
        if not scalar:
            continue
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            product = add_exponents(multiplier, exponents)
            updated = accumulator.get(product, Fraction(0)) + scalar * coefficient
            if updated:
                accumulator[product] = updated
            else:
                accumulator.pop(product, None)
    return accumulator


def exact_koszul_image(column, descriptors, generator_terms):
    """Apply the Macaulay map to one sparse integer Koszul row over QQ."""

    accumulator = {}
    for coordinate, scalar in column:
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            product = add_exponents(multiplier, exponents)
            updated = accumulator.get(product, Fraction(0)) + scalar * coefficient
            if updated:
                accumulator[product] = updated
            else:
                accumulator.pop(product, None)
    return accumulator


def modular_macaulay_image(vector, descriptors, generator_terms, prime):
    accumulator = {}
    for coordinate, scalar in enumerate(vector):
        scalar %= prime
        if not scalar:
            continue
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            denominator = coefficient.denominator % prime
            if not denominator:
                raise ZeroDivisionError(f"generator denominator vanishes modulo {prime}")
            delta = scalar * (coefficient.numerator % prime) * pow(denominator, -1, prime)
            product = add_exponents(multiplier, exponents)
            updated = (accumulator.get(product, 0) + delta) % prime
            if updated:
                accumulator[product] = updated
            else:
                accumulator.pop(product, None)
    return accumulator


def modular_terms(terms, prime):
    result = {}
    for exponents, coefficient in terms:
        denominator = coefficient.denominator % prime
        if not denominator:
            raise ZeroDivisionError(f"target denominator vanishes modulo {prime}")
        value = coefficient.numerator % prime * pow(denominator, -1, prime) % prime
        if value:
            result[exponents] = value
    return result


def hopcroft_karp(adjacency):
    left_count = len(adjacency)
    pair_left = [-1] * left_count
    pair_right = {}
    distance = [0] * left_count
    infinity = left_count + 1

    def bfs():
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
                mate = pair_right.get(right, -1)
                if mate < 0:
                    found = True
                elif distance[mate] == infinity:
                    distance[mate] = distance[left] + 1
                    queue.append(mate)
        return found

    def dfs(left):
        for right in adjacency[left]:
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
    return size, pair_left


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


def p181_pivot_coordinates(columns, preferred_rows, coordinate_degrees, started):
    basis = {}
    pivots = []
    for column_index, integer_column in enumerate(columns):
        work = {coordinate: value % 181 for coordinate, value in integer_column if value % 181}
        for pivot in pivots:
            factor = work.get(pivot, 0)
            if not factor:
                continue
            for coordinate, value in basis[pivot].items():
                updated = (work.get(coordinate, 0) - factor * value) % 181
                if updated:
                    work[coordinate] = updated
                else:
                    work.pop(coordinate, None)
        if not work:
            raise AssertionError(f"Koszul rank dropped at column {column_index}")
        preferred = preferred_rows[column_index]
        pivot = preferred if preferred in work else min(
            work, key=lambda coordinate: (coordinate_degrees[coordinate], coordinate)
        )
        inverse = pow(work[pivot], -1, 181)
        basis[pivot] = {coordinate: value * inverse % 181 for coordinate, value in work.items()}
        pivots.append(pivot)
        if column_index % 64 == 0:
            guard(started, "p181 fixed-pivot reconstruction")
    return pivots


def fixed_minor_rank(columns, selected, prime, started):
    """Rank the selected square minor by independent sparse column elimination."""

    selected_set = set(selected)
    selected_position = {coordinate: position for position, coordinate in enumerate(selected)}
    basis = {}
    pivot_order = []
    preferred_hits = 0
    dependent_columns = []
    maximum_support = 0
    coefficient_updates = 0
    for column_index, integer_column in enumerate(columns):
        work = {
            coordinate: value % prime
            for coordinate, value in integer_column
            if coordinate in selected_set and value % prime
        }
        maximum_support = max(maximum_support, len(work))
        for pivot in pivot_order:
            factor = work.get(pivot, 0)
            if not factor:
                continue
            for coordinate, value in basis[pivot].items():
                updated = (work.get(coordinate, 0) - factor * value) % prime
                if updated:
                    work[coordinate] = updated
                else:
                    work.pop(coordinate, None)
                coefficient_updates += 1
        if not work:
            dependent_columns.append(column_index)
            continue
        preferred = selected[column_index]
        if preferred in work:
            pivot = preferred
            preferred_hits += 1
        else:
            pivot = min(work, key=selected_position.__getitem__)
        inverse = pow(work[pivot], -1, prime)
        basis[pivot] = {coordinate: value * inverse % prime for coordinate, value in work.items()}
        pivot_order.append(pivot)
        maximum_support = max(maximum_support, len(work))
        if column_index % 64 == 0:
            guard(started, f"fixed-minor rank modulo {prime}")
    return len(pivot_order), {
        "rank": len(pivot_order),
        "dependent_column_count": len(dependent_columns),
        "first_dependent_column": dependent_columns[0] if dependent_columns else None,
        "preferred_pivot_hits": preferred_hits,
        "coefficient_update_count": coefficient_updates,
        "maximum_working_support": maximum_support,
        "pivot_coordinate_set_sha256": canonical_hash(sorted(pivot_order)),
    }


def reconstruct(campaign: Path, started: float):
    for relative, expected in FROZEN_INPUT_HASHES.items():
        observed = sha256_bytes((campaign / relative).read_bytes())
        if observed != expected:
            raise ValueError(f"frozen input hash changed: {relative}")

    sys.path.insert(0, str(campaign / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading_form, open_factor = homogeneous_saturation_system()
    if len(equations) != 17 or len(variables) != 18:
        raise ValueError("frozen cubic system dimensions changed")
    cubic_expressions = [sp.expand(equation) for equation in equations]
    cubic_terms = [rational_terms(equation, variables) for equation in equations]
    h_terms, h_expression = load_term_artifact(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4, 4,
    )
    h2_terms, h2_expression = load_term_artifact(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 4, 3,
    )
    h3_terms, h3_expression = load_term_artifact(
        campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
        "terms", variables, 248, 4, 2,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = cubic_expressions + [h_expression, h2_expression]
    generator_degrees = [3] * 17 + [4, 4]
    generator_characters = []
    for terms, expected_degree in zip(generator_terms, generator_degrees, strict=True):
        degrees = {sum(exponents) for exponents, _ in terms}
        characters = {character(exponents) for exponents, _ in terms}
        if degrees != {expected_degree} or len(characters) != 1:
            raise ValueError("generator grading changed")
        generator_characters.append(next(iter(characters)))
    if expression_hash(generator_expressions) != EXPECTED_GENERATOR_HASH:
        raise ValueError("generator expression stream changed")

    target_expression = sp.expand(open_factor * h3_expression)
    target_terms = rational_terms(target_expression, variables)
    if expression_hash((target_expression,)) != EXPECTED_TARGET_HASH:
        raise ValueError("target expression changed")

    pools = {}
    for degree in (4, 5):
        for monomial in exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (degree, weight) in enumerate(
        zip(generator_degrees, generator_characters, strict=True)
    ):
        multiplier_degree = TARGET_DEGREE - degree
        multiplier_character = (TARGET_CHARACTER - weight) % CHARACTER_MODULUS
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(multiplier_degree, multiplier_character)]
        )
    if len(descriptors) != EXPECTED_COORDINATE_COUNT:
        raise AssertionError("multiplier-coordinate count changed")
    if canonical_hash(descriptors) != EXPECTED_DESCRIPTOR_HASH:
        raise AssertionError("descriptor stream changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}
    guard(started, "problem reconstruction")

    columns = []
    pair_counts = Counter()
    for left in range(len(generator_terms)):
        for right in range(left + 1, len(generator_terms)):
            residual_degree = TARGET_DEGREE - generator_degrees[left] - generator_degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (
                TARGET_CHARACTER - generator_characters[left] - generator_characters[right]
            ) % CHARACTER_MODULUS
            for residual in exponent_tuples(len(variables), residual_degree):
                if character(residual) != residual_character:
                    continue
                column = primitive_koszul_row(
                    left, right, residual, generator_terms, descriptor_index
                )
                if exact_koszul_image(column, descriptors, generator_terms):
                    raise AssertionError("a reconstructed Koszul row has nonzero exact image")
                columns.append(column)
                label = (
                    ("cubic" if generator_degrees[left] == 3 else "quartic")
                    + "-"
                    + ("cubic" if generator_degrees[right] == 3 else "quartic")
                )
                pair_counts[label] += 1
                if len(columns) % 64 == 0:
                    guard(started, "Koszul reconstruction and exact A*K replay")
    if len(columns) != EXPECTED_COLUMN_COUNT or sum(map(len, columns)) != EXPECTED_NNZ:
        raise AssertionError("Koszul matrix profile changed")
    if dict(pair_counts) != {"cubic-cubic": 1993, "cubic-quartic": 60}:
        raise AssertionError("Koszul pair profile changed")

    adjacency = [[coordinate for coordinate, _ in column] for column in columns]
    matching_size, matching = hopcroft_karp(adjacency)
    if matching_size != EXPECTED_COLUMN_COUNT or canonical_hash(matching) != EXPECTED_MATCHING_HASH:
        raise AssertionError("support matching changed")
    coordinate_degrees = Counter(coordinate for row in adjacency for coordinate in row)
    active = sorted(coordinate_degrees)
    if len(active) != EXPECTED_ACTIVE_COORDINATES:
        raise AssertionError("active-coordinate count changed")
    active_index = {coordinate: index for index, coordinate in enumerate(active)}
    union_find = UnionFind(len(columns) + len(active))
    for row_index, coordinates in enumerate(adjacency):
        for coordinate in coordinates:
            union_find.union(row_index, len(columns) + active_index[coordinate])
    components = {}
    for row_index in range(len(columns)):
        root = union_find.find(row_index)
        components.setdefault(root, [0, 0])[0] += 1
    for coordinate in active:
        root = union_find.find(len(columns) + active_index[coordinate])
        components.setdefault(root, [0, 0])[1] += 1
    profiles = sorted(components.values(), reverse=True)
    if canonical_hash(profiles) != EXPECTED_COMPONENT_HASH:
        raise AssertionError("support-component profile changed")

    pivots = p181_pivot_coordinates(columns, matching, coordinate_degrees, started)
    if len(pivots) != EXPECTED_COLUMN_COUNT or canonical_hash(pivots) != EXPECTED_PIVOT_HASH:
        raise AssertionError("fixed p181 pivot-coordinate stream changed")
    guard(started, "fixed coordinate reconstruction")
    return {
        "variables": variables,
        "descriptors": descriptors,
        "generator_terms": generator_terms,
        "target_terms": target_terms,
        "columns": columns,
        "pivots": pivots,
        "pair_counts": dict(pair_counts),
        "matching_hash": canonical_hash(matching),
        "component_hash": canonical_hash(profiles),
    }


def get_first(mapping, names, *, required=True):
    for name in names:
        if name in mapping:
            return mapping[name]
    if required:
        raise KeyError(f"none of the required keys is present: {names}")
    return None


def relative_campaign_path(campaign: Path, value) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = campaign / path
    return path.resolve()


def extract_producer_records(campaign: Path, producer_receipt_path: Path):
    """Parse only the reviewed fixed-normalizer schema (with explicit aliases)."""

    receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    if not str(receipt.get("status", "")).startswith("PASS"):
        raise ValueError("producer normalizer receipt is not PASS")
    receipt_pivots = get_first(
        receipt,
        ("pivot_coordinates", "selected_coordinates", "fixed_coordinate_indices"),
        required=False,
    )
    receipt_pivot_hash = get_first(
        receipt,
        (
            "pivot_coordinates_sha256",
            "selected_coordinates_sha256",
            "fixed_coordinate_indices_sha256",
        ),
        required=False,
    )
    raw_records = get_first(
        receipt,
        ("prime_records", "normalizations", "transformed_artifacts", "artifacts"),
    )
    if isinstance(raw_records, dict):
        items = []
        for prime_text, record in raw_records.items():
            if isinstance(record, str):
                record = {"artifact_path": record}
            record = dict(record)
            record.setdefault("characteristic", int(prime_text))
            items.append(record)
        raw_records = items
    if not isinstance(raw_records, list) or len(raw_records) != len(PRIMES):
        raise ValueError("producer receipt must list exactly five prime records")

    records = {}
    for outer in raw_records:
        if not isinstance(outer, dict):
            raise TypeError("producer prime record is not an object")
        artifact_path = relative_campaign_path(
            campaign,
            get_first(outer, ("artifact_path", "path", "normalized_artifact_path")),
        )
        if campaign.resolve() not in artifact_path.parents:
            raise ValueError("producer artifact is outside the campaign")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        prime = int(
            get_first(
                artifact,
                ("characteristic", "prime", "modulus"),
                required=False,
            )
            or get_first(outer, ("characteristic", "prime", "modulus"))
        )
        if prime in records:
            raise ValueError(f"duplicate producer record for prime {prime}")
        normalized = list(
            map(
                int,
                get_first(
                    artifact,
                    (
                        "coordinate_vector",
                        "normalized_coordinate_vector",
                        "transformed_coordinate_vector",
                    ),
                ),
            )
        )
        alpha = list(
            map(
                int,
                get_first(
                    artifact,
                    (
                        "koszul_coefficient_vector",
                        "alpha_vector",
                        "koszul_coefficients",
                        "normalization_coefficients",
                    ),
                ),
            )
        )
        pivots = get_first(
            artifact,
            ("pivot_coordinates", "selected_coordinates", "fixed_coordinate_indices"),
            required=False,
        )
        pivots = list(map(int, pivots if pivots is not None else receipt_pivots or []))
        pivot_hash = get_first(
            artifact,
            (
                "pivot_coordinates_sha256",
                "selected_coordinates_sha256",
                "fixed_coordinate_indices_sha256",
            ),
            required=False,
        ) or receipt_pivot_hash
        source_path_value = get_first(
            artifact,
            ("source_artifact_path", "source_path"),
            required=False,
        ) or get_first(outer, ("source_artifact_path", "source_path"), required=False)
        source_hash = get_first(
            artifact,
            ("source_artifact_sha256", "source_sha256"),
            required=False,
        ) or get_first(outer, ("source_artifact_sha256", "source_sha256"), required=False)
        if source_path_value is None or source_hash is None:
            source_object = artifact.get("source_artifact") or outer.get("source_artifact")
            if isinstance(source_object, dict):
                source_path_value = source_path_value or source_object.get("path")
                source_hash = source_hash or source_object.get("sha256")
        if source_path_value is None or source_hash is None:
            raise KeyError("producer artifact lacks explicit source path/hash binding")
        source_path = relative_campaign_path(campaign, source_path_value)
        vector_hash = get_first(
            artifact,
            (
                "coordinate_vector_sha256",
                "normalized_coordinate_vector_sha256",
                "transformed_coordinate_vector_sha256",
            ),
        )
        alpha_hash = get_first(
            artifact,
            (
                "koszul_coefficient_vector_sha256",
                "alpha_vector_sha256",
                "koszul_coefficients_sha256",
                "normalization_coefficients_sha256",
            ),
        )
        records[prime] = {
            "artifact_path": artifact_path,
            "artifact_sha256": sha256_bytes(artifact_path.read_bytes()),
            "artifact": artifact,
            "source_path": source_path,
            "source_sha256": str(source_hash),
            "normalized": normalized,
            "normalized_sha256": str(vector_hash),
            "alpha": alpha,
            "alpha_sha256": str(alpha_hash),
            "pivots": pivots,
            "pivot_sha256": str(pivot_hash),
        }
    if set(records) != set(PRIMES):
        raise ValueError(f"producer prime set changed: {sorted(records)}")
    return receipt, records


def source_record(campaign: Path, prime: int):
    artifact_relative, artifact_hash, receipt_relative, receipt_hash = SOURCE_FILES[prime]
    artifact_path = (campaign / artifact_relative).resolve()
    receipt_path = (campaign / receipt_relative).resolve()
    if sha256_bytes(artifact_path.read_bytes()) != artifact_hash:
        raise ValueError(f"frozen source artifact changed at prime {prime}")
    if sha256_bytes(receipt_path.read_bytes()) != receipt_hash:
        raise ValueError(f"frozen source receipt changed at prime {prime}")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    replay = receipt.get("same_process_sparse_replay", {})
    if (
        receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        or int(receipt.get("characteristic", -1)) != prime
        or not replay.get("completed")
        or not replay.get("identity_zero")
        or int(replay.get("mismatch_count", -1)) != 0
        or replay.get("first_mismatch") is not None
    ):
        raise ValueError(f"frozen source replay is not exact at prime {prime}")
    vector = list(map(int, artifact["coordinate_vector"]))
    if (
        int(artifact.get("characteristic", -1)) != prime
        or len(vector) != EXPECTED_COORDINATE_COUNT
        or canonical_hash(vector) != artifact.get("coordinate_vector_sha256")
        or artifact.get("generator_stream_sha256") != EXPECTED_GENERATOR_HASH
        or artifact.get("row_descriptor_sha256") != EXPECTED_DESCRIPTOR_HASH
        or artifact.get("target_sha256") != EXPECTED_TARGET_HASH
    ):
        raise ValueError(f"frozen source artifact metadata failed at prime {prime}")
    return artifact_path, artifact_hash, vector


def verify_normalization_record(campaign, prime, record, reconstruction, started):
    source_path, source_hash, source = source_record(campaign, prime)
    if record["source_path"] != source_path or record["source_sha256"] != source_hash:
        raise ValueError(f"producer source binding changed at prime {prime}")
    normalized = record["normalized"]
    alpha = record["alpha"]
    pivots = record["pivots"]
    if len(normalized) != EXPECTED_COORDINATE_COUNT or len(alpha) != EXPECTED_COLUMN_COUNT:
        raise ValueError(f"producer vector dimensions changed at prime {prime}")
    if pivots != reconstruction["pivots"] or record["pivot_sha256"] != EXPECTED_PIVOT_HASH:
        raise ValueError(f"producer fixed-coordinate stream changed at prime {prime}")
    if canonical_hash(normalized) != record["normalized_sha256"]:
        raise ValueError(f"normalized-vector hash mismatch at prime {prime}")
    if canonical_hash(alpha) != record["alpha_sha256"]:
        raise ValueError(f"Koszul-coefficient hash mismatch at prime {prime}")
    if any(not 0 <= value < prime for value in normalized + alpha):
        raise ValueError(f"noncanonical modular residue at prime {prime}")
    if any(normalized[coordinate] % prime for coordinate in pivots):
        raise AssertionError(f"fixed coordinates are not all zero at prime {prime}")

    combination = [0] * EXPECTED_COORDINATE_COUNT
    for scalar, column in zip(alpha, reconstruction["columns"], strict=True):
        if not scalar:
            continue
        for coordinate, value in column:
            combination[coordinate] = (combination[coordinate] + scalar * value) % prime
    mismatch = next(
        (
            coordinate
            for coordinate in range(EXPECTED_COORDINATE_COUNT)
            if (normalized[coordinate] - source[coordinate] - combination[coordinate]) % prime
        ),
        None,
    )
    if mismatch is not None:
        raise AssertionError(f"Koszul difference mismatch at prime {prime}, coordinate {mismatch}")
    guard(started, f"Koszul-combination replay modulo {prime}")

    target = modular_terms(reconstruction["target_terms"], prime)
    source_image = modular_macaulay_image(
        source, reconstruction["descriptors"], reconstruction["generator_terms"], prime
    )
    normalized_image = modular_macaulay_image(
        normalized, reconstruction["descriptors"], reconstruction["generator_terms"], prime
    )
    if source_image != target:
        raise AssertionError(f"independent source identity replay failed modulo {prime}")
    if normalized_image != target:
        raise AssertionError(f"independent normalized identity replay failed modulo {prime}")
    guard(started, f"independent Macaulay replay modulo {prime}")
    return {
        "prime": prime,
        "producer_artifact_path": str(record["artifact_path"]),
        "producer_artifact_sha256": record["artifact_sha256"],
        "source_artifact_path": str(source_path),
        "source_artifact_sha256": source_hash,
        "normalized_coordinate_vector_sha256": record["normalized_sha256"],
        "koszul_coefficient_vector_sha256": record["alpha_sha256"],
        "selected_coordinates_zero": True,
        "difference_equals_recorded_koszul_combination": True,
        "source_identity_independently_replayed": True,
        "normalized_identity_independently_replayed": True,
        "normalized_support_count": sum(bool(value) for value in normalized),
        "koszul_coefficient_support_count": sum(bool(value) for value in alpha),
    }


def audit(campaign: Path, producer_receipt_path: Path, started: float):
    reconstruction = reconstruct(campaign, started)
    rank_records = {}
    for prime in PRIMES:
        rank_started = time.perf_counter()
        rank, telemetry = fixed_minor_rank(
            reconstruction["columns"], reconstruction["pivots"], prime, started
        )
        if rank != EXPECTED_COLUMN_COUNT:
            raise AssertionError(f"fixed minor is singular modulo {prime}: rank {rank}")
        rank_records[str(prime)] = {
            **telemetry,
            "seconds": time.perf_counter() - rank_started,
        }
        guard(started, f"fixed-minor rank modulo {prime}")

    producer_receipt_hash = sha256_bytes(producer_receipt_path.read_bytes())
    _producer_receipt, producer_records = extract_producer_records(
        campaign, producer_receipt_path
    )
    prime_records = []
    for prime in PRIMES:
        prime_records.append(
            verify_normalization_record(
                campaign, prime, producer_records[prime], reconstruction, started
            )
        )

    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    guard(started, "final receipt")
    return {
        "schema": "hc4.third-colon-koszul-fixed-minor-normalization-independent-audit.v1",
        "status": "PASS_INDEPENDENT_FIXED_MINOR_KOSZUL_NORMALIZATION",
        "assurance": "independent exact reconstruction and bounded five-prime modular replay",
        "claim_boundary": (
            "A PASS proves only that the producer's five modular vectors are the stated "
            "fixed-minor projections of the five frozen modular identities along 2,053 "
            "independently reconstructed exact Koszul syzygies, that the same integer "
            "minor is nonsingular at the five frozen primes, and that every transformed "
            "vector independently replays the same modular Macaulay identity. It proves "
            "no QQ multiplier identity, colon or saturation equality, secant-chart "
            "closure, nullcone containment, or HC4."
        ),
        "independence_boundary": {
            "producer_normalizer_imported_or_executed": False,
            "producer_normalizer_source_used_as_code": False,
            "koszul_rows_reconstructed_from_frozen_generators": True,
            "pivot_coordinates_reconstructed_by_local_sparse_echelon": True,
            "fixed_minor_rank_implementation": "local_sparse_column_elimination",
            "macaulay_identity_rebuilt_and_replayed": True,
        },
        "dimensions": {
            "multiplier_coordinate_count": EXPECTED_COORDINATE_COUNT,
            "koszul_row_count": len(reconstruction["columns"]),
            "koszul_nonzero_count": sum(map(len, reconstruction["columns"])),
            "fixed_minor_shape": [EXPECTED_COLUMN_COUNT, EXPECTED_COLUMN_COUNT],
        },
        "hashes": {
            "frozen_inputs": FROZEN_INPUT_HASHES,
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "producer_receipt_path": str(producer_receipt_path),
            "producer_receipt_sha256": producer_receipt_hash,
            "generator_stream_sha256": EXPECTED_GENERATOR_HASH,
            "descriptor_stream_sha256": EXPECTED_DESCRIPTOR_HASH,
            "target_sha256": EXPECTED_TARGET_HASH,
            "matching_vector_sha256": reconstruction["matching_hash"],
            "component_profiles_sha256": reconstruction["component_hash"],
            "pivot_coordinates_sha256": canonical_hash(reconstruction["pivots"]),
        },
        "fixed_minor_ranks": rank_records,
        "prime_records": prime_records,
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "process_swap_cap": 0,
            "total_wall_seconds": wall,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swaps": process_swaps(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def p197_singularity_audit(campaign: Path, producer_receipt_path: Path, started: float):
    """Independently decide the frozen minor's rank modulo 197."""

    producer_script_path = campaign / "scripts/normalize_j2_secant_r10_third_colon_koszul_fixed_minor.py"
    if sha256_bytes(producer_script_path.read_bytes()) != EXPECTED_FINAL_PRODUCER_SCRIPT_HASH:
        raise ValueError("final producer script hash changed")
    if sha256_bytes(producer_receipt_path.read_bytes()) != EXPECTED_FINAL_PRODUCER_RECEIPT_HASH:
        raise ValueError("final producer failure receipt hash changed")
    reconstruction = reconstruct(campaign, started)
    custom_started = time.perf_counter()
    custom_rank, custom_telemetry = fixed_minor_rank(
        reconstruction["columns"], reconstruction["pivots"], 197, started
    )
    custom_seconds = time.perf_counter() - custom_started
    guard(started, "custom p197 fixed-minor rank")

    # This matrix is K[:,R]^T: each reconstructed Koszul row is one column.
    # Building it from sparse coordinate entries avoids sharing the producer's
    # elimination state or its row-oriented sparse representation.
    from sage.all import GF, Matrix

    selected_position = {
        coordinate: position for position, coordinate in enumerate(reconstruction["pivots"])
    }
    entries = {}
    for column_index, column in enumerate(reconstruction["columns"]):
        for coordinate, value in column:
            row_index = selected_position.get(coordinate)
            if row_index is not None and value % 197:
                entries[(row_index, column_index)] = value % 197
    if len(entries) != 13915:
        raise AssertionError(f"frozen p197 minor support changed: {len(entries)} nonzeros")
    guard(started, "explicit p197 minor construction")

    sage_started = time.perf_counter()
    matrix = Matrix(GF(197), EXPECTED_COLUMN_COUNT, EXPECTED_COLUMN_COUNT, entries, sparse=True)
    sage_rank = int(matrix.rank())
    sage_seconds = time.perf_counter() - sage_started
    guard(started, "Sage sparse p197 rank")
    if custom_rank != sage_rank:
        raise AssertionError(
            f"independent rank methods disagree modulo 197: custom={custom_rank}, Sage={sage_rank}"
        )
    if sage_rank != 2052:
        raise AssertionError(f"unexpected frozen-minor rank modulo 197: {sage_rank}")

    producer_hash = sha256_bytes(producer_receipt_path.read_bytes())
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    if producer_receipt.get("status") != "FAIL_CLOSED_FIXED_MINOR_SINGULAR":
        raise ValueError("bound producer receipt is not the frozen singular-minor stop")
    witness = producer_receipt.get("singular_minor_witness", {})
    if (
        int(witness.get("characteristic", -1)) != 197
        or witness.get("pivot_coordinates_sha256") != EXPECTED_PIVOT_HASH
        or list(map(int, witness.get("shape", []))) != [2053, 2053]
    ):
        raise ValueError("producer failure receipt is not bound to the frozen p197 minor")

    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    guard(started, "p197 singularity receipt")
    return {
        "schema": "hc4.third-colon-koszul-fixed-minor-p197-independent-singularity-audit.v1",
        "status": "PASS_INDEPENDENT_P197_FIXED_MINOR_SINGULARITY",
        "assurance": "independent exact reconstruction and two-method finite-field rank audit",
        "claim_boundary": (
            "A PASS proves only that the preregistered 2,053-by-2,053 integer minor "
            "selected by the frozen p181 pivot rule has rank exactly 2,052 modulo 197. "
            "It therefore stops this fixed-minor five-prime normalization route. It does "
            "not invalidate the p197 modular multiplier identity, prove or disprove QQ "
            "membership, determine the 114-dimensional quotient, compute a colon or "
            "saturation, close the secant chart, establish nullcone containment, or prove HC4."
        ),
        "independence_boundary": {
            "producer_normalizer_imported_or_executed": False,
            "producer_normalizer_source_used_as_code": False,
            "koszul_rows_reconstructed_from_frozen_generators": True,
            "pivot_coordinates_reconstructed_from_frozen_p181_rule": True,
            "rank_method_one": "local sparse incremental column basis with dependent-column continuation",
            "rank_method_two": "Sage sparse matrix rank over GF(197)",
        },
        "dimensions": {
            "minor_shape": [2053, 2053],
            "minor_nonzero_count": len(entries),
            "rank_mod_197": sage_rank,
            "nullity_mod_197": EXPECTED_COLUMN_COUNT - sage_rank,
        },
        "exact_checks": {
            "all_2053_koszul_rows_reconstructed": len(reconstruction["columns"]) == 2053,
            "all_koszul_rows_have_exact_zero_macaulay_image": True,
            "pivot_coordinate_hash_reproduced": canonical_hash(reconstruction["pivots"])
            == EXPECTED_PIVOT_HASH,
            "custom_rank_mod_197": custom_rank,
            "sage_sparse_rank_mod_197": sage_rank,
            "rank_methods_agree": custom_rank == sage_rank,
            "producer_reported_rank_is_not_relied_upon": True,
            "producer_reported_rank": witness.get("rank"),
        },
        "custom_rank_telemetry": {
            **custom_telemetry,
            "seconds": custom_seconds,
        },
        "sage_rank_telemetry": {
            "algorithm": "Sage sparse Matrix.rank over GF(197)",
            "seconds": sage_seconds,
        },
        "hashes": {
            "frozen_inputs": FROZEN_INPUT_HASHES,
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "producer_failure_receipt_path": str(producer_receipt_path),
            "producer_failure_receipt_sha256": producer_hash,
            "producer_script_path": str(producer_script_path),
            "producer_script_sha256": EXPECTED_FINAL_PRODUCER_SCRIPT_HASH,
            "generator_stream_sha256": EXPECTED_GENERATOR_HASH,
            "descriptor_stream_sha256": EXPECTED_DESCRIPTOR_HASH,
            "matching_vector_sha256": reconstruction["matching_hash"],
            "component_profiles_sha256": reconstruction["component_hash"],
            "pivot_coordinates_sha256": canonical_hash(reconstruction["pivots"]),
            "minor_entries_sha256": canonical_hash(
                [[row, column, int(value)] for (row, column), value in sorted(entries.items())]
            ),
        },
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "process_swap_cap": 0,
            "total_wall_seconds": wall,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swaps": process_swaps(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--producer-receipt",
        type=Path,
        required=False,
        help="passing fixed-minor normalizer receipt to audit",
    )
    parser.add_argument(
        "--p197-singularity",
        action="store_true",
        help="audit the preregistered minor's p197 singularity instead of normalized artifacts",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    if arguments.producer_receipt is None:
        if not arguments.p197_singularity:
            parser.error("--producer-receipt is required")
        arguments.producer_receipt = Path(
            "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization.json"
        )
    producer_receipt_path = relative_campaign_path(campaign, arguments.producer_receipt)
    default_name = (
        "hsop-j2-secant-r10-third-colon-koszul-fixed-minor-p197-independent-singularity-audit.json"
        if arguments.p197_singularity
        else "hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization-independent-audit.json"
    )
    output = arguments.output or campaign / "receipts" / default_name
    if not output.is_absolute():
        output = campaign / output
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("180-second alarm")),
    )
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        receipt = (
            p197_singularity_audit(campaign, producer_receipt_path, started)
            if arguments.p197_singularity
            else audit(campaign, producer_receipt_path, started)
        )
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "output": str(output),
                    "wall_seconds": receipt["resources"]["total_wall_seconds"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-fixed-minor-normalization-independent-audit.v1",
            "status": "FAIL_CLOSED_INDEPENDENT_NORMALIZATION_AUDIT",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No positive mathematical conclusion is licensed by this failed or incomplete audit.",
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "producer_receipt_path": str(producer_receipt_path),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swaps": process_swaps(),
        }
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
