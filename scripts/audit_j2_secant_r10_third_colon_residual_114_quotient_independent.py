#!/usr/bin/env sage-python
"""Independent replay of the frozen residual-114 quotient scout.

This file does not import or execute the producer.  It reconstructs the
integer Koszul rows from the frozen rational generators, rebuilds the free
restriction and p181 lexicographic chart, replays the same fixed integer B at
all five fields, and independently performs the complete transition-entry
M70 census.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import os
import platform
import resource
import signal
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIMES = (181, 173, 197, 2147483647, 2147483629)
SOURCE_PRIMES = (181, 2147483647, 2147483629)
SELECTOR_PRIMES = (173, 197)
SOURCE_MODULUS = 834715161561466408303
FULL_COUNT = 38048
FREE_COUNT = 2167
KOSZUL_COUNT = 2053
QUOTIENT_COUNT = 114
ENTRY_COUNT = KOSZUL_COUNT * QUOTIENT_COUNT
WALL_CAP_SECONDS = 300.0
RSS_CAP_BYTES = 1_500_000_000
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)

PREREG_PATH = "research/THIRD_COLON_RESIDUAL_114_QUOTIENT_SCOUT_PREREGISTRATION.md"
PREREG_HASH = "112fb4ea3de68c84459422903e0c6f3c4c2902d364b13639f130c2a7f6cebf22"
PRODUCER_PATH = "scripts/scout_j2_secant_r10_third_colon_residual_114_quotient.py"
PRODUCER_HASH = "607706e89e25990ed3ed1bdd5f7d9a972c824b0bff62a33035789860f75f3b81"
ARTIFACT_PATH = "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
ARTIFACT_HASH = "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74"
PRODUCER_RECEIPT_PATH = "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json"
PRODUCER_RECEIPT_HASH = "652af633649c32af3322b9405eac8d6e60fdaba5668817de6a11330782bc752a"
OUTPUT_PATH = "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json"
FAILURE_PREFIX = "hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit-failed"

FREE_HASH = "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
KOSZUL_HASH = "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856"

SOURCE_ARTIFACTS = {
    181: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
    173: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
    197: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
    2147483647: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
    2147483629: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
}
SOURCE_HASHES = {
    181: "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b",
    173: "b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c",
    197: "f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272",
    2147483647: "a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad",
    2147483629: "2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90",
}
PRODUCER_FROZEN_HASHES = {
    PREREG_PATH: PREREG_HASH,
    **{SOURCE_ARTIFACTS[p]: SOURCE_HASHES[p] for p in PRIMES},
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json": "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout.py": "39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py": "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def framed_update(hasher, value: object) -> None:
    payload = canonical_bytes(value)
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


class CanonicalListHasher:
    def __init__(self):
        self._digest = hashlib.sha256(b"[")
        self._first = True
        self.count = 0

    def add(self, value: object) -> None:
        if not self._first:
            self._digest.update(b",")
        self._digest.update(canonical_bytes(value))
        self._first = False
        self.count += 1

    def hexdigest(self) -> str:
        clone = self._digest.copy()
        clone.update(b"]")
        return clone.hexdigest()


def native_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def process_swaps() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)


def guard(started: float, stage: str) -> None:
    elapsed = time.perf_counter() - started
    if elapsed >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {elapsed:.6f}s")
    if native_rss_bytes() >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {native_rss_bytes()}")
    if process_swaps() != 0:
        raise MemoryError(f"nonzero process swaps during {stage}: {process_swaps()}")


def write_new_json(path: Path, payload: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="ascii") as handle:
        handle.write(text)


def exponent_tuples(variable_count: int, degree: int):
    def visit(position, remaining, prefix):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from visit(position + 1, remaining - exponent, prefix + (exponent,))

    yield from visit(0, degree, ())


def character(exponents) -> int:
    return sum(a * b for a, b in zip(exponents, CHARACTER_WEIGHTS, strict=True)) % 12


def add_exponents(left, right):
    return tuple(a + b for a, b in zip(left, right, strict=True))


def expression_hash(expressions) -> str:
    text = "\n".join(str(sp.expand(item)).replace("**", "^") for item in expressions)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def rational_terms(expression, variables):
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return [
        (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
        for exponents, coefficient in polynomial.terms()
    ]


def load_quartic(path: Path, key: str, variables, expected_count: int, expected_character: int):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError(f"variable order changed in {path.name}")
    records = payload.get(key)
    if not isinstance(records, list) or len(records) != expected_count:
        raise ValueError(f"term stream changed in {path.name}")
    terms = []
    expression = sp.Integer(0)
    seen = set()
    for record in records:
        exponents = tuple(map(int, record["exponents"]))
        coefficient = Fraction(int(record["numerator"]), int(record["denominator"]))
        if (
            len(exponents) != len(variables)
            or exponents in seen
            or not coefficient
            or sum(exponents) != 4
            or character(exponents) != expected_character
        ):
            raise ValueError(f"malformed quartic term in {path.name}")
        seen.add(exponents)
        terms.append((exponents, coefficient))
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += sp.Rational(coefficient.numerator, coefficient.denominator) * monomial
    terms.sort(reverse=True)
    return terms, sp.expand(expression)


def primitive_koszul_row(left, right, residual, generator_terms, descriptor_index):
    rational = {}
    for exponents, coefficient in generator_terms[right]:
        coordinate = descriptor_index[(left, add_exponents(residual, exponents))]
        rational[coordinate] = rational.get(coordinate, Fraction(0)) + coefficient
    for exponents, coefficient in generator_terms[left]:
        coordinate = descriptor_index[(right, add_exponents(residual, exponents))]
        rational[coordinate] = rational.get(coordinate, Fraction(0)) - coefficient
    rational = {coordinate: value for coordinate, value in rational.items() if value}
    denominator = math.lcm(*(value.denominator for value in rational.values()))
    integral = {
        coordinate: value.numerator * (denominator // value.denominator)
        for coordinate, value in rational.items()
    }
    content = math.gcd(*(abs(value) for value in integral.values()))
    integral = {coordinate: value // content for coordinate, value in integral.items()}
    if integral[min(integral)] < 0:
        integral = {coordinate: -value for coordinate, value in integral.items()}
    if math.gcd(*(abs(value) for value in integral.values())) != 1:
        raise AssertionError("nonprimitive Koszul row")
    return tuple(sorted(integral.items()))


def exact_sparse_image(row, descriptors, generator_terms):
    image = {}
    for coordinate, scalar in row:
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            monomial = add_exponents(multiplier, exponents)
            updated = image.get(monomial, Fraction(0)) + scalar * coefficient
            if updated:
                image[monomial] = updated
            else:
                image.pop(monomial, None)
    return image


def reconstruct_koszul(campaign: Path, started: float):
    for relative, expected in PRODUCER_FROZEN_HASHES.items():
        if file_hash(campaign / relative) != expected:
            raise ValueError(f"frozen input hash changed: {relative}")
    if file_hash(campaign / PRODUCER_PATH) != PRODUCER_HASH:
        raise ValueError("producer source hash changed")
    if file_hash(campaign / ARTIFACT_PATH) != ARTIFACT_HASH:
        raise ValueError("producer artifact hash changed")
    if file_hash(campaign / PRODUCER_RECEIPT_PATH) != PRODUCER_RECEIPT_HASH:
        raise ValueError("producer receipt hash changed")

    sys.path.insert(0, str(campaign / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading, _open = homogeneous_saturation_system()
    if len(equations) != 17 or len(variables) != 18:
        raise ValueError("frozen cubic system dimensions changed")
    cubic_terms = [rational_terms(equation, variables) for equation in equations]
    h_terms, h = load_quartic(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4,
    )
    h2_terms, h2 = load_quartic(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 3,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = [sp.expand(equation) for equation in equations] + [h, h2]
    degrees = [3] * 17 + [4, 4]
    characters = []
    for terms, degree in zip(generator_terms, degrees, strict=True):
        if {sum(exponents) for exponents, _coefficient in terms} != {degree}:
            raise ValueError("generator degree changed")
        values = {character(exponents) for exponents, _coefficient in terms}
        if len(values) != 1:
            raise ValueError("generator character changed")
        characters.append(next(iter(values)))
    if expression_hash(generator_expressions) != GENERATOR_HASH:
        raise ValueError("generator stream changed")

    pools = {}
    for degree in (4, 5):
        for monomial in exponent_tuples(18, degree):
            pools.setdefault((degree, character(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (degree, weight) in enumerate(zip(degrees, characters, strict=True)):
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(8 - degree, (3 - weight) % 12)]
        )
    if len(descriptors) != FULL_COUNT or canonical_hash(descriptors) != DESCRIPTOR_HASH:
        raise ValueError("descriptor stream changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}

    rows = []
    row_hasher = hashlib.sha256()
    pair_counts = collections.Counter()
    for left in range(19):
        for right in range(left + 1, 19):
            residual_degree = 8 - degrees[left] - degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (3 - characters[left] - characters[right]) % 12
            for residual in exponent_tuples(18, residual_degree):
                if character(residual) != residual_character:
                    continue
                row = primitive_koszul_row(
                    left, right, residual, generator_terms, descriptor_index
                )
                if exact_sparse_image(row, descriptors, generator_terms):
                    raise AssertionError("nonzero exact Koszul image")
                rows.append(row)
                framed_update(
                    row_hasher,
                    [[coordinate, str(value)] for coordinate, value in row],
                )
                pair_counts[(degrees[left], degrees[right])] += 1
        guard(started, "independent integer Koszul reconstruction")
    if (
        len(rows) != KOSZUL_COUNT
        or sum(map(len, rows)) != 154939
        or pair_counts != collections.Counter({(3, 3): 1993, (3, 4): 60})
        or row_hasher.hexdigest() != KOSZUL_HASH
    ):
        raise AssertionError("integer Koszul reconstruction profile changed")
    return rows


def load_free_sources(campaign: Path):
    free_reference = None
    bindings = {}
    for prime in PRIMES:
        relative = SOURCE_ARTIFACTS[prime]
        payload = json.loads((campaign / relative).read_text(encoding="utf-8"))
        vector = list(map(int, payload.get("coordinate_vector", [])))
        free = list(map(int, payload.get("free_unknown_indices", [])))
        if (
            int(payload.get("characteristic", -1)) != prime
            or len(vector) != FULL_COUNT
            or canonical_hash(vector) != payload.get("coordinate_vector_sha256")
            or len(free) != FREE_COUNT
            or free != sorted(free)
            or len(set(free)) != FREE_COUNT
            or canonical_hash(free) != FREE_HASH
            or payload.get("free_unknown_indices_sha256") != FREE_HASH
            or any(not 0 <= value < prime for value in vector)
        ):
            raise ValueError(f"malformed frozen source p{prime}")
        if free_reference is None:
            free_reference = free
        elif free != free_reference:
            raise ValueError(f"free-coordinate list changed at p{prime}")
        restriction = [vector[coordinate] for coordinate in free]
        if any(restriction):
            raise ValueError(f"source is nonzero on F at p{prime}")
        bindings[str(prime)] = {
            "artifact_path": relative,
            "artifact_sha256": SOURCE_HASHES[prime],
            "coordinate_vector_sha256": payload["coordinate_vector_sha256"],
            "free_coordinate_restriction_length": len(restriction),
            "free_coordinate_restriction_nonzero_count": 0,
            "free_coordinate_restriction_sha256": canonical_hash(restriction),
            "identity_transformation_applied": False,
        }
    if free_reference is None:
        raise AssertionError("no free list loaded")
    return free_reference, bindings


def restrict_rows(rows, free):
    absolute_to_local = {absolute: local for local, absolute in enumerate(free)}
    restricted = []
    for row_index, row in enumerate(rows):
        local_row = tuple(
            (absolute_to_local[absolute], value)
            for absolute, value in row
            if absolute in absolute_to_local
        )
        if not local_row:
            raise ValueError(f"empty restricted row {row_index}")
        if tuple(sorted(local_row)) != local_row:
            raise AssertionError("restricted row order changed")
        restricted.append(local_row)
    return restricted, absolute_to_local


def select_p181_pivots(rows, started):
    basis = {}
    pivots = []
    reductions = coefficient_updates = basis_nonzeros = 0
    maximum_working_support = 0
    for row_index, row in enumerate(rows):
        work = {column: value % 181 for column, value in row if value % 181}
        maximum_working_support = max(maximum_working_support, len(work))
        while work:
            column = min(work)
            if column not in basis:
                break
            factor = work[column]
            reductions += 1
            for target, value in basis[column].items():
                updated = (work.get(target, 0) - factor * value) % 181
                if updated:
                    work[target] = updated
                else:
                    work.pop(target, None)
                coefficient_updates += 1
            maximum_working_support = max(maximum_working_support, len(work))
        if not work:
            raise ValueError(f"restricted p181 rank stopped before row {row_index}")
        pivot = min(work)
        inverse = pow(work[pivot], -1, 181)
        normalized = {column: value * inverse % 181 for column, value in work.items()}
        if min(normalized) != pivot or normalized[pivot] != 1 or pivot in basis:
            raise AssertionError("p181 lexicographic pivot invariant failed")
        basis[pivot] = normalized
        pivots.append(pivot)
        basis_nonzeros += len(normalized)
        if row_index % 128 == 0:
            guard(started, "p181 lexicographic pivot replay")
    telemetry = {
        "algorithm": "row_order_incremental_sparse_echelon_smallest_nonzero_local_coordinate_mod_181",
        "rank": len(pivots),
        "row_count_processed": len(rows),
        "reduction_count": reductions,
        "coefficient_update_count": coefficient_updates,
        "maximum_working_support": maximum_working_support,
        "stored_basis_nonzero_count": basis_nonzeros,
        "matching_or_column_preference_used": False,
        "column_swap_or_lookahead_used": False,
    }
    return pivots, telemetry


def split_matrices(rows, pivots, complement):
    ppos = {column: index for index, column in enumerate(pivots)}
    spos = {column: index for index, column in enumerate(complement)}
    b_rows, c_rows = [], []
    for row in rows:
        b_row, c_row = [], []
        for column, value in row:
            if column in ppos:
                b_row.append((ppos[column], value))
            else:
                c_row.append((spos[column], value))
        b_rows.append(tuple(sorted(b_row)))
        c_rows.append(tuple(sorted(c_row)))
    return b_rows, c_rows


def solve_transition(prime, b_rows, c_rows, restricted, pivots, complement, started):
    basis_b, basis_c = {}, {}
    reductions = b_updates = c_updates = 0
    max_b_support = max_c_support = 0
    discovered = []
    for row_index, (integer_b, integer_c) in enumerate(zip(b_rows, c_rows, strict=True)):
        work_b = {column: value % prime for column, value in integer_b if value % prime}
        work_c = {column: value % prime for column, value in integer_c if value % prime}
        max_b_support = max(max_b_support, len(work_b))
        max_c_support = max(max_c_support, len(work_c))
        while work_b:
            column = min(work_b)
            if column not in basis_b:
                break
            factor = work_b[column]
            reductions += 1
            for target, value in basis_b[column].items():
                updated = (work_b.get(target, 0) - factor * value) % prime
                if updated:
                    work_b[target] = updated
                else:
                    work_b.pop(target, None)
                b_updates += 1
            for target, value in basis_c[column].items():
                updated = (work_c.get(target, 0) - factor * value) % prime
                if updated:
                    work_c[target] = updated
                else:
                    work_c.pop(target, None)
                c_updates += 1
            max_b_support = max(max_b_support, len(work_b))
            max_c_support = max(max_c_support, len(work_c))
        if not work_b:
            raise ValueError(f"fixed B singular modulo {prime} at row {row_index}")
        pivot = min(work_b)
        inverse = pow(work_b[pivot], -1, prime)
        normalized_b = {column: value * inverse % prime for column, value in work_b.items()}
        normalized_c = {column: value * inverse % prime for column, value in work_c.items()}
        if min(normalized_b) != pivot or normalized_b[pivot] != 1 or pivot in basis_b:
            raise AssertionError(f"fixed-B pivot invariant failed at p{prime}")
        basis_b[pivot] = normalized_b
        basis_c[pivot] = normalized_c
        discovered.append(pivot)
        if row_index % 128 == 0:
            guard(started, f"fixed-B elimination p{prime}")
    if len(basis_b) != KOSZUL_COUNT or set(basis_b) != set(range(KOSZUL_COUNT)):
        raise ValueError(f"fixed B rank below 2053 modulo {prime}")

    transition = [None] * KOSZUL_COUNT
    back_updates = 0
    for pivot in range(KOSZUL_COUNT - 1, -1, -1):
        result = [0] * QUOTIENT_COUNT
        for column, value in basis_c[pivot].items():
            result[column] = value
        for later, coefficient in basis_b[pivot].items():
            if later == pivot:
                continue
            if later < pivot or transition[later] is None:
                raise AssertionError(f"nonechelon fixed B at p{prime}")
            for quotient_column in range(QUOTIENT_COUNT):
                result[quotient_column] = (
                    result[quotient_column]
                    - coefficient * transition[later][quotient_column]
                ) % prime
                back_updates += 1
        transition[pivot] = result
        if pivot % 128 == 0:
            guard(started, f"fixed-B back substitution p{prime}")

    bt_stream = CanonicalListHasher()
    bt_mismatches = 0
    for row_index, (integer_b, integer_c) in enumerate(zip(b_rows, c_rows, strict=True)):
        expected = {column: value % prime for column, value in integer_c if value % prime}
        residual = []
        for quotient_column in range(QUOTIENT_COUNT):
            value = -expected.get(quotient_column, 0)
            for pivot, coefficient in integer_b:
                value += coefficient * transition[pivot][quotient_column]
            value %= prime
            residual.append(value)
            bt_mismatches += int(value != 0)
        bt_stream.add([row_index, residual])
    if bt_mismatches:
        raise AssertionError(f"B*T=C mismatch at p{prime}")

    ppos = {column: index for index, column in enumerate(pivots)}
    spos = {column: index for index, column in enumerate(complement)}
    annihilation_stream = CanonicalListHasher()
    annihilation_mismatches = 0
    for row_index, row in enumerate(restricted):
        pentries, sentries = [], {}
        for column, coefficient in row:
            if column in ppos:
                pentries.append((ppos[column], coefficient))
            else:
                sentries[spos[column]] = coefficient % prime
        residual = []
        for quotient_column in range(QUOTIENT_COUNT):
            value = sentries.get(quotient_column, 0)
            for pivot, coefficient in pentries:
                value -= coefficient * transition[pivot][quotient_column]
            value %= prime
            residual.append(value)
            annihilation_mismatches += int(value != 0)
        annihilation_stream.add([row_index, residual])
    if annihilation_mismatches:
        raise AssertionError(f"quotient annihilation mismatch at p{prime}")

    return transition, {
        "rank": len(basis_b),
        "fixed_minor_shape": [KOSZUL_COUNT, KOSZUL_COUNT],
        "right_hand_side_count": QUOTIENT_COUNT,
        "incremental_pivot_columns_in_B_indexing_sha256": canonical_hash(discovered),
        "incremental_pivot_column_set_complete": set(discovered) == set(range(KOSZUL_COUNT)),
        "elimination_reduction_count": reductions,
        "elimination_B_coefficient_update_count": b_updates,
        "elimination_C_coefficient_update_count": c_updates,
        "maximum_working_B_support": max_b_support,
        "maximum_working_C_support": max_c_support,
        "back_substitution_coefficient_update_count": back_updates,
        "transition_nonzero_count": sum(value != 0 for row in transition for value in row),
        "transition_matrix_row_major_sha256": canonical_hash(transition),
        "BT_equals_C_replay": {
            "stream_format": "canonical list of [Koszul-row-index,114-entry residual-vector]",
            "stream_record_count": bt_stream.count,
            "scalar_comparison_count": ENTRY_COUNT,
            "mismatch_count": bt_mismatches,
            "stream_sha256": bt_stream.hexdigest(),
        },
        "koszul_quotient_annihilation_replay": {
            "stream_format": "canonical list of [Koszul-row-index,114-entry q_p(row)-vector]",
            "stream_record_count": annihilation_stream.count,
            "scalar_comparison_count": ENTRY_COUNT,
            "mismatch_count": annihilation_mismatches,
            "stream_sha256": annihilation_stream.hexdigest(),
        },
        "row_or_column_swap_count": 0,
        "adaptive_minor_repair_used": False,
    }


def crt_setup(primes):
    modulus = 1
    stages = []
    for prime in primes:
        stages.append((prime, modulus, pow(modulus % prime, -1, prime)))
        modulus *= prime
    return stages, modulus


def direct_crt(residues, stages):
    value = 0
    for residue, (prime, modulus, inverse) in zip(residues, stages, strict=True):
        value += modulus * (((residue - value) % prime) * inverse % prime)
    return value


def strict_candidates(residue, modulus):
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


def literal_candidates(residue, modulus):
    candidates = set()
    for denominator in range(1, modulus + 1):
        if math.gcd(denominator, modulus) != 1:
            continue
        least = residue * denominator % modulus
        for numerator in (least, least - modulus):
            if (
                math.gcd(abs(numerator), denominator) == 1
                and 2 * abs(numerator) * denominator < modulus
                and (numerator - residue * denominator) % modulus == 0
            ):
                candidates.add((numerator, denominator))
    return sorted(candidates)


def self_test_candidates(started):
    transcript = hashlib.sha256()
    count = 0
    for modulus in range(2, 100):
        for residue in range(modulus):
            observed, _steps = strict_candidates(residue, modulus)
            expected = literal_candidates(residue, modulus)
            if observed != expected:
                raise AssertionError(f"candidate self-test mismatch at {residue} mod {modulus}")
            transcript.update(f"{modulus}:{residue}:{observed}\n".encode("ascii"))
            count += 1
        if modulus % 8 == 0:
            guard(started, "small-modulus literal candidate self-test")
    return {
        "modulus_range_inclusive": [2, 99],
        "residue_modulus_pairs_tested": count,
        "transcript_sha256": transcript.hexdigest(),
        "all_sets_equal": True,
    }


def m70_census(transitions, started):
    stages, modulus = crt_setup(SOURCE_PRIMES)
    if modulus != SOURCE_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("source modulus changed")
    outcomes = collections.Counter()
    candidate_histogram = collections.Counter()
    survivor_histogram = collections.Counter()
    eea_histogram = collections.Counter()
    product_bit_histogram = collections.Counter()
    joint_height_histogram = collections.Counter()
    selector_totals = collections.Counter()
    total_candidates = total_survivors = total_steps = maximum_steps = 0
    maximum_numerator = maximum_denominator = maximum_product = None
    combined_stream = CanonicalListHasher()
    candidate_stream = CanonicalListHasher()
    candidate_count_stream = CanonicalListHasher()
    eea_stream = CanonicalListHasher()
    outcome_stream = CanonicalListHasher()
    survivor_stream = CanonicalListHasher()
    height_stream = CanonicalListHasher()

    for row_index in range(KOSZUL_COUNT):
        for quotient_column in range(QUOTIENT_COUNT):
            entry = row_index * QUOTIENT_COUNT + quotient_column
            combined = direct_crt(
                [transitions[p][row_index][quotient_column] for p in SOURCE_PRIMES],
                stages,
            )
            candidates, steps = strict_candidates(combined, modulus)
            combined_stream.add(str(combined))
            candidate_stream.add(
                [entry, [[str(n), str(d)] for n, d in candidates]]
            )
            candidate_count_stream.add(len(candidates))
            eea_stream.add(steps)
            candidate_histogram[len(candidates)] += 1
            eea_histogram[steps] += 1
            total_candidates += len(candidates)
            total_steps += steps
            maximum_steps = max(maximum_steps, steps)

            survivors = candidates
            for selector in SELECTOR_PRIMES:
                observed = transitions[selector][row_index][quotient_column]
                survivors = [
                    (n, d)
                    for n, d in survivors
                    if d % selector
                    and n % selector * pow(d % selector, -1, selector) % selector
                    == observed
                ]
                selector_totals[selector] += len(survivors)
            survivor_histogram[len(survivors)] += 1
            total_survivors += len(survivors)
            survivor_stream.add([entry, [[str(n), str(d)] for n, d in survivors]])
            if not survivors:
                label = "no_candidate"
            elif len(survivors) > 1:
                label = "ambiguous"
            else:
                label = "unique_zero" if survivors[0][0] == 0 else "unique_nonzero"
            outcomes[label] += 1
            outcome_stream.add([entry, label])

            for numerator, denominator in survivors:
                absolute = abs(numerator)
                product = 2 * absolute * denominator
                nbits, dbits, pbits = absolute.bit_length(), denominator.bit_length(), product.bit_length()
                product_bit_histogram[pbits] += 1
                joint_height_histogram[(nbits, dbits, pbits)] += 1
                height_stream.add(
                    [entry, str(numerator), str(denominator), nbits, dbits, str(product), pbits]
                )
                nrank = (absolute, entry, numerator, denominator)
                drank = (denominator, entry, numerator)
                prank = (product, entry, numerator, denominator)
                if maximum_numerator is None or nrank > maximum_numerator[0]:
                    maximum_numerator = (
                        nrank,
                        {"entry_index": entry, "transition_row": row_index,
                         "quotient_column": quotient_column, "numerator": str(numerator),
                         "absolute_numerator": str(absolute), "denominator": str(denominator)},
                    )
                if maximum_denominator is None or drank > maximum_denominator[0]:
                    maximum_denominator = (
                        drank,
                        {"entry_index": entry, "transition_row": row_index,
                         "quotient_column": quotient_column, "numerator": str(numerator),
                         "denominator": str(denominator)},
                    )
                if maximum_product is None or prank > maximum_product[0]:
                    maximum_product = (
                        prank,
                        {"entry_index": entry, "transition_row": row_index,
                         "quotient_column": quotient_column, "numerator": str(numerator),
                         "denominator": str(denominator), "twice_absolute_product": str(product),
                         "twice_absolute_product_bit_length": pbits},
                    )
        if row_index % 64 == 0:
            guard(started, "complete 234042-entry M70 census")

    normalized = {
        label: outcomes[label]
        for label in ("no_candidate", "unique_zero", "unique_nonzero", "ambiguous")
    }
    if sum(normalized.values()) != ENTRY_COUNT:
        raise AssertionError("M70 classification count changed")
    value_u = normalized["no_candidate"] + normalized["ambiguous"]
    if value_u == 0:
        band = "decisive_quotient_height_signal"
        next_route = "freeze; exact QQ assembly and coefficientwise B*T=C replay require a separate preregistration"
    elif value_u <= 54616:
        band = "strong_but_incomplete_signal"
        next_route = "freeze; at most one separately preregistered two-prime extension may be considered"
    elif value_u <= 109233:
        band = "intermediate_signal"
        next_route = "freeze; add no primes automatically and prefer a direct p-adic or exact rational target solve"
    else:
        band = "route_stop"
        next_route = "add no primes and do not alter P; move to a direct exact rational solve or separately posed integer-lattice question"
    height_records = [
        [[a, b, c], count]
        for (a, b, c), count in sorted(joint_height_histogram.items())
    ]
    return {
        "entry_order": "row-major over 2053 transition rows then 114 quotient columns",
        "entry_count": ENTRY_COUNT,
        "source_characteristics": list(SOURCE_PRIMES),
        "selector_characteristics": list(SELECTOR_PRIMES),
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "strict_product_inequality": "2*abs(n)*d < M",
        "outcome": normalized,
        "U_no_candidate_plus_ambiguous": value_u,
        "interpretation_band": band,
        "next_route": next_route,
        "enumeration": {
            "total_candidates_before_selectors": total_candidates,
            "total_extended_euclid_steps": total_steps,
            "maximum_extended_euclid_steps_per_entry": maximum_steps,
            "candidate_count_histogram": {
                str(k): v for k, v in sorted(candidate_histogram.items())
            },
            "extended_euclid_step_histogram": {
                str(k): v for k, v in sorted(eea_histogram.items())
            },
            "selector_survivor_totals": {
                str(p): selector_totals[p] for p in SELECTOR_PRIMES
            },
            "final_survivor_count": total_survivors,
            "final_survivor_count_histogram": {
                str(k): v for k, v in sorted(survivor_histogram.items())
            },
        },
        "height": {
            "maximum_surviving_absolute_numerator": None if maximum_numerator is None else maximum_numerator[1],
            "maximum_surviving_denominator": None if maximum_denominator is None else maximum_denominator[1],
            "maximum_surviving_twice_absolute_product": None if maximum_product is None else maximum_product[1],
            "surviving_product_bit_length_histogram": {
                str(k): v for k, v in sorted(product_bit_histogram.items())
            },
            "joint_numerator_denominator_product_bit_length_histogram": {
                f"{a},{b},{c}": count
                for (a, b, c), count in sorted(joint_height_histogram.items())
            },
        },
        "hashes": {
            "combined_CRT_residue_stream_sha256": combined_stream.hexdigest(),
            "complete_preselector_candidate_stream_sha256": candidate_stream.hexdigest(),
            "candidate_count_stream_sha256": candidate_count_stream.hexdigest(),
            "extended_euclid_step_stream_sha256": eea_stream.hexdigest(),
            "complete_outcome_stream_sha256": outcome_stream.hexdigest(),
            "complete_surviving_candidate_stream_sha256": survivor_stream.hexdigest(),
            "complete_surviving_height_record_stream_sha256": height_stream.hexdigest(),
            "height_histogram_stream_sha256": canonical_hash(height_records),
        },
        "stream_serialization": "each stream hash is SHA-256 of its declared compact canonical JSON list",
        "rational_assembly_performed": False,
    }


def compare_payloads(campaign, free, bindings, restricted, absolute_to_local, pivots,
                     pivot_telemetry, complement, b_rows, c_rows, transitions,
                     prime_records, census):
    artifact = json.loads((campaign / ARTIFACT_PATH).read_text(encoding="utf-8"))
    receipt = json.loads((campaign / PRODUCER_RECEIPT_PATH).read_text(encoding="utf-8"))
    restricted_decimal = [[[column, str(value)] for column, value in row] for row in restricted]
    b_decimal = [[[column, str(value)] for column, value in row] for row in b_rows]
    c_decimal = [[[column, str(value)] for column, value in row] for row in c_rows]
    local_map = {str(absolute): local for absolute, local in absolute_to_local.items()}
    pivot_absolute = [free[column] for column in pivots]
    complement_absolute = [free[column] for column in complement]
    dimensions = {
        "full_multiplier_coordinate_count": FULL_COUNT,
        "free_coordinate_count": FREE_COUNT,
        "integer_koszul_row_count": KOSZUL_COUNT,
        "integer_koszul_full_nonzero_count": 154939,
        "restricted_K_F_shape": [KOSZUL_COUNT, FREE_COUNT],
        "restricted_K_F_nonzero_count": sum(map(len, restricted)),
        "B_shape": [KOSZUL_COUNT, KOSZUL_COUNT],
        "B_nonzero_count": sum(map(len, b_rows)),
        "C_shape": [KOSZUL_COUNT, QUOTIENT_COUNT],
        "C_nonzero_count": sum(map(len, c_rows)),
        "quotient_coordinate_count": QUOTIENT_COUNT,
        "transition_shape_each_prime": [KOSZUL_COUNT, QUOTIENT_COUNT],
        "transition_entry_count_each_prime": ENTRY_COUNT,
    }
    artifact_hashes = {
        "source_script_sha256": PRODUCER_HASH,
        "frozen_input_file_sha256": PRODUCER_FROZEN_HASHES,
        "descriptor_stream_sha256": DESCRIPTOR_HASH,
        "integer_koszul_content_invariant_stream_sha256": KOSZUL_HASH,
        "ordered_free_absolute_coordinates_sha256": canonical_hash(free),
        "absolute_to_local_map_sha256": canonical_hash(local_map),
        "restricted_K_F_sparse_integer_rows_sha256": canonical_hash(restricted_decimal),
        "ordered_pivot_local_coordinates_sha256": canonical_hash(pivots),
        "ordered_pivot_absolute_coordinates_sha256": canonical_hash(pivot_absolute),
        "ordered_complement_local_coordinates_sha256": canonical_hash(complement),
        "ordered_complement_absolute_coordinates_sha256": canonical_hash(complement_absolute),
        "B_sparse_integer_rows_sha256": canonical_hash(b_decimal),
        "C_sparse_integer_rows_sha256": canonical_hash(c_decimal),
        "transition_matrix_row_major_sha256": {
            str(p): prime_records[str(p)]["transition_matrix_row_major_sha256"] for p in PRIMES
        },
        "quotient_annihilation_replay_stream_sha256": {
            str(p): prime_records[str(p)]["koszul_quotient_annihilation_replay"]["stream_sha256"]
            for p in PRIMES
        },
    }
    checks = {
        "all_five_source_vectors_zero_on_all_2167_free_coordinates": True,
        "no_identity_height_improvement_reported": True,
        "all_2053_restricted_rows_nonempty": True,
        "p181_lexicographic_rank_equals_2053": len(pivots) == KOSZUL_COUNT,
        "complement_dimension_equals_114": len(complement) == QUOTIENT_COUNT,
        "same_B_rank_equals_2053_at_all_five_primes": all(
            prime_records[str(p)]["rank"] == KOSZUL_COUNT for p in PRIMES
        ),
        "all_five_BT_equals_C_replays_pass": all(
            prime_records[str(p)]["BT_equals_C_replay"]["mismatch_count"] == 0 for p in PRIMES
        ),
        "all_five_quotient_annihilation_replays_pass": all(
            prime_records[str(p)]["koszul_quotient_annihilation_replay"]["mismatch_count"] == 0
            for p in PRIMES
        ),
        "no_minor_repair_or_column_swap": True,
        "zero_process_swap_gate_at_structural_freeze": True,
    }
    expected_artifact = {
        "schema": "hc4.third-colon-residual-114-quotient-chart.v1",
        "status": "PASS_FIVE_FIBRE_COMMON_RESIDUAL_114_QUOTIENT_CHART",
        "assurance": "bounded exact modular quotient-transition structure only",
        "claim_boundary": (
            "This artifact proves only that the displayed five finite-field fibres share one explicit 114-coordinate quotient chart for the separately verified 2053-row Koszul subspace. It does not prove characteristic-zero quotient-kernel dimension 114, construct residual rational syzygies, improve or reconstruct a target multiplier, prove QQ membership, compute a colon or saturation, close a secant chart, establish nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": PREREG_PATH,
            "preregistration_sha256": PREREG_HASH,
            "characteristics_in_frozen_order": list(PRIMES),
            "pivot_selection_characteristic": 181,
            "fixed_minor_reused_without_change_at_all_primes": True,
            "alternative_minor_prime_gauge_or_matching_used": False,
            "source_vectors_transformed": False,
        },
        "dimensions": dimensions,
        "ordered_free_absolute_coordinates": free,
        "absolute_to_local_map": local_map,
        "ordered_pivot_local_coordinates_discovery_order": pivots,
        "ordered_pivot_absolute_coordinates_discovery_order": pivot_absolute,
        "ordered_complement_local_coordinates_increasing": complement,
        "ordered_complement_absolute_coordinates": complement_absolute,
        "restricted_K_F_sparse_integer_rows": restricted_decimal,
        "B_sparse_integer_rows": b_decimal,
        "C_sparse_integer_rows": c_decimal,
        "source_zero_free_coordinate_checks": bindings,
        "p181_pivot_selection": pivot_telemetry,
        "prime_records": {
            str(p): {**prime_records[str(p)], "transition_matrix_row_major": transitions[p]}
            for p in PRIMES
        },
        "hashes": artifact_hashes,
        "checks": checks,
    }
    observed_artifact = {
        key: value
        for key, value in artifact.items()
        if key not in {"created_at_utc", "resources_at_structural_freeze", "timings"}
    }
    if expected_artifact != observed_artifact:
        bad = sorted(
            key for key in set(expected_artifact) | set(observed_artifact)
            if expected_artifact.get(key) != observed_artifact.get(key)
        )
        raise AssertionError(f"producer artifact deterministic payload mismatch: {bad}")
    aresources = artifact.get("resources_at_structural_freeze", {})
    if (
        int(aresources.get("initial_process_swaps", -1)) != 0
        or int(aresources.get("current_process_swaps", -1)) != 0
        or int(aresources.get("process_swap_delta", -1)) != 0
        or int(aresources.get("maximum_rss_native", RSS_CAP_BYTES)) >= RSS_CAP_BYTES
        or float(aresources.get("elapsed_wall_seconds", WALL_CAP_SECONDS)) >= WALL_CAP_SECONDS
    ):
        raise AssertionError("producer structural resource gate failed")

    band = census["interpretation_band"]
    status = {
        "decisive_quotient_height_signal": "PASS_DECISIVE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "strong_but_incomplete_signal": "PASS_STRONG_INCOMPLETE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "intermediate_signal": "PASS_INTERMEDIATE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "route_stop": "PASS_STRUCTURAL_CHART_ROUTE_STOP_QUOTIENT_HEIGHT_CENSUS",
    }[band]
    expected_receipt = {
        "schema": "hc4.third-colon-residual-114-quotient-scout.v1",
        "status": status,
        "assurance": "bounded exact five-fibre quotient structure and strict-product M70 transition-height census only",
        "claim_boundary": (
            "This receipt reports a five-fibre 114-coordinate quotient chart for the separately verified Koszul subspace and a bounded strict-product height census of its transition matrices. It does not establish characteristic-zero quotient-kernel dimension 114, construct residual rational syzygies, assemble a QQ quotient chart or target multiplier, prove QQ membership, compute a colon or saturation, establish residual dimension 114, close a secant chart, prove nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": PREREG_PATH,
            "preregistration_sha256": PREREG_HASH,
            "source_script_path": PRODUCER_PATH,
            "source_script_sha256": PRODUCER_HASH,
            "one_algebra_process": True,
            "new_prime_minor_gauge_or_pivot_repair_used": False,
            "full_vector_M70_census_performed": False,
            "target_multiplier_entries_opened_by_phase_2": False,
        },
        "retrospective_feasibility_disclosure": {
            "preregistration_disclosed_unretained_calibration": "fewer than ten thousand restricted nonzeros and five modular rank checks completing in seconds",
            "calibration_used_as_acceptance_evidence": False,
            "pivot_lists_transition_values_transition_hashes_and_all_M70_outcomes": "prospective when first serialized by this producer",
        },
        "structural_artifact": {
            "path": ARTIFACT_PATH,
            "sha256": ARTIFACT_HASH,
            "byte_count": (campaign / ARTIFACT_PATH).stat().st_size,
            "status": artifact["status"],
            "dimensions": dimensions,
            "hashes": artifact_hashes,
            "p181_pivot_selection": pivot_telemetry,
            "prime_telemetry": {
                str(p): prime_records[str(p)] for p in PRIMES
            },
            "source_zero_free_coordinate_checks": bindings,
        },
        "M70_transition_height_census": census,
        "interpretation": {
            "U": census["U_no_candidate_plus_ambiguous"],
            "band": band,
            "next_route": census["next_route"],
            "numerical_threshold_is_route_selection_not_significance_test": True,
        },
        "checks": {
            "structural_artifact_frozen_before_phase_2": True,
            "all_phase_1_checks_pass": True,
            "all_234042_transition_entries_classified": True,
            "M70_uses_only_transition_entries": True,
            "no_QQ_assembly_or_target_membership_replay": True,
            "zero_process_swap_gate": True,
        },
    }
    observed_receipt = {
        key: value
        for key, value in receipt.items()
        if key not in {"created_at_utc", "resources", "timings"}
    }
    if expected_receipt != observed_receipt:
        bad = sorted(
            key for key in set(expected_receipt) | set(observed_receipt)
            if expected_receipt.get(key) != observed_receipt.get(key)
        )
        raise AssertionError(f"producer receipt deterministic payload mismatch: {bad}")
    resources = receipt.get("resources", {})
    timings = receipt.get("timings", {})
    if (
        int(resources.get("initial_process_swaps", -1)) != 0
        or int(resources.get("final_process_swaps", -1)) != 0
        or int(resources.get("process_swap_delta", -1)) != 0
        or int(resources.get("maximum_rss_native", RSS_CAP_BYTES)) >= RSS_CAP_BYTES
        or float(timings.get("total_wall_seconds", WALL_CAP_SECONDS)) >= WALL_CAP_SECONDS
    ):
        raise AssertionError("producer final resource gate failed")
    return artifact, receipt, dimensions, artifact_hashes


def run(campaign: Path, script_path: Path, started: float):
    rows = reconstruct_koszul(campaign, started)
    free, bindings = load_free_sources(campaign)
    restricted, absolute_to_local = restrict_rows(rows, free)
    pivots, pivot_telemetry = select_p181_pivots(restricted, started)
    if len(pivots) != KOSZUL_COUNT or len(set(pivots)) != KOSZUL_COUNT:
        raise AssertionError("p181 pivot count changed")
    complement = sorted(set(range(FREE_COUNT)) - set(pivots))
    if len(complement) != QUOTIENT_COUNT:
        raise AssertionError("quotient complement count changed")
    b_rows, c_rows = split_matrices(restricted, pivots, complement)
    transitions, prime_records = {}, {}
    for prime in PRIMES:
        transition, record = solve_transition(
            prime, b_rows, c_rows, restricted, pivots, complement, started
        )
        transitions[prime] = transition
        prime_records[str(prime)] = record
        guard(started, f"complete five-prime transition replay p{prime}")
    brute_force = self_test_candidates(started)
    census = m70_census(transitions, started)
    artifact, producer_receipt, dimensions, artifact_hashes = compare_payloads(
        campaign, free, bindings, restricted, absolute_to_local, pivots,
        pivot_telemetry, complement, b_rows, c_rows, transitions, prime_records, census
    )
    guard(started, "complete producer payload comparison")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.third-colon-residual-114-quotient-independent-audit.v1",
        "status": "PASS_INDEPENDENT_RESIDUAL_114_QUOTIENT_AND_M70_REPLAY",
        "producer_status": producer_receipt["status"],
        "assurance": "independent exact reconstruction of the five-fibre quotient chart and complete transition-entry M70 census",
        "claim_boundary": (
            "This PASS establishes only independent reproducibility of the displayed five finite-field quotient chart for the verified Koszul subspace and its bounded strict-product transition-height census. It does not prove characteristic-zero quotient-kernel dimension 114, construct residual rational syzygies, assemble a QQ quotient chart or target multiplier, provide a target-height improvement, prove QQ membership, compute a colon or saturation, close the secant chart, establish nullcone containment, or prove HC4."
        ),
        "independence_boundary": {
            "producer_imported_or_executed": False,
            "producer_helpers_imported": False,
            "integer_K_reconstructed_from_frozen_rational_generators": True,
            "p181_pivot_chart_reconstructed": True,
            "all_five_fixed_B_solves_and_direct_replays_reconstructed": True,
            "complete_234042_entry_M70_census_reconstructed": True,
            "QQ_or_target_multiplier_entries_opened": False,
        },
        "dimensions": dimensions,
        "hashes": {
            "independent_source_sha256": file_hash(script_path),
            "preregistration_sha256": PREREG_HASH,
            "producer_source_sha256": PRODUCER_HASH,
            "producer_artifact_sha256": ARTIFACT_HASH,
            "producer_receipt_sha256": PRODUCER_RECEIPT_HASH,
            "integer_koszul_stream_sha256": KOSZUL_HASH,
            "ordered_free_coordinates_sha256": canonical_hash(free),
            "ordered_pivot_local_coordinates_sha256": canonical_hash(pivots),
            "ordered_complement_local_coordinates_sha256": canonical_hash(complement),
            "restricted_K_F_sha256": artifact_hashes["restricted_K_F_sparse_integer_rows_sha256"],
            "B_sha256": artifact_hashes["B_sparse_integer_rows_sha256"],
            "C_sha256": artifact_hashes["C_sparse_integer_rows_sha256"],
            "transition_matrix_row_major_sha256": artifact_hashes["transition_matrix_row_major_sha256"],
            "quotient_annihilation_replay_stream_sha256": artifact_hashes["quotient_annihilation_replay_stream_sha256"],
        },
        "prime_replay": {
            str(prime): {
                "rank": prime_records[str(prime)]["rank"],
                "transition_nonzero_count": prime_records[str(prime)]["transition_nonzero_count"],
                "transition_matrix_row_major_sha256": prime_records[str(prime)]["transition_matrix_row_major_sha256"],
                "BT_equals_C_replay": prime_records[str(prime)]["BT_equals_C_replay"],
                "koszul_quotient_annihilation_replay": prime_records[str(prime)]["koszul_quotient_annihilation_replay"],
            }
            for prime in PRIMES
        },
        "candidate_enumerator_brute_force_check": brute_force,
        "M70_transition_height_census": census,
        "comparisons": {
            "producer_artifact_deterministic_payload_exact": True,
            "producer_receipt_deterministic_payload_exact": True,
            "producer_nondeterministic_metadata_resource_validated": True,
            "all_transition_matrices_exact": True,
            "all_M70_classifications_and_canonical_stream_hashes_exact": True,
            "no_output_overwrite": True,
        },
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "required_initial_process_swaps": 0,
            "required_final_process_swaps": 0,
            "initial_process_swaps": 0,
            "final_process_swaps": process_swaps(),
            "total_wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_rss_bytes(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }
    guard(started, "independent PASS receipt freeze")
    return result


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / OUTPUT_PATH
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("300-second independent wall alarm")),
    )
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        if process_swaps() != 0:
            raise MemoryError(f"nonzero initial process swaps: {process_swaps()}")
        if output.exists():
            raise FileExistsError(f"independent output already exists: {output}")
        result = run(campaign, script_path, started)
        write_new_json(output, result)
        print(json.dumps({
            "status": result["status"],
            "producer_status": result["producer_status"],
            "output": str(output),
            "U": result["M70_transition_height_census"]["U_no_candidate_plus_ambiguous"],
            "wall_seconds": result["resources"]["total_wall_seconds"],
            "maximum_rss_native": result["resources"]["maximum_rss_native"],
        }, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-residual-114-quotient-independent-audit-failure.v1",
            "status": "FAIL_CLOSED_INDEPENDENT_RESIDUAL_114_QUOTIENT_AUDIT",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No characteristic-zero quotient dimension, rational syzygy, QQ chart, target multiplier or height, colon, saturation, secant-chart, nullcone, or HC4 conclusion is licensed by this failure.",
            "source_sha256": file_hash(script_path),
            "producer_artifact_sha256": ARTIFACT_HASH,
            "producer_receipt_sha256": PRODUCER_RECEIPT_HASH,
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_rss_bytes(),
            "initial_process_swaps_required": 0,
            "final_process_swaps": process_swaps(),
        }
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        failure_path = campaign / "receipts" / f"{FAILURE_PREFIX}-{stamp}.json"
        write_new_json(failure_path, failure)
        print(json.dumps({**failure, "receipt": str(failure_path)}, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
