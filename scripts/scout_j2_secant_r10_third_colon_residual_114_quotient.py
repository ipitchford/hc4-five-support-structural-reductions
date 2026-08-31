#!/usr/bin/env sage-python
"""Frozen residual-114 quotient-chart and bounded transition-height scout.

This producer constructs only the quotient of the frozen 2,167-coordinate
free space by the independently verified 2,053-row integer Koszul subspace.
It does not construct residual syzygies or a characteristic-zero multiplier.
"""

from __future__ import annotations

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
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIMES = (181, 173, 197, 2147483647, 2147483629)
SOURCE_PRIMES = (181, 2147483647, 2147483629)
SELECTOR_PRIMES = (173, 197)
SOURCE_MODULUS = 834715161561466408303
FULL_COORDINATE_COUNT = 38048
FREE_COUNT = 2167
KOSZUL_COUNT = 2053
QUOTIENT_COUNT = 114
TRANSITION_ENTRY_COUNT = KOSZUL_COUNT * QUOTIENT_COUNT
WALL_CAP_SECONDS = 300.0
RSS_CAP_BYTES = 1_500_000_000

PREREGISTRATION = "research/THIRD_COLON_RESIDUAL_114_QUOTIENT_SCOUT_PREREGISTRATION.md"
PREREGISTRATION_HASH = "112fb4ea3de68c84459422903e0c6f3c4c2902d364b13639f130c2a7f6cebf22"
FREE_HASH = "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
INTEGER_KOSZUL_STREAM_HASH = "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856"

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
FROZEN_HASHES = {
    PREREGISTRATION: PREREGISTRATION_HASH,
    **{SOURCE_ARTIFACTS[p]: SOURCE_HASHES[p] for p in PRIMES},
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout.json": "6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json": "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout.py": "39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py": "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
}

ARTIFACT_RELATIVE = "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
RECEIPT_RELATIVE = "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json"
FAILURE_PREFIX = "hsop-j2-secant-r10-third-colon-residual-114-quotient-scout-failed"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


class CanonicalListHasher:
    """Incremental SHA-256 of one compact canonical JSON list."""

    def __init__(self) -> None:
        self._hasher = hashlib.sha256()
        self._hasher.update(b"[")
        self._first = True
        self.count = 0

    def add(self, value: object) -> None:
        if not self._first:
            self._hasher.update(b",")
        self._hasher.update(canonical_bytes(value))
        self._first = False
        self.count += 1

    def hexdigest(self) -> str:
        clone = self._hasher.copy()
        clone.update(b"]")
        return clone.hexdigest()


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def guard(started: float, initial_swaps: int, stage: str) -> None:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    rss = native_max_rss_bytes()
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if rss >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {rss} bytes")
    if initial_swaps != 0 or int(usage.ru_nswap) != 0:
        raise MemoryError(f"process swap count is nonzero during {stage}")


def write_new_json(path: Path, payload: object, *, compact: bool = False) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen output: {path}")
    if compact:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="ascii") as handle:
        handle.write(text)


def failure_path(campaign: Path, phase: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return campaign / "receipts" / f"{FAILURE_PREFIX}-{phase}-{stamp}.json"


def validate_frozen_inputs(campaign: Path) -> None:
    for relative, expected in FROZEN_HASHES.items():
        path = campaign / relative
        observed = sha256_bytes(path.read_bytes())
        if observed != expected:
            raise ValueError(f"frozen input hash changed: {relative}: {observed}")
    reference = json.loads(
        (campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        reference.get("status")
        != "PASS_INDEPENDENT_CONTENT_INVARIANT_2053_KOSZUL_SYZYGIES_AND_RANK"
        or reference.get("dimensions", {}).get("koszul_column_count") != KOSZUL_COUNT
        or reference.get("dimensions", {}).get("koszul_nonzero_count") != 154939
        or reference.get("hashes", {}).get("descriptor_stream_sha256") != DESCRIPTOR_HASH
        or reference.get("hashes", {}).get("primitive_column_stream_sha256")
        != INTEGER_KOSZUL_STREAM_HASH
    ):
        raise ValueError("independent Koszul audit is not the frozen passing evidence")


def load_zero_free_sources(campaign: Path):
    bindings = {}
    free_reference = None
    for prime in PRIMES:
        relative = SOURCE_ARTIFACTS[prime]
        payload = json.loads((campaign / relative).read_text(encoding="utf-8"))
        if int(payload.get("characteristic", -1)) != prime:
            raise ValueError(f"source characteristic changed at p{prime}")
        vector = list(map(int, payload.get("coordinate_vector", [])))
        free = list(map(int, payload.get("free_unknown_indices", [])))
        if (
            len(vector) != FULL_COORDINATE_COUNT
            or canonical_hash(vector) != payload.get("coordinate_vector_sha256")
            or len(free) != FREE_COUNT
            or free != sorted(free)
            or len(set(free)) != FREE_COUNT
            or canonical_hash(free) != FREE_HASH
            or payload.get("free_unknown_indices_sha256") != FREE_HASH
        ):
            raise ValueError(f"malformed vector or free-coordinate gauge at p{prime}")
        if any(value < 0 or value >= prime for value in vector):
            raise ValueError(f"source coefficient outside GF(p) at p{prime}")
        if free_reference is None:
            free_reference = free
        elif free != free_reference:
            raise ValueError(f"ordered free-coordinate list changed at p{prime}")
        restriction = [vector[coordinate] for coordinate in free]
        nonzero_coordinates = [free[i] for i, value in enumerate(restriction) if value]
        if nonzero_coordinates:
            raise ValueError(f"source vector is nonzero on F at p{prime}")
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
        raise AssertionError("no source gauge loaded")
    return free_reference, bindings


def reconstruct_koszul(campaign: Path, started: float, initial_swaps: int):
    sys.path.insert(0, str(campaign / "scripts"))
    import audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit as ind
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading, _open_factor = homogeneous_saturation_system()
    if len(equations) != 17 or len(variables) != 18:
        raise ValueError("frozen cubic system dimensions changed")
    cubic_terms = []
    cubic_expressions = []
    for equation in equations:
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
            for exponents, coefficient in polynomial.terms()
        ]
        if {sum(exponents) for exponents, _coefficient in terms} != {3}:
            raise ValueError("cubic grading changed")
        cubic_terms.append(terms)
        cubic_expressions.append(sp.expand(equation))
    h_terms, h_expression = ind.artifact_terms(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms",
        variables,
        189,
        4,
    )
    h2_terms, h2_expression = ind.artifact_terms(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms",
        variables,
        211,
        3,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = cubic_expressions + [h_expression, h2_expression]
    degrees = [3] * 17 + [4, 4]
    characters = []
    for terms in generator_terms:
        observed = {ind.character(exponents) for exponents, _coefficient in terms}
        if len(observed) != 1:
            raise ValueError("generator character changed")
        characters.append(next(iter(observed)))
    if ind.expression_hash(generator_expressions) != GENERATOR_HASH:
        raise ValueError("generator expression stream changed")

    pools = {}
    for degree in (4, 5):
        for monomial in ind.exponent_tuples(18, degree):
            pools.setdefault((degree, ind.character(monomial)), []).append(monomial)
    descriptors = []
    for generator_index, (degree, character) in enumerate(zip(degrees, characters, strict=True)):
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(8 - degree, (3 - character) % 12)]
        )
    if len(descriptors) != FULL_COORDINATE_COUNT or canonical_hash(descriptors) != DESCRIPTOR_HASH:
        raise ValueError("descriptor stream changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}

    rows = []
    stream = hashlib.sha256()
    pair_counts = collections.Counter()
    for left in range(19):
        for right in range(left + 1, 19):
            residual_degree = 8 - degrees[left] - degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (3 - characters[left] - characters[right]) % 12
            for residual in ind.exponent_tuples(18, residual_degree):
                if ind.character(residual) != residual_character:
                    continue
                row = ind.primitive_column(
                    left, right, residual, generator_terms, descriptor_index
                )
                rows.append(row)
                ind.framed_update(stream, [[coordinate, str(value)] for coordinate, value in row])
                pair_counts[(degrees[left], degrees[right])] += 1
        guard(started, initial_swaps, "integer Koszul reconstruction")
    if (
        len(rows) != KOSZUL_COUNT
        or sum(map(len, rows)) != 154939
        or pair_counts != collections.Counter({(3, 3): 1993, (3, 4): 60})
        or stream.hexdigest() != INTEGER_KOSZUL_STREAM_HASH
    ):
        raise ValueError("integer Koszul reconstruction changed")
    return rows


def restrict_koszul(rows, free):
    absolute_to_local = {absolute: local for local, absolute in enumerate(free)}
    restricted = []
    for row_index, row in enumerate(rows):
        local_row = tuple(
            (absolute_to_local[absolute], value)
            for absolute, value in row
            if absolute in absolute_to_local
        )
        if not local_row:
            raise ValueError(f"empty restricted Koszul row {row_index}")
        if tuple(sorted(local_row)) != local_row:
            raise AssertionError("restricted row order changed")
        restricted.append(local_row)
    return restricted, absolute_to_local


def select_lexicographic_p181_pivots(rows, started, initial_swaps):
    prime = 181
    basis = {}
    pivots = []
    reductions = 0
    coefficient_updates = 0
    maximum_working_support = 0
    basis_nonzeros = 0
    for row_index, integer_row in enumerate(rows):
        work = {coordinate: value % prime for coordinate, value in integer_row if value % prime}
        maximum_working_support = max(maximum_working_support, len(work))
        while work:
            coordinate = min(work)
            if coordinate not in basis:
                break
            factor = work[coordinate]
            pivot_row = basis[coordinate]
            reductions += 1
            for column, value in pivot_row.items():
                updated = (work.get(column, 0) - factor * value) % prime
                if updated:
                    work[column] = updated
                else:
                    work.pop(column, None)
                coefficient_updates += 1
            maximum_working_support = max(maximum_working_support, len(work))
        if not work:
            raise ValueError(f"p181 restricted rank stopped before row {row_index}")
        pivot = min(work)
        if pivot in basis:
            raise AssertionError("lexicographic pivot collision")
        inverse = pow(work[pivot], -1, prime)
        normalized = {column: value * inverse % prime for column, value in work.items()}
        if normalized[pivot] != 1 or min(normalized) != pivot:
            raise AssertionError("p181 basis normalization failed")
        basis[pivot] = normalized
        pivots.append(pivot)
        basis_nonzeros += len(normalized)
        if row_index % 128 == 0:
            guard(started, initial_swaps, "p181 lexicographic pivot selection")
    return pivots, {
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


def split_integer_matrices(rows, pivots, complement):
    pivot_position = {coordinate: index for index, coordinate in enumerate(pivots)}
    complement_position = {coordinate: index for index, coordinate in enumerate(complement)}
    b_rows = []
    c_rows = []
    for row in rows:
        b_row = []
        c_row = []
        for coordinate, value in row:
            if coordinate in pivot_position:
                b_row.append((pivot_position[coordinate], value))
            else:
                c_row.append((complement_position[coordinate], value))
        b_rows.append(tuple(sorted(b_row)))
        c_rows.append(tuple(sorted(c_row)))
    return b_rows, c_rows


def solve_transition(prime, b_rows, c_rows, restricted_rows, pivots, complement, started, initial_swaps):
    basis_b = {}
    basis_c = {}
    reductions = 0
    b_updates = 0
    c_updates = 0
    max_b_support = 0
    max_c_support = 0
    discovered_columns = []
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
            raise ValueError(f"fixed B is singular modulo {prime} at row {row_index}")
        pivot_column = min(work_b)
        inverse = pow(work_b[pivot_column], -1, prime)
        normalized_b = {
            column: value * inverse % prime for column, value in work_b.items()
        }
        normalized_c = {
            column: value * inverse % prime for column, value in work_c.items()
        }
        if normalized_b[pivot_column] != 1 or min(normalized_b) != pivot_column:
            raise AssertionError(f"modular solve normalization failed at p{prime}")
        basis_b[pivot_column] = normalized_b
        basis_c[pivot_column] = normalized_c
        discovered_columns.append(pivot_column)
        if row_index % 128 == 0:
            guard(started, initial_swaps, f"fixed-B elimination modulo {prime}")

    rank = len(basis_b)
    if rank != KOSZUL_COUNT or set(basis_b) != set(range(KOSZUL_COUNT)):
        raise ValueError(f"fixed B rank below {KOSZUL_COUNT} modulo {prime}")

    transition = [None] * KOSZUL_COUNT
    back_substitution_updates = 0
    for pivot_column in range(KOSZUL_COUNT - 1, -1, -1):
        result = [0] * QUOTIENT_COUNT
        for column, value in basis_c[pivot_column].items():
            result[column] = value
        for later_column, coefficient in basis_b[pivot_column].items():
            if later_column == pivot_column:
                continue
            if later_column < pivot_column or transition[later_column] is None:
                raise AssertionError(f"non-echelon fixed-B basis modulo {prime}")
            later = transition[later_column]
            for quotient_column in range(QUOTIENT_COUNT):
                result[quotient_column] = (
                    result[quotient_column] - coefficient * later[quotient_column]
                ) % prime
                back_substitution_updates += 1
        transition[pivot_column] = result
        if pivot_column % 128 == 0:
            guard(started, initial_swaps, f"fixed-B back substitution modulo {prime}")

    bt_replay = CanonicalListHasher()
    bt_mismatches = 0
    for row_index, (integer_b, integer_c) in enumerate(zip(b_rows, c_rows, strict=True)):
        expected = {column: value % prime for column, value in integer_c if value % prime}
        residual = []
        for quotient_column in range(QUOTIENT_COUNT):
            value = -expected.get(quotient_column, 0)
            for pivot_column, coefficient in integer_b:
                value += coefficient * transition[pivot_column][quotient_column]
            value %= prime
            residual.append(value)
            bt_mismatches += int(value != 0)
        bt_replay.add([row_index, residual])
    if bt_mismatches:
        raise AssertionError(f"B*T=C replay failed modulo {prime}: {bt_mismatches}")

    pivot_position = {coordinate: index for index, coordinate in enumerate(pivots)}
    complement_position = {coordinate: index for index, coordinate in enumerate(complement)}
    annihilation_replay = CanonicalListHasher()
    annihilation_mismatches = 0
    for row_index, row in enumerate(restricted_rows):
        pivot_entries = []
        complement_entries = {}
        for coordinate, coefficient in row:
            if coordinate in pivot_position:
                pivot_entries.append((pivot_position[coordinate], coefficient))
            else:
                complement_entries[complement_position[coordinate]] = coefficient % prime
        residual = []
        for quotient_column in range(QUOTIENT_COUNT):
            value = complement_entries.get(quotient_column, 0)
            for pivot_column, coefficient in pivot_entries:
                value -= coefficient * transition[pivot_column][quotient_column]
            value %= prime
            residual.append(value)
            annihilation_mismatches += int(value != 0)
        annihilation_replay.add([row_index, residual])
    if annihilation_mismatches:
        raise AssertionError(
            f"Koszul quotient-annihilation replay failed modulo {prime}: {annihilation_mismatches}"
        )

    transition_nonzeros = sum(value != 0 for row in transition for value in row)
    return transition, {
        "rank": rank,
        "fixed_minor_shape": [KOSZUL_COUNT, KOSZUL_COUNT],
        "right_hand_side_count": QUOTIENT_COUNT,
        "incremental_pivot_columns_in_B_indexing_sha256": canonical_hash(discovered_columns),
        "incremental_pivot_column_set_complete": set(discovered_columns) == set(range(KOSZUL_COUNT)),
        "elimination_reduction_count": reductions,
        "elimination_B_coefficient_update_count": b_updates,
        "elimination_C_coefficient_update_count": c_updates,
        "maximum_working_B_support": max_b_support,
        "maximum_working_C_support": max_c_support,
        "back_substitution_coefficient_update_count": back_substitution_updates,
        "transition_nonzero_count": transition_nonzeros,
        "transition_matrix_row_major_sha256": canonical_hash(transition),
        "BT_equals_C_replay": {
            "stream_format": "canonical list of [Koszul-row-index,114-entry residual-vector]",
            "stream_record_count": bt_replay.count,
            "scalar_comparison_count": TRANSITION_ENTRY_COUNT,
            "mismatch_count": bt_mismatches,
            "stream_sha256": bt_replay.hexdigest(),
        },
        "koszul_quotient_annihilation_replay": {
            "stream_format": "canonical list of [Koszul-row-index,114-entry q_p(row)-vector]",
            "stream_record_count": annihilation_replay.count,
            "scalar_comparison_count": TRANSITION_ENTRY_COUNT,
            "mismatch_count": annihilation_mismatches,
            "stream_sha256": annihilation_replay.hexdigest(),
        },
        "row_or_column_swap_count": 0,
        "adaptive_minor_repair_used": False,
    }


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


def m70_census(transitions, started, initial_swaps):
    stages, modulus = crt_setup(SOURCE_PRIMES)
    if modulus != SOURCE_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("frozen M70 modulus changed")

    outcomes = collections.Counter()
    candidate_histogram = collections.Counter()
    survivor_histogram = collections.Counter()
    eea_histogram = collections.Counter()
    product_bit_histogram = collections.Counter()
    joint_height_histogram = collections.Counter()
    selector_survivor_totals = collections.Counter()
    total_candidates = 0
    total_survivors = 0
    total_eea_steps = 0
    maximum_eea_steps = 0
    maximum_abs_numerator = None
    maximum_denominator = None
    maximum_product = None

    combined_stream = CanonicalListHasher()
    candidate_stream = CanonicalListHasher()
    candidate_count_stream = CanonicalListHasher()
    eea_step_stream = CanonicalListHasher()
    outcome_stream = CanonicalListHasher()
    survivor_stream = CanonicalListHasher()
    height_record_stream = CanonicalListHasher()

    for row_index in range(KOSZUL_COUNT):
        for quotient_column in range(QUOTIENT_COUNT):
            entry_index = row_index * QUOTIENT_COUNT + quotient_column
            source_residues = [
                transitions[prime][row_index][quotient_column] for prime in SOURCE_PRIMES
            ]
            combined = crt(source_residues, stages)
            candidates, steps = strict_product_candidates(combined, modulus)
            combined_stream.add(str(combined))
            candidate_stream.add(
                [entry_index, [[str(numerator), str(denominator)] for numerator, denominator in candidates]]
            )
            candidate_count_stream.add(len(candidates))
            eea_step_stream.add(steps)
            candidate_histogram[len(candidates)] += 1
            eea_histogram[steps] += 1
            total_candidates += len(candidates)
            total_eea_steps += steps
            maximum_eea_steps = max(maximum_eea_steps, steps)

            survivors = candidates
            for selector in SELECTOR_PRIMES:
                observed = transitions[selector][row_index][quotient_column]
                survivors = [
                    (numerator, denominator)
                    for numerator, denominator in survivors
                    if denominator % selector
                    and numerator % selector * pow(denominator % selector, -1, selector) % selector
                    == observed
                ]
                selector_survivor_totals[selector] += len(survivors)

            survivor_histogram[len(survivors)] += 1
            total_survivors += len(survivors)
            survivor_stream.add(
                [entry_index, [[str(numerator), str(denominator)] for numerator, denominator in survivors]]
            )
            if not survivors:
                label = "no_candidate"
            elif len(survivors) > 1:
                label = "ambiguous"
            else:
                label = "unique_zero" if survivors[0][0] == 0 else "unique_nonzero"
            outcomes[label] += 1
            outcome_stream.add([entry_index, label])

            for numerator, denominator in survivors:
                abs_numerator = abs(numerator)
                product = 2 * abs_numerator * denominator
                numerator_bits = abs_numerator.bit_length()
                denominator_bits = denominator.bit_length()
                product_bits = product.bit_length()
                product_bit_histogram[product_bits] += 1
                joint_height_histogram[(numerator_bits, denominator_bits, product_bits)] += 1
                height_record_stream.add(
                    [
                        entry_index,
                        str(numerator),
                        str(denominator),
                        numerator_bits,
                        denominator_bits,
                        str(product),
                        product_bits,
                    ]
                )
                numerator_rank = (abs_numerator, entry_index, numerator, denominator)
                denominator_rank = (denominator, entry_index, numerator)
                product_rank = (product, entry_index, numerator, denominator)
                if maximum_abs_numerator is None or numerator_rank > maximum_abs_numerator[0]:
                    maximum_abs_numerator = (
                        numerator_rank,
                        {
                            "entry_index": entry_index,
                            "transition_row": row_index,
                            "quotient_column": quotient_column,
                            "numerator": str(numerator),
                            "absolute_numerator": str(abs_numerator),
                            "denominator": str(denominator),
                        },
                    )
                if maximum_denominator is None or denominator_rank > maximum_denominator[0]:
                    maximum_denominator = (
                        denominator_rank,
                        {
                            "entry_index": entry_index,
                            "transition_row": row_index,
                            "quotient_column": quotient_column,
                            "numerator": str(numerator),
                            "denominator": str(denominator),
                        },
                    )
                if maximum_product is None or product_rank > maximum_product[0]:
                    maximum_product = (
                        product_rank,
                        {
                            "entry_index": entry_index,
                            "transition_row": row_index,
                            "quotient_column": quotient_column,
                            "numerator": str(numerator),
                            "denominator": str(denominator),
                            "twice_absolute_product": str(product),
                            "twice_absolute_product_bit_length": product_bits,
                        },
                    )
        if row_index % 64 == 0:
            guard(started, initial_swaps, "M70 quotient-transition census")

    normalized_outcomes = {
        label: outcomes[label]
        for label in ("no_candidate", "unique_zero", "unique_nonzero", "ambiguous")
    }
    if sum(normalized_outcomes.values()) != TRANSITION_ENTRY_COUNT:
        raise AssertionError("M70 outcomes do not cover all transition entries")
    height_histogram_records = [
        [[numerator_bits, denominator_bits, product_bits], count]
        for (numerator_bits, denominator_bits, product_bits), count in sorted(
            joint_height_histogram.items()
        )
    ]
    value_u = normalized_outcomes["no_candidate"] + normalized_outcomes["ambiguous"]
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

    return {
        "entry_order": "row-major over 2053 transition rows then 114 quotient columns",
        "entry_count": TRANSITION_ENTRY_COUNT,
        "source_characteristics": list(SOURCE_PRIMES),
        "selector_characteristics": list(SELECTOR_PRIMES),
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "strict_product_inequality": "2*abs(n)*d < M",
        "outcome": normalized_outcomes,
        "U_no_candidate_plus_ambiguous": value_u,
        "interpretation_band": band,
        "next_route": next_route,
        "enumeration": {
            "total_candidates_before_selectors": total_candidates,
            "total_extended_euclid_steps": total_eea_steps,
            "maximum_extended_euclid_steps_per_entry": maximum_eea_steps,
            "candidate_count_histogram": {
                str(key): value for key, value in sorted(candidate_histogram.items())
            },
            "extended_euclid_step_histogram": {
                str(key): value for key, value in sorted(eea_histogram.items())
            },
            "selector_survivor_totals": {
                str(prime): selector_survivor_totals[prime] for prime in SELECTOR_PRIMES
            },
            "final_survivor_count": total_survivors,
            "final_survivor_count_histogram": {
                str(key): value for key, value in sorted(survivor_histogram.items())
            },
        },
        "height": {
            "maximum_surviving_absolute_numerator": None
            if maximum_abs_numerator is None
            else maximum_abs_numerator[1],
            "maximum_surviving_denominator": None
            if maximum_denominator is None
            else maximum_denominator[1],
            "maximum_surviving_twice_absolute_product": None
            if maximum_product is None
            else maximum_product[1],
            "surviving_product_bit_length_histogram": {
                str(key): value for key, value in sorted(product_bit_histogram.items())
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
            "extended_euclid_step_stream_sha256": eea_step_stream.hexdigest(),
            "complete_outcome_stream_sha256": outcome_stream.hexdigest(),
            "complete_surviving_candidate_stream_sha256": survivor_stream.hexdigest(),
            "complete_surviving_height_record_stream_sha256": height_record_stream.hexdigest(),
            "height_histogram_stream_sha256": canonical_hash(height_histogram_records),
        },
        "stream_serialization": "each stream hash is SHA-256 of its declared compact canonical JSON list",
        "rational_assembly_performed": False,
    }


def build_structural_artifact(campaign: Path, script_path: Path, started: float, initial_swaps: int):
    validate_frozen_inputs(campaign)
    guard(started, initial_swaps, "frozen input validation")
    free, source_bindings = load_zero_free_sources(campaign)
    guard(started, initial_swaps, "zero-free source validation")
    integer_koszul = reconstruct_koszul(campaign, started, initial_swaps)
    restricted, absolute_to_local = restrict_koszul(integer_koszul, free)
    restricted_nonzeros = sum(map(len, restricted))
    pivots, pivot_telemetry = select_lexicographic_p181_pivots(
        restricted, started, initial_swaps
    )
    if len(pivots) != KOSZUL_COUNT or len(set(pivots)) != KOSZUL_COUNT:
        raise ValueError("p181 lexicographic restricted rank is not 2053")
    complement = sorted(set(range(FREE_COUNT)) - set(pivots))
    if len(complement) != QUOTIENT_COUNT:
        raise ValueError("free-coordinate complement does not have dimension 114")
    b_rows, c_rows = split_integer_matrices(restricted, pivots, complement)
    b_nonzeros = sum(map(len, b_rows))
    c_nonzeros = sum(map(len, c_rows))
    if b_nonzeros + c_nonzeros != restricted_nonzeros:
        raise AssertionError("B/C split lost a restricted integer coefficient")

    transitions = {}
    prime_records = {}
    solve_started = time.perf_counter()
    for prime in PRIMES:
        transition, telemetry = solve_transition(
            prime,
            b_rows,
            c_rows,
            restricted,
            pivots,
            complement,
            started,
            initial_swaps,
        )
        transitions[prime] = transition
        prime_records[str(prime)] = {
            **telemetry,
            "transition_matrix_row_major": transition,
        }
        gc.collect()
        guard(started, initial_swaps, f"completed quotient chart modulo {prime}")
    solve_seconds = time.perf_counter() - solve_started
    if not all(record["rank"] == KOSZUL_COUNT for record in prime_records.values()):
        raise ValueError("same fixed B is not full rank at every admitted prime")

    restricted_decimal = [
        [[column, str(value)] for column, value in row] for row in restricted
    ]
    b_decimal = [[[column, str(value)] for column, value in row] for row in b_rows]
    c_decimal = [[[column, str(value)] for column, value in row] for row in c_rows]
    absolute_to_local_serialized = {
        str(absolute): local for absolute, local in absolute_to_local.items()
    }
    pivot_absolute = [free[coordinate] for coordinate in pivots]
    complement_absolute = [free[coordinate] for coordinate in complement]
    usage = resource.getrusage(resource.RUSAGE_SELF)
    artifact = {
        "schema": "hc4.third-colon-residual-114-quotient-chart.v1",
        "status": "PASS_FIVE_FIBRE_COMMON_RESIDUAL_114_QUOTIENT_CHART",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "bounded exact modular quotient-transition structure only",
        "claim_boundary": (
            "This artifact proves only that the displayed five finite-field fibres share one explicit 114-coordinate quotient chart for the separately verified 2053-row Koszul subspace. It does not prove characteristic-zero quotient-kernel dimension 114, construct residual rational syzygies, improve or reconstruct a target multiplier, prove QQ membership, compute a colon or saturation, close a secant chart, establish nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": PREREGISTRATION,
            "preregistration_sha256": PREREGISTRATION_HASH,
            "characteristics_in_frozen_order": list(PRIMES),
            "pivot_selection_characteristic": 181,
            "fixed_minor_reused_without_change_at_all_primes": True,
            "alternative_minor_prime_gauge_or_matching_used": False,
            "source_vectors_transformed": False,
        },
        "dimensions": {
            "full_multiplier_coordinate_count": FULL_COORDINATE_COUNT,
            "free_coordinate_count": len(free),
            "integer_koszul_row_count": len(integer_koszul),
            "integer_koszul_full_nonzero_count": sum(map(len, integer_koszul)),
            "restricted_K_F_shape": [len(restricted), len(free)],
            "restricted_K_F_nonzero_count": restricted_nonzeros,
            "B_shape": [len(b_rows), len(pivots)],
            "B_nonzero_count": b_nonzeros,
            "C_shape": [len(c_rows), len(complement)],
            "C_nonzero_count": c_nonzeros,
            "quotient_coordinate_count": len(complement),
            "transition_shape_each_prime": [KOSZUL_COUNT, QUOTIENT_COUNT],
            "transition_entry_count_each_prime": TRANSITION_ENTRY_COUNT,
        },
        "ordered_free_absolute_coordinates": free,
        "absolute_to_local_map": absolute_to_local_serialized,
        "ordered_pivot_local_coordinates_discovery_order": pivots,
        "ordered_pivot_absolute_coordinates_discovery_order": pivot_absolute,
        "ordered_complement_local_coordinates_increasing": complement,
        "ordered_complement_absolute_coordinates": complement_absolute,
        "restricted_K_F_sparse_integer_rows": restricted_decimal,
        "B_sparse_integer_rows": b_decimal,
        "C_sparse_integer_rows": c_decimal,
        "source_zero_free_coordinate_checks": source_bindings,
        "p181_pivot_selection": pivot_telemetry,
        "prime_records": prime_records,
        "hashes": {
            "source_script_sha256": sha256_bytes(script_path.read_bytes()),
            "frozen_input_file_sha256": FROZEN_HASHES,
            "descriptor_stream_sha256": DESCRIPTOR_HASH,
            "integer_koszul_content_invariant_stream_sha256": INTEGER_KOSZUL_STREAM_HASH,
            "ordered_free_absolute_coordinates_sha256": canonical_hash(free),
            "absolute_to_local_map_sha256": canonical_hash(absolute_to_local_serialized),
            "restricted_K_F_sparse_integer_rows_sha256": canonical_hash(restricted_decimal),
            "ordered_pivot_local_coordinates_sha256": canonical_hash(pivots),
            "ordered_pivot_absolute_coordinates_sha256": canonical_hash(pivot_absolute),
            "ordered_complement_local_coordinates_sha256": canonical_hash(complement),
            "ordered_complement_absolute_coordinates_sha256": canonical_hash(complement_absolute),
            "B_sparse_integer_rows_sha256": canonical_hash(b_decimal),
            "C_sparse_integer_rows_sha256": canonical_hash(c_decimal),
            "transition_matrix_row_major_sha256": {
                str(prime): prime_records[str(prime)]["transition_matrix_row_major_sha256"]
                for prime in PRIMES
            },
            "quotient_annihilation_replay_stream_sha256": {
                str(prime): prime_records[str(prime)]["koszul_quotient_annihilation_replay"]["stream_sha256"]
                for prime in PRIMES
            },
        },
        "checks": {
            "all_five_source_vectors_zero_on_all_2167_free_coordinates": all(
                record["free_coordinate_restriction_nonzero_count"] == 0
                for record in source_bindings.values()
            ),
            "no_identity_height_improvement_reported": True,
            "all_2053_restricted_rows_nonempty": len(restricted) == KOSZUL_COUNT,
            "p181_lexicographic_rank_equals_2053": len(pivots) == KOSZUL_COUNT,
            "complement_dimension_equals_114": len(complement) == QUOTIENT_COUNT,
            "same_B_rank_equals_2053_at_all_five_primes": all(
                record["rank"] == KOSZUL_COUNT for record in prime_records.values()
            ),
            "all_five_BT_equals_C_replays_pass": all(
                record["BT_equals_C_replay"]["mismatch_count"] == 0
                for record in prime_records.values()
            ),
            "all_five_quotient_annihilation_replays_pass": all(
                record["koszul_quotient_annihilation_replay"]["mismatch_count"] == 0
                for record in prime_records.values()
            ),
            "no_minor_repair_or_column_swap": True,
            "zero_process_swap_gate_at_structural_freeze": initial_swaps == 0
            and int(usage.ru_nswap) == 0,
        },
        "resources_at_structural_freeze": {
            "wall_cap_seconds_total": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "elapsed_wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "initial_process_swaps": initial_swaps,
            "current_process_swaps": int(usage.ru_nswap),
            "process_swap_delta": int(usage.ru_nswap) - initial_swaps,
        },
        "timings": {
            "five_prime_solve_and_replay_seconds": solve_seconds,
        },
    }
    return artifact, transitions


def run(campaign: Path, script_path: Path, started: float, initial_swaps: int):
    artifact_path = campaign / ARTIFACT_RELATIVE
    receipt_path = campaign / RECEIPT_RELATIVE
    if artifact_path.exists() or receipt_path.exists():
        raise FileExistsError("declared quotient scout output already exists; refusing overwrite")

    phase1_started = time.perf_counter()
    artifact, transitions = build_structural_artifact(
        campaign, script_path, started, initial_swaps
    )
    guard(started, initial_swaps, "Phase 1 structural gates before freeze")
    write_new_json(artifact_path, artifact, compact=True)
    artifact_hash = sha256_bytes(artifact_path.read_bytes())
    phase1_seconds = time.perf_counter() - phase1_started
    guard(started, initial_swaps, "Phase 1 structural artifact freeze")

    phase2_started = time.perf_counter()
    census = m70_census(transitions, started, initial_swaps)
    phase2_seconds = time.perf_counter() - phase2_started
    guard(started, initial_swaps, "Phase 2 M70 census")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    final_swaps = int(usage.ru_nswap)
    if initial_swaps != 0 or final_swaps != 0:
        raise MemoryError("process swap count is nonzero before final receipt freeze")
    if native_max_rss_bytes() >= RSS_CAP_BYTES:
        raise MemoryError("RSS cap reached before final receipt freeze")

    band = census["interpretation_band"]
    status = {
        "decisive_quotient_height_signal": "PASS_DECISIVE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "strong_but_incomplete_signal": "PASS_STRONG_INCOMPLETE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "intermediate_signal": "PASS_INTERMEDIATE_RESIDUAL_114_QUOTIENT_HEIGHT_SIGNAL",
        "route_stop": "PASS_STRUCTURAL_CHART_ROUTE_STOP_QUOTIENT_HEIGHT_CENSUS",
    }[band]
    receipt = {
        "schema": "hc4.third-colon-residual-114-quotient-scout.v1",
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "bounded exact five-fibre quotient structure and strict-product M70 transition-height census only",
        "claim_boundary": (
            "This receipt reports a five-fibre 114-coordinate quotient chart for the separately verified Koszul subspace and a bounded strict-product height census of its transition matrices. It does not establish characteristic-zero quotient-kernel dimension 114, construct residual rational syzygies, assemble a QQ quotient chart or target multiplier, prove QQ membership, compute a colon or saturation, establish residual dimension 114, close a secant chart, prove nullcone containment, or prove HC4."
        ),
        "protocol": {
            "preregistration_path": PREREGISTRATION,
            "preregistration_sha256": PREREGISTRATION_HASH,
            "source_script_path": str(script_path.relative_to(campaign)),
            "source_script_sha256": sha256_bytes(script_path.read_bytes()),
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
            "path": ARTIFACT_RELATIVE,
            "sha256": artifact_hash,
            "byte_count": artifact_path.stat().st_size,
            "status": artifact["status"],
            "dimensions": artifact["dimensions"],
            "hashes": artifact["hashes"],
            "p181_pivot_selection": artifact["p181_pivot_selection"],
            "prime_telemetry": {
                str(prime): {
                    key: value
                    for key, value in artifact["prime_records"][str(prime)].items()
                    if key != "transition_matrix_row_major"
                }
                for prime in PRIMES
            },
            "source_zero_free_coordinate_checks": artifact[
                "source_zero_free_coordinate_checks"
            ],
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
            "all_phase_1_checks_pass": all(artifact["checks"].values()),
            "all_234042_transition_entries_classified": sum(census["outcome"].values())
            == TRANSITION_ENTRY_COUNT,
            "M70_uses_only_transition_entries": True,
            "no_QQ_assembly_or_target_membership_replay": True,
            "zero_process_swap_gate": initial_swaps == 0 and final_swaps == 0,
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
            "phase_1_structural_seconds": phase1_seconds,
            "phase_2_M70_census_seconds": phase2_seconds,
            "total_wall_seconds": time.perf_counter() - started,
        },
    }
    write_new_json(receipt_path, receipt, compact=False)
    return receipt_path, receipt


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(
            TimeoutError("300-second preregistered wall alarm")
        ),
    )
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    phase = "phase1"
    try:
        if initial_swaps != 0:
            raise MemoryError("initial process swap count is nonzero")
        artifact_path = campaign / ARTIFACT_RELATIVE
        phase = "phase1"
        receipt_path, receipt = run(campaign, script_path, started, initial_swaps)
        phase = "complete"
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "receipt": str(receipt_path),
                    "artifact": str(artifact_path),
                    "U": receipt["interpretation"]["U"],
                    "band": receipt["interpretation"]["band"],
                    "wall_seconds": receipt["timings"]["total_wall_seconds"],
                    "maximum_rss_native": receipt["resources"]["maximum_rss_native"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        artifact_path = campaign / ARTIFACT_RELATIVE
        phase = "phase2" if artifact_path.exists() else "phase1"
        failure = {
            "schema": "hc4.third-colon-residual-114-quotient-scout-failure.v1",
            "status": "FAIL_CLOSED_RESIDUAL_114_QUOTIENT_SCOUT",
            "failed_phase": phase,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": (
                "No characteristic-zero quotient dimension, residual syzygy, QQ quotient chart, target multiplier, QQ membership, colon, saturation, secant-chart, nullcone, or HC4 conclusion is licensed by this failure."
            ),
            "preregistration_sha256": PREREGISTRATION_HASH,
            "source_script_sha256": sha256_bytes(script_path.read_bytes()),
            "structural_artifact_retained": None
            if not artifact_path.exists()
            else {
                "path": ARTIFACT_RELATIVE,
                "sha256": sha256_bytes(artifact_path.read_bytes()),
                "byte_count": artifact_path.stat().st_size,
            },
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swap_delta": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
            - initial_swaps,
        }
        path = failure_path(campaign, phase)
        write_new_json(path, failure, compact=False)
        print(json.dumps({**failure, "receipt": str(path)}, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
