#!/usr/bin/env sage-python
"""Independent audit of the p197 common-minor Koszul experiment.

This implementation does not import or execute the common-minor producer, the
stopped p181-minor normalizer, or their helper functions.  It reconstructs the
integer Koszul matrix from frozen rational algebra, reloads the target-blind
p197 coordinate list from the frozen full-rank audit, and independently
replays normalization, modular identities, the primary M70 census, and the
one-way fresh-prime audit.

The producer adapter near ``load_producer_bundle`` is the only schema-coupled
section.  All algebra, rank, solve, CRT, EEA, brute-force, classification, and
audit logic is local to this file.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import platform
import resource
import signal
import sys
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIMARY_PRIMES = (181, 173, 197, 2147483647, 2147483629)
SOURCE_PRIMES = (181, 2147483647, 2147483629)
SELECTOR_PRIMES = (173, 197)
AUDIT_PRIME = 2147482867
ALL_PRIMES = PRIMARY_PRIMES + (AUDIT_PRIME,)
TARGET_DEGREE = 8
TARGET_CHARACTER = 3
CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
WALL_CAP_SECONDS = 240.0
RSS_CAP_BYTES = 1_500_000_000
EXPECTED_COORDINATE_COUNT = 38048
EXPECTED_KOSZUL_COUNT = 2053
EXPECTED_KOSZUL_NNZ = 154939
EXPECTED_DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
EXPECTED_GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
EXPECTED_TARGET_HASH = "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
EXPECTED_KOSZUL_CONTENT_HASH = "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856"
EXPECTED_R197_HASH = "dfb318fa370a3bc01bf4013d760c8ffdfff61c695caeee2ec7151f91dd212164"
EXPECTED_FREE_HASH = "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
EXPECTED_MODULUS = 834715161561466408303
NORMALIZATION_PRODUCER_PATH = "scripts/normalize_j2_secant_r10_third_colon_koszul_p197_common_minor.py"
EXPECTED_NORMALIZATION_PRODUCER_HASH = "fdbed62134385b5412474cd40e70e25a69eea9c5284a6a06dc99ecc121c4d57e"
EXPECTED_NORMALIZATION_RECEIPT_HASH = "3c2f2ac3b2a0c98bb279e90a1fffe8aea68f8c8c4db85e15ced673d50648946e"
CENSUS_PRODUCER_PATH = "scripts/census_j2_secant_r10_third_colon_koszul_p197_common_minor_m70.py"
EXPECTED_CENSUS_PRODUCER_HASH = "6c09d24f9ef3962b1d677c38b34521be20fb4fb3f13dd34c12f270920beccb44"
CENSUS_RECEIPT_PATH = "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-m70-census.json"
EXPECTED_CENSUS_RECEIPT_HASH = "7bb84b8e56df2e68fc4989cf22fc538d8660a5888d7ed0a6eac692512e69367c"
EXPECTED_PRIMARY_COMMITMENT_HASH = "251d387e4d641ae995fd9b95758e78b0fa28db4e3792685ef0be65c25d3d8a85"
EXPECTED_AUDIT_REJECTED_COORDINATES = (7651, 9478, 11678, 15642, 27227, 27928, 29343, 30173)
EXPECTED_NORMALIZED_ARTIFACT_HASHES = {
    173: "385449532e894e3e745f6a7755df7c6313b41416c5d198cfe59d8bc945b25ea9",
    181: "03e8e2ea2c9530890387ecf6861c0cd254ade1ae0618af723be5c79a60f7c41e",
    197: "488b086aa9a1909484c7480e20439ab06b135c4d7ea896b12dc704814417fada",
    2147482867: "9947bcb94ea15ba67e7e67b2a6694b64896d621a584ddd5384cb9cead2e9d2bb",
    2147483629: "81d8e3699876829dd99b435cf0617c220e186c1890702128d560aacae9c440b3",
    2147483647: "9c5043ac740db09da3127aebaeeb52317bdfe334229e7833bd77452cad04d0ab",
}

FROZEN_HASHES = {
    "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md": "b203a118b302c50394a0188501e32d12cc077c85fca2b1513bed770f59a112f8",
    "research/THIRD_COLON_KOSZUL_FULL_RANK_MODULAR_AUDIT_REGISTRATION.md": "86843c6d3a525087c4d940f9004fb0bac7176b1f1ec07720a48231285a69a614",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-full-rank-modular-audit.json": "86598ea5b5df670017d0d104978f5c8db7eef6f9313b3aac511f0ea6a5ad4dc2",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
}

PRIMARY_SOURCE_SPECS = {
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

AUDIT_SOURCE_PATHS = (
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867.json",
    "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867.json",
)
AUDIT_SOURCE_HASHES = {
    "artifact_sha256": "101c4679e8c0512ccc00682107283c9add82a019476ab5a7bf9e586b41c9512f",
    "receipt_sha256": "fb306ea450ffa84942ae7cc6a231c5c680664cdd6f6933f78e5369022d808277",
    "telemetry_path": "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867-telemetry.json",
    "telemetry_sha256": "c0034711d93855a51abef069b31751a545bac2c8e8adec2b5c60137fdf37be1a",
}


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def framed_update(hasher, value: object) -> None:
    payload = canonical_bytes(value)
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def expression_hash(expressions) -> str:
    payload = "\n".join(str(sp.expand(item)).replace("**", "^") for item in expressions)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def native_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def process_swaps() -> int:
    return int(getattr(resource.getrusage(resource.RUSAGE_SELF), "ru_nswap", 0))


def guard(started: float, stage: str) -> None:
    wall = time.perf_counter() - started
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if native_rss_bytes() >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {native_rss_bytes()}")
    if process_swaps():
        raise MemoryError(f"process swaps observed during {stage}: {process_swaps()}")


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


def rational_terms(expression, variables):
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return [
        (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
        for exponents, coefficient in polynomial.terms()
    ]


def load_quartic(path, key, variables, expected_count, expected_character):
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
        raise AssertionError("Koszul row is not primitive")
    return tuple(sorted(integral.items()))


def exact_sparse_image(row, descriptors, generator_terms):
    accumulator = {}
    for coordinate, scalar in row:
        generator_index, multiplier = descriptors[coordinate]
        for exponents, coefficient in generator_terms[generator_index]:
            monomial = add_exponents(multiplier, exponents)
            updated = accumulator.get(monomial, Fraction(0)) + scalar * coefficient
            if updated:
                accumulator[monomial] = updated
            else:
                accumulator.pop(monomial, None)
    return accumulator


def modular_image(vector, descriptors, generator_terms, prime):
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
            monomial = add_exponents(multiplier, exponents)
            updated = (accumulator.get(monomial, 0) + delta) % prime
            if updated:
                accumulator[monomial] = updated
            else:
                accumulator.pop(monomial, None)
    return accumulator


def modular_target(target_terms, prime):
    output = {}
    for exponents, coefficient in target_terms:
        denominator = coefficient.denominator % prime
        if not denominator:
            raise ZeroDivisionError(f"target denominator vanishes modulo {prime}")
        value = coefficient.numerator % prime * pow(denominator, -1, prime) % prime
        if value:
            output[exponents] = value
    return output


def reconstruct_algebra(campaign: Path, started: float):
    for relative, expected in FROZEN_HASHES.items():
        if file_sha256(campaign / relative) != expected:
            raise ValueError(f"frozen input changed: {relative}")

    sys.path.insert(0, str(campaign / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    cubics, variables, _leading_form, open_factor = homogeneous_saturation_system()
    if len(cubics) != 17 or len(variables) != 18:
        raise ValueError("cubic system dimensions changed")
    cubic_expressions = [sp.expand(item) for item in cubics]
    cubic_terms = [rational_terms(item, variables) for item in cubics]
    h_terms, h = load_quartic(
        campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4,
    )
    h2_terms, h2 = load_quartic(
        campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 3,
    )
    _h3_terms, h3 = load_quartic(
        campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
        "terms", variables, 248, 2,
    )
    generators = cubic_expressions + [h, h2]
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_degrees = [3] * 17 + [4, 4]
    generator_characters = []
    for terms, degree in zip(generator_terms, generator_degrees, strict=True):
        if {sum(exponents) for exponents, _ in terms} != {degree}:
            raise ValueError("generator degree changed")
        weights = {character(exponents) for exponents, _ in terms}
        if len(weights) != 1:
            raise ValueError("generator character changed")
        generator_characters.append(next(iter(weights)))
    if expression_hash(generators) != EXPECTED_GENERATOR_HASH:
        raise ValueError("generator expression hash changed")
    target_expression = sp.expand(open_factor * h3)
    if expression_hash((target_expression,)) != EXPECTED_TARGET_HASH:
        raise ValueError("target expression hash changed")
    target_terms = rational_terms(target_expression, variables)

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
        raise AssertionError("descriptor count changed")
    if canonical_hash(descriptors) != EXPECTED_DESCRIPTOR_HASH:
        raise AssertionError("descriptor stream hash changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}

    columns = []
    primitive_hasher = hashlib.sha256()
    pair_counts = collections.Counter()
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
                row = primitive_koszul_row(
                    left, right, residual, generator_terms, descriptor_index
                )
                if exact_sparse_image(row, descriptors, generator_terms):
                    raise AssertionError("nonzero exact Koszul image")
                columns.append(row)
                framed_update(
                    primitive_hasher,
                    [[coordinate, str(value)] for coordinate, value in row],
                )
                label = (
                    ("cubic" if generator_degrees[left] == 3 else "quartic")
                    + "-"
                    + ("cubic" if generator_degrees[right] == 3 else "quartic")
                )
                pair_counts[label] += 1
                if len(columns) % 64 == 0:
                    guard(started, "independent Koszul reconstruction")
    if (
        len(columns) != EXPECTED_KOSZUL_COUNT
        or sum(map(len, columns)) != EXPECTED_KOSZUL_NNZ
        or dict(pair_counts) != {"cubic-cubic": 1993, "cubic-quartic": 60}
        or primitive_hasher.hexdigest() != EXPECTED_KOSZUL_CONTENT_HASH
    ):
        raise AssertionError("Koszul reconstruction profile changed")

    full_rank_receipt = json.loads(
        (campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-full-rank-modular-audit.json").read_text()
    )
    if full_rank_receipt.get("status") != "PASS_FULL_KOSZUL_RANK_AT_173_181_197":
        raise ValueError("frozen full-rank audit is not PASS")
    r197 = list(
        map(
            int,
            full_rank_receipt["prime_records"]["197"]["custom_rank_telemetry"][
                "pivot_coordinates"
            ],
        )
    )
    if len(r197) != EXPECTED_KOSZUL_COUNT or canonical_hash(r197) != EXPECTED_R197_HASH:
        raise AssertionError("ordered R197 stream changed")
    if len(set(r197)) != len(r197):
        raise AssertionError("R197 repeats a coordinate")

    selected_position = {coordinate: position for position, coordinate in enumerate(r197)}
    minor_entries = []
    for column_index, column in enumerate(columns):
        for coordinate, value in column:
            row_index = selected_position.get(coordinate)
            if row_index is not None:
                minor_entries.append((row_index, column_index, value))
    minor_entries.sort()
    minor_rows = [[] for _ in r197]
    minor_integer_rows = [[] for _ in r197]
    for row, column, value in minor_entries:
        minor_rows[row].append([column, str(value)])
        minor_integer_rows[row].append([column, value])
    guard(started, "R197 and integer minor reconstruction")
    return {
        "variables": variables,
        "descriptors": descriptors,
        "generator_terms": generator_terms,
        "target_terms": target_terms,
        "columns": columns,
        "r197": r197,
        "minor_entries": minor_entries,
        "minor_entry_stream_sha256": canonical_hash(
            [[row, column, str(value)] for row, column, value in minor_entries]
        ),
        "minor_integer_rows_sha256": canonical_hash(minor_integer_rows),
        "minor_sparse_rows_sha256": canonical_hash(minor_rows),
    }


def load_source_identity(campaign, prime, audit_hashes=None):
    if prime in PRIMARY_SOURCE_SPECS:
        artifact_relative, artifact_hash, receipt_relative, receipt_hash = PRIMARY_SOURCE_SPECS[prime]
    else:
        artifact_relative, receipt_relative = AUDIT_SOURCE_PATHS
        artifact_hash = audit_hashes["artifact_sha256"]
        receipt_hash = audit_hashes["receipt_sha256"]
    artifact_path = campaign / artifact_relative
    receipt_path = campaign / receipt_relative
    if file_sha256(artifact_path) != artifact_hash or file_sha256(receipt_path) != receipt_hash:
        raise ValueError(f"source identity hash changed at prime {prime}")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    replay = receipt.get("same_process_sparse_replay", {})
    certificate = receipt.get("certificate", {})
    vector = list(map(int, artifact.get("coordinate_vector", [])))
    free = list(map(int, artifact.get("free_unknown_indices", [])))
    if (
        int(artifact.get("characteristic", -1)) != prime
        or int(receipt.get("characteristic", -1)) != prime
        or receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        or not replay.get("completed")
        or not replay.get("identity_zero")
        or int(replay.get("mismatch_count", -1)) != 0
        or replay.get("first_mismatch") is not None
        or certificate.get("sha256") != artifact_hash
        or len(vector) != EXPECTED_COORDINATE_COUNT
        or any(not 0 <= value < prime for value in vector)
        or canonical_hash(vector) != artifact.get("coordinate_vector_sha256")
        or canonical_hash(free) != artifact.get("free_unknown_indices_sha256")
        or artifact.get("free_unknown_indices_sha256") != EXPECTED_FREE_HASH
        or artifact.get("row_descriptor_sha256") != EXPECTED_DESCRIPTOR_HASH
        or artifact.get("generator_stream_sha256") != EXPECTED_GENERATOR_HASH
        or artifact.get("target_sha256") != EXPECTED_TARGET_HASH
    ):
        raise AssertionError(f"source identity failed validation at prime {prime}")
    return {
        "prime": prime,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_hash,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt_hash,
        "vector": vector,
        "vector_sha256": artifact["coordinate_vector_sha256"],
    }


def sparse_minor_rank_det_solve(reconstruction, prime, rhs_values, started):
    """Local sparse Gaussian solve with determinant and exact rank telemetry."""

    size = EXPECTED_KOSZUL_COUNT
    rows = [dict() for _ in range(size)]
    for row, column, value in reconstruction["minor_entries"]:
        residue = value % prime
        if residue:
            rows[row][column] = residue
    rhs = [value % prime for value in rhs_values]
    initial_nnz = sum(map(len, rows))
    maximum_nnz = initial_nnz
    maximum_row_length = max(map(len, rows))
    coefficient_updates = 0
    row_swaps = 0
    determinant = 1
    for pivot_column in range(size):
        candidates = [
            row_index
            for row_index in range(pivot_column, size)
            if rows[row_index].get(pivot_column, 0)
        ]
        if not candidates:
            raise AssertionError(
                f"common minor singular modulo {prime}: missing pivot column {pivot_column}"
            )
        pivot_row = min(candidates, key=lambda row_index: (len(rows[row_index]), row_index))
        if pivot_row != pivot_column:
            rows[pivot_column], rows[pivot_row] = rows[pivot_row], rows[pivot_column]
            rhs[pivot_column], rhs[pivot_row] = rhs[pivot_row], rhs[pivot_column]
            determinant = -determinant % prime
            row_swaps += 1
        pivot = rows[pivot_column][pivot_column]
        determinant = determinant * pivot % prime
        inverse = pow(pivot, -1, prime)
        rows[pivot_column] = {
            column: value * inverse % prime
            for column, value in rows[pivot_column].items()
        }
        rhs[pivot_column] = rhs[pivot_column] * inverse % prime
        pivot_tail = [
            (column, value)
            for column, value in rows[pivot_column].items()
            if column > pivot_column
        ]
        for row_index in range(pivot_column + 1, size):
            factor = rows[row_index].pop(pivot_column, 0)
            if not factor:
                continue
            row = rows[row_index]
            for column, value in pivot_tail:
                updated = (row.get(column, 0) - factor * value) % prime
                if updated:
                    row[column] = updated
                else:
                    row.pop(column, None)
                coefficient_updates += 1
            rhs[row_index] = (rhs[row_index] - factor * rhs[pivot_column]) % prime
        if pivot_column % 32 == 0:
            current_nnz = sum(map(len, rows))
            maximum_nnz = max(maximum_nnz, current_nnz)
            maximum_row_length = max(maximum_row_length, max(map(len, rows)))
            guard(started, f"sparse rank determinant and solve modulo {prime}")

    alpha = [0] * size
    for row_index in range(size - 1, -1, -1):
        value = rhs[row_index]
        for column, coefficient in rows[row_index].items():
            if column > row_index:
                value -= coefficient * alpha[column]
        alpha[row_index] = value % prime
    replay = [0] * size
    for row, column, value in reconstruction["minor_entries"]:
        replay[row] = (replay[row] + value * alpha[column]) % prime
    if any(
        observed != expected % prime
        for observed, expected in zip(replay, rhs_values, strict=True)
    ):
        raise AssertionError(f"independent modular solve replay failed at prime {prime}")
    guard(started, f"rank determinant and solve modulo {prime}")
    return size, determinant, alpha, {
        "algorithm": "local sparse Gaussian elimination with shortest-row pivoting and back substitution",
        "initial_nonzero_count": initial_nnz,
        "maximum_sampled_nonzero_count": maximum_nnz,
        "maximum_sampled_row_length": maximum_row_length,
        "coefficient_update_count": coefficient_updates,
        "row_swap_count": row_swaps,
    }


def koszul_combination(columns, alpha, prime):
    output = [0] * EXPECTED_COORDINATE_COUNT
    for scalar, column in zip(alpha, columns, strict=True):
        if not scalar:
            continue
        for coordinate, value in column:
            output[coordinate] = (output[coordinate] + scalar * value) % prime
    return output


def verify_one_normalization(reconstruction, source, producer_record, started):
    prime = source["prime"]
    r197 = reconstruction["r197"]
    rhs = [(-source["vector"][coordinate]) % prime for coordinate in r197]
    rank, determinant, alpha, solve_telemetry = sparse_minor_rank_det_solve(
        reconstruction, prime, rhs, started
    )
    combination = koszul_combination(reconstruction["columns"], alpha, prime)
    normalized = [
        (source_value + delta) % prime
        for source_value, delta in zip(source["vector"], combination, strict=True)
    ]
    if any(normalized[coordinate] for coordinate in r197):
        raise AssertionError(f"R197 coordinates did not normalize to zero at prime {prime}")
    if producer_record["alpha"] != alpha:
        raise AssertionError(f"producer alpha mismatch at prime {prime}")
    if producer_record["normalized"] != normalized:
        raise AssertionError(f"producer normalized vector mismatch at prime {prime}")
    if producer_record["difference"] != combination:
        raise AssertionError(f"producer difference vector mismatch at prime {prime}")
    if canonical_hash(alpha) != producer_record["alpha_sha256"]:
        raise AssertionError(f"producer alpha hash mismatch at prime {prime}")
    if canonical_hash(normalized) != producer_record["normalized_sha256"]:
        raise AssertionError(f"producer normalized hash mismatch at prime {prime}")
    if canonical_hash(combination) != producer_record["difference_sha256"]:
        raise AssertionError(f"producer difference hash mismatch at prime {prime}")
    target = modular_target(reconstruction["target_terms"], prime)
    source_image = modular_image(
        source["vector"], reconstruction["descriptors"], reconstruction["generator_terms"], prime
    )
    normalized_image = modular_image(
        normalized, reconstruction["descriptors"], reconstruction["generator_terms"], prime
    )
    if source_image != target or normalized_image != target:
        raise AssertionError(f"direct Macaulay identity replay failed at prime {prime}")
    if int(producer_record["rank"]) != rank or int(producer_record["determinant"]) != determinant:
        raise AssertionError(f"producer rank/determinant mismatch at prime {prime}")
    guard(started, f"complete normalization replay modulo {prime}")
    return {
        "prime": prime,
        "rank": rank,
        "determinant_residue": determinant,
        "minor_nonzero_count": solve_telemetry["initial_nonzero_count"],
        "solve_telemetry": solve_telemetry,
        "source_artifact_sha256": source["artifact_sha256"],
        "alpha_sha256": canonical_hash(alpha),
        "normalized_vector_sha256": canonical_hash(normalized),
        "difference_vector_sha256": canonical_hash(combination),
        "normalized_support_count": sum(bool(value) for value in normalized),
        "direct_source_identity_replay": True,
        "direct_normalized_identity_replay": True,
        "normalized": normalized,
    }


def direct_crt_basis(primes):
    modulus = math.prod(primes)
    weights = []
    for prime in primes:
        partial = modulus // prime
        weights.append(partial * pow(partial % prime, -1, prime))
    if any(
        weight % own != 1
        or any(weight % other for other in primes if other != own)
        for own, weight in zip(primes, weights, strict=True)
    ):
        raise AssertionError("direct CRT basis failed its residue identities")
    return modulus, weights


def direct_crt(residues, weights, modulus):
    return sum(
        residue * weight for residue, weight in zip(residues, weights, strict=True)
    ) % modulus


def ordinary_eea_candidates(residue, modulus):
    """Enumerate strict-product candidates via ordinary Euclidean convergents."""

    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0
    quotients = []
    numerator, denominator = residue, modulus
    while denominator:
        quotient, remainder = divmod(numerator, denominator)
        quotients.append(quotient)
        numerator, denominator = denominator, remainder

    h0, h1 = 0, 1
    k0, k1 = 1, 0
    candidates = set()
    proper_convergents = 0
    for index, quotient in enumerate(quotients):
        h2 = quotient * h1 + h0
        k2 = quotient * k1 + k0
        h0, h1 = h1, h2
        k0, k1 = k1, k2
        if index + 1 == len(quotients):
            break
        proper_convergents += 1
        candidate_numerator = residue * k2 - modulus * h2
        candidate_denominator = k2
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
    return sorted(candidates), proper_convergents


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


def candidate_enumerator_self_test(started):
    transcript = hashlib.sha256()
    tested = 0
    for modulus in range(2, 100):
        for residue in range(modulus):
            observed, _steps = ordinary_eea_candidates(residue, modulus)
            expected = literal_candidates(residue, modulus)
            if observed != expected:
                raise AssertionError(
                    f"EEA/brute-force mismatch at modulus={modulus}, residue={residue}"
                )
            transcript.update(f"{modulus}:{residue}:{observed}\n".encode("ascii"))
            tested += 1
        if modulus % 8 == 0:
            guard(started, "small-modulus candidate self-test")
    return {
        "modulus_range_inclusive": [2, 99],
        "residue_modulus_pairs_tested": tested,
        "transcript_sha256": transcript.hexdigest(),
        "all_sets_equal": True,
    }


def run_primary_census(normalized_by_prime, started):
    source_vectors = [normalized_by_prime[prime] for prime in SOURCE_PRIMES]
    selector_vectors = [normalized_by_prime[prime] for prime in SELECTOR_PRIMES]
    modulus, weights = direct_crt_basis(SOURCE_PRIMES)
    if modulus != EXPECTED_MODULUS or modulus.bit_length() != 70:
        raise AssertionError("primary CRT modulus changed")

    labels = ("no_candidate", "ambiguous", "unique_zero", "unique_nonzero")
    outcome = collections.Counter()
    coordinates_by_outcome = {label: [] for label in labels}
    outcome_vector = []
    candidate_counts = []
    eea_step_counts = []
    combined_residues = []
    candidate_histogram = collections.Counter()
    final_histogram = collections.Counter()
    height_histogram = collections.Counter()
    stage_counts = [[] for _ in SELECTOR_PRIMES]
    stage_totals = [0] * len(SELECTOR_PRIMES)
    stage_nonempty = [0] * len(SELECTOR_PRIMES)
    survivors_by_coordinate = []
    nonempty_records = []
    height_records = []
    total_candidates = 0
    total_eea_steps = 0
    all_source_zero = 0
    maximum_profile = None
    candidate_hasher = hashlib.sha256()
    stage_hashers = [hashlib.sha256() for _ in SELECTOR_PRIMES]
    outcome_hasher = hashlib.sha256()
    unique_hasher = hashlib.sha256()

    census_started = time.perf_counter()
    for coordinate in range(EXPECTED_COORDINATE_COUNT):
        residues = [vector[coordinate] % prime for vector, prime in zip(source_vectors, SOURCE_PRIMES, strict=True)]
        all_source_zero += int(not any(residues))
        combined = direct_crt(residues, weights, modulus)
        if any(combined % prime != residue for prime, residue in zip(SOURCE_PRIMES, residues, strict=True)):
            raise AssertionError(f"CRT reduction failed at coordinate {coordinate}")
        combined_residues.append(str(combined))
        candidates, eea_steps = ordinary_eea_candidates(combined, modulus)
        eea_step_counts.append(eea_steps)
        total_eea_steps += eea_steps
        total_candidates += len(candidates)
        candidate_counts.append(len(candidates))
        candidate_histogram[len(candidates)] += 1
        candidate_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in candidates:
            candidate_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        candidate_hasher.update(b"\n")

        survivors = candidates
        for stage, (prime, vector) in enumerate(zip(SELECTOR_PRIMES, selector_vectors, strict=True)):
            observed = vector[coordinate] % prime
            survivors = [
                (numerator, denominator)
                for numerator, denominator in survivors
                if denominator % prime
                and numerator % prime * pow(denominator % prime, -1, prime) % prime == observed
            ]
            stage_counts[stage].append(len(survivors))
            stage_totals[stage] += len(survivors)
            stage_nonempty[stage] += int(bool(survivors))
            stage_hashers[stage].update(f"{coordinate}:".encode("ascii"))
            for numerator, denominator in survivors:
                stage_hashers[stage].update(f"{numerator}/{denominator};".encode("ascii"))
            stage_hashers[stage].update(b"\n")

        survivors_by_coordinate.append(survivors)
        final_histogram[len(survivors)] += 1
        if survivors:
            nonempty_records.append(
                {
                    "coordinate": coordinate,
                    "candidates": [
                        [str(n), str(d)]
                        for n, d in survivors
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
            unique_hasher.update(f"{coordinate}:{numerator}/{denominator}\n".encode("ascii"))
            twice_product = 2 * abs(numerator) * denominator
            product_bits = twice_product.bit_length()
            numerator_bits = abs(numerator).bit_length()
            denominator_bits = denominator.bit_length()
            height_histogram[product_bits] += 1
            height_record = {
                "coordinate": coordinate,
                "numerator": str(numerator),
                "positive_denominator": str(denominator),
                "twice_absolute_product": str(twice_product),
                "twice_product_bit_length": product_bits,
                "absolute_numerator_bit_length": numerator_bits,
                "denominator_bit_length": denominator_bits,
            }
            height_records.append(height_record)
            profile = (
                product_bits,
                numerator_bits,
                denominator_bits,
                coordinate,
                numerator,
                denominator,
            )
            if maximum_profile is None or profile > maximum_profile:
                maximum_profile = profile
        outcome[label] += 1
        coordinates_by_outcome[label].append(coordinate)
        outcome_vector.append(label)
        outcome_hasher.update(f"{coordinate}:{label}\n".encode("ascii"))
        if coordinate % 4096 == 0:
            guard(started, "primary M70 census")

    maximum_record = None
    if maximum_profile is not None:
        product_bits, numerator_bits, denominator_bits, coordinate, numerator, denominator = maximum_profile
        maximum_record = {
            "coordinate": coordinate,
            "numerator": str(numerator),
            "positive_denominator": str(denominator),
            "twice_absolute_product": str(2 * abs(numerator) * denominator),
            "twice_product_bit_length": product_bits,
            "absolute_numerator_bit_length": numerator_bits,
            "denominator_bit_length": denominator_bits,
        }
    stages = [
        {
            "characteristic": prime,
            "survivor_count_sum_after_selector": stage_totals[index],
            "coordinates_with_a_survivor_after_selector": stage_nonempty[index],
            "survivor_count_vector": stage_counts[index],
            "survivor_count_vector_sha256": canonical_hash(stage_counts[index]),
            "survivor_candidate_stream_sha256": stage_hashers[index].hexdigest(),
        }
        for index, prime in enumerate(SELECTOR_PRIMES)
    ]
    outcome_dict = {label: outcome[label] for label in labels}
    guard(started, "primary M70 census completion")
    return {
        "source_characteristics": list(SOURCE_PRIMES),
        "selector_characteristics": list(SELECTOR_PRIMES),
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "crt_basis_weights_sha256": canonical_hash([str(value) for value in weights]),
        "outcome": outcome_dict,
        "route_selection_U": outcome["no_candidate"] + outcome["ambiguous"],
        "outcome_label_vector": outcome_vector,
        "outcome_label_vector_sha256": canonical_hash(outcome_vector),
        "outcome_text_stream_sha256": outcome_hasher.hexdigest(),
        "coordinates_by_outcome": coordinates_by_outcome,
        "coordinates_by_outcome_sha256": {
            label: canonical_hash(values) for label, values in coordinates_by_outcome.items()
        },
        "candidate_count_vector": candidate_counts,
        "candidate_count_vector_sha256": canonical_hash(candidate_counts),
        "extended_euclid_step_count_vector": eea_step_counts,
        "extended_euclid_step_count_vector_sha256": canonical_hash(eea_step_counts),
        "candidate_count_histogram": {
            str(key): value for key, value in sorted(candidate_histogram.items())
        },
        "total_candidates_before_selectors": total_candidates,
        "total_extended_euclid_steps": total_eea_steps,
        "all_source_residues_zero_coordinate_count": all_source_zero,
        "complete_candidate_text_stream_sha256": candidate_hasher.hexdigest(),
        "combined_crt_residue_vector_sha256": canonical_hash(combined_residues),
        "selector_stages": stages,
        "final_survivor_count_histogram": {
            str(key): value for key, value in sorted(final_histogram.items())
        },
        "unique_candidate_coordinate_value_stream_sha256": unique_hasher.hexdigest(),
        "nonempty_final_survivor_records": nonempty_records,
        "nonempty_final_survivor_records_sha256": canonical_hash(nonempty_records),
        "unique_candidate_height_records": height_records,
        "unique_candidate_height_records_sha256": canonical_hash(height_records),
        "unique_candidate_product_bit_length_histogram": {
            str(key): value for key, value in sorted(height_histogram.items())
        },
        "maximum_unique_candidate_height_profile": maximum_record,
        "census_wall_seconds": time.perf_counter() - census_started,
        "_survivors_by_coordinate": survivors_by_coordinate,
    }


def run_fresh_audit(primary, audit_vector, started):
    decision_hasher = hashlib.sha256()
    survivor_hasher = hashlib.sha256()
    coordinates_with_primary_candidates = 0
    candidates_tested = 0
    candidates_rejected = 0
    candidates_surviving = 0
    denominator_failures = 0
    primary_unique_rejected = 0
    ambiguous_reduction = collections.Counter()
    survivor_counts = []
    survivor_records = []
    rejected_coordinates = []

    for coordinate, candidates in enumerate(primary["_survivors_by_coordinate"]):
        if candidates:
            coordinates_with_primary_candidates += 1
        audit_residue = audit_vector[coordinate] % AUDIT_PRIME
        audit_survivors = []
        for numerator, denominator in candidates:
            candidates_tested += 1
            if denominator % AUDIT_PRIME == 0:
                decision = "reject_denominator_zero"
                denominator_failures += 1
            elif numerator % AUDIT_PRIME * pow(denominator % AUDIT_PRIME, -1, AUDIT_PRIME) % AUDIT_PRIME != audit_residue:
                decision = "reject_residue_mismatch"
            else:
                decision = "survive"
                audit_survivors.append((numerator, denominator))
            if decision == "survive":
                candidates_surviving += 1
            else:
                candidates_rejected += 1
            decision_hasher.update(
                f"{coordinate}:{numerator}/{denominator}:{decision}\n".encode("ascii")
            )
        survivor_counts.append(len(audit_survivors))
        survivor_hasher.update(f"{coordinate}:".encode("ascii"))
        for numerator, denominator in audit_survivors:
            survivor_hasher.update(f"{numerator}/{denominator};".encode("ascii"))
        survivor_hasher.update(b"\n")
        if audit_survivors:
            survivor_records.append(
                {
                    "coordinate": coordinate,
                    "candidates": [
                        [str(n), str(d)]
                        for n, d in audit_survivors
                    ],
                }
            )
        if len(candidates) == 1 and not audit_survivors:
            primary_unique_rejected += 1
            rejected_coordinates.append(coordinate)
        elif len(candidates) > 1:
            if not audit_survivors:
                ambiguous_reduction["zero"] += 1
            elif len(audit_survivors) == 1:
                ambiguous_reduction["one"] += 1
            else:
                ambiguous_reduction["multiple"] += 1
        if coordinate % 4096 == 0:
            guard(started, "fresh audit selector")

    guard(started, "fresh audit completion")
    return {
        "characteristic": AUDIT_PRIME,
        "coordinates_with_primary_survivors": coordinates_with_primary_candidates,
        "candidates_tested": candidates_tested,
        "candidates_rejected": candidates_rejected,
        "candidates_surviving": candidates_surviving,
        "primary_unique_candidates_rejected": primary_unique_rejected,
        "primary_unique_candidate_rejected_coordinates": rejected_coordinates,
        "ambiguous_sets_reduced_to_zero": ambiguous_reduction["zero"],
        "ambiguous_sets_reduced_to_one": ambiguous_reduction["one"],
        "ambiguous_sets_remaining_multiple": ambiguous_reduction["multiple"],
        "audit_denominator_failures": denominator_failures,
        "audit_decision_text_stream_sha256": decision_hasher.hexdigest(),
        "audit_survivor_text_stream_sha256": survivor_hasher.hexdigest(),
        "audit_survivor_count_vector_sha256": canonical_hash(survivor_counts),
        "audit_survivor_records_sha256": canonical_hash(survivor_records),
        "audit_survivor_records": survivor_records,
        "audit_survivor_record_count": len(survivor_records),
        "primary_outcome_stream_unchanged": True,
        "route_selection_U_unchanged": primary["route_selection_U"],
    }


def primary_public_payload(primary):
    selector_count_hashes = {
        str(stage["characteristic"]): stage["survivor_count_vector_sha256"]
        for stage in primary["selector_stages"]
    }
    selector_text_hashes = {
        str(stage["characteristic"]): stage["survivor_candidate_stream_sha256"]
        for stage in primary["selector_stages"]
    }
    hashes = {
        "candidate_count_vector_sha256": primary["candidate_count_vector_sha256"],
        "combined_crt_residue_vector_sha256": primary["combined_crt_residue_vector_sha256"],
        "complete_candidate_text_stream_sha256": primary["complete_candidate_text_stream_sha256"],
        "coordinates_by_outcome_sha256": primary["coordinates_by_outcome_sha256"],
        "extended_euclid_step_count_vector_sha256": primary[
            "extended_euclid_step_count_vector_sha256"
        ],
        "final_survivor_text_stream_sha256": selector_text_hashes[str(SELECTOR_PRIMES[-1])],
        "nonempty_survivor_records_sha256": primary[
            "nonempty_final_survivor_records_sha256"
        ],
        "outcome_label_vector_sha256": primary["outcome_label_vector_sha256"],
        "outcome_text_stream_sha256": primary["outcome_text_stream_sha256"],
        "selector_survivor_count_vector_sha256": selector_count_hashes,
        "selector_survivor_text_stream_sha256": selector_text_hashes,
        "unique_candidate_height_records_sha256": primary[
            "unique_candidate_height_records_sha256"
        ],
    }
    return {
        "source_characteristics": primary["source_characteristics"],
        "selector_characteristics": primary["selector_characteristics"],
        "selector_assurance": "confirmatory primary selectors; p173 and p197 are not fully held out",
        "source_modulus": primary["source_modulus"],
        "source_modulus_bit_length": primary["source_modulus_bit_length"],
        "outcome": primary["outcome"],
        "U_no_candidate_plus_ambiguous": primary["route_selection_U"],
        "outcome_label_vector": primary["outcome_label_vector"],
        "coordinates_by_outcome": primary["coordinates_by_outcome"],
        "candidate_enumeration": {
            "candidate_count_vector": primary["candidate_count_vector"],
            "candidate_count_histogram": primary["candidate_count_histogram"],
            "extended_euclid_step_count_vector": primary[
                "extended_euclid_step_count_vector"
            ],
            "total_candidates_before_selectors": primary[
                "total_candidates_before_selectors"
            ],
            "total_extended_euclid_steps": primary["total_extended_euclid_steps"],
            "final_survivor_count_histogram": primary[
                "final_survivor_count_histogram"
            ],
            "unique_candidate_product_bit_length_histogram": primary[
                "unique_candidate_product_bit_length_histogram"
            ],
        },
        "nonempty_survivor_records": primary["nonempty_final_survivor_records"],
        "unique_candidate_height_records": primary["unique_candidate_height_records"],
        "maximum_unique_candidate_height_profile": primary[
            "maximum_unique_candidate_height_profile"
        ],
        "hashes": hashes,
    }


def fresh_public_payload(primary_public, audit):
    primary_commitment = canonical_hash(
        {
            "outcome": primary_public["outcome"],
            "U": primary_public["U_no_candidate_plus_ambiguous"],
            "hashes": primary_public["hashes"],
        }
    )
    return {
        "characteristic": audit["characteristic"],
        "role": "fresh one-way audit-only falsifier",
        "coordinates_with_primary_survivors": audit[
            "coordinates_with_primary_survivors"
        ],
        "candidates_tested": audit["candidates_tested"],
        "candidates_rejected": audit["candidates_rejected"],
        "candidates_surviving": audit["candidates_surviving"],
        "primary_unique_candidates_rejected": audit[
            "primary_unique_candidates_rejected"
        ],
        "primary_unique_candidate_rejected_coordinates": audit[
            "primary_unique_candidate_rejected_coordinates"
        ],
        "ambiguous_sets_reduced_to_zero": audit["ambiguous_sets_reduced_to_zero"],
        "ambiguous_sets_reduced_to_one": audit["ambiguous_sets_reduced_to_one"],
        "ambiguous_sets_remaining_multiple": audit[
            "ambiguous_sets_remaining_multiple"
        ],
        "audit_denominator_failures": audit["audit_denominator_failures"],
        "audit_survivor_records": audit["audit_survivor_records"],
        "audit_decision_text_stream_sha256": audit[
            "audit_decision_text_stream_sha256"
        ],
        "audit_survivor_text_stream_sha256": audit[
            "audit_survivor_text_stream_sha256"
        ],
        "audit_survivor_records_sha256": audit["audit_survivor_records_sha256"],
        "primary_commitment_before_audit_sha256": primary_commitment,
        "primary_commitment_after_audit_sha256": primary_commitment,
        "primary_counts_or_U_changed": False,
        "primary_no_candidate_rescued": False,
    }


def load_census_receipt(campaign: Path, normalization_bundle):
    producer_path = campaign / CENSUS_PRODUCER_PATH
    receipt_path = campaign / CENSUS_RECEIPT_PATH
    if file_sha256(producer_path) != EXPECTED_CENSUS_PRODUCER_HASH:
        raise ValueError("final census producer hash changed")
    if file_sha256(receipt_path) != EXPECTED_CENSUS_RECEIPT_HASH:
        raise ValueError("final census receipt hash changed")
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    source_script = payload.get("source_script", {})
    checks = payload.get("checks", {})
    resources = payload.get("resources", {})
    timings = payload.get("timings", {})
    if (
        payload.get("schema")
        != "hc4.third-colon-koszul-p197-common-minor-m70-census.v1"
        or payload.get("status") != "FRESH_AUDIT_FALSIFIED_PRIMARY_CANDIDATE"
        or source_script.get("path") != CENSUS_PRODUCER_PATH
        or source_script.get("sha256") != EXPECTED_CENSUS_PRODUCER_HASH
        or source_script.get("imports_normalizer_or_previous_census") is not False
        or not checks
        or not all(value is True for value in checks.values())
        or float(timings.get("total_wall_seconds", 31.0)) >= 30.0
        or int(resources.get("maximum_rss_native", 512_000_000)) >= 512_000_000
        or int(resources.get("process_swap_delta", -1)) != 0
        or int(resources.get("final_process_swaps", -1)) != 0
    ):
        raise ValueError("final census producer receipt failed schema/resource gates")

    normalization_input = payload.get("normalization_input", {})
    if (
        normalization_input.get("producer_script_sha256")
        != EXPECTED_NORMALIZATION_PRODUCER_HASH
        or normalization_input.get("receipt_sha256")
        != EXPECTED_NORMALIZATION_RECEIPT_HASH
        or normalization_input.get("ordered_R197_sha256") != EXPECTED_R197_HASH
    ):
        raise ValueError("census normalization binding changed")
    manifests = normalization_input.get("normalized_artifacts", {})
    if set(map(int, manifests)) != set(ALL_PRIMES):
        raise ValueError("census normalization artifact prime set changed")
    for prime in ALL_PRIMES:
        manifest = manifests[str(prime)]
        record = normalization_bundle["records"][prime]
        expected_role = "fresh_audit_only" if prime == AUDIT_PRIME else "primary"
        if (
            manifest.get("sha256") != record["artifact_sha256"]
            or manifest.get("sha256") != EXPECTED_NORMALIZED_ARTIFACT_HASHES[prime]
            or manifest.get("normalized_coordinate_vector_sha256")
            != record["normalized_sha256"]
            or manifest.get("role") != expected_role
        ):
            raise AssertionError(f"census artifact manifest mismatch at prime {prime}")
    return {
        "payload": payload,
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": EXPECTED_CENSUS_RECEIPT_HASH,
    }


def compare_census_replay(primary, audit, census_bundle):
    primary_public = primary_public_payload(primary)
    fresh_public = fresh_public_payload(primary_public, audit)
    producer = census_bundle["payload"]
    if primary_public != producer.get("primary_census"):
        mismatches = sorted(
            key
            for key in set(primary_public) | set(producer.get("primary_census", {}))
            if primary_public.get(key) != producer.get("primary_census", {}).get(key)
        )
        raise AssertionError(f"primary census payload mismatch in fields {mismatches}")
    if fresh_public != producer.get("fresh_audit"):
        mismatches = sorted(
            key
            for key in set(fresh_public) | set(producer.get("fresh_audit", {}))
            if fresh_public.get(key) != producer.get("fresh_audit", {}).get(key)
        )
        raise AssertionError(f"fresh audit payload mismatch in fields {mismatches}")
    commitment = fresh_public["primary_commitment_before_audit_sha256"]
    if (
        commitment != EXPECTED_PRIMARY_COMMITMENT_HASH
        or tuple(fresh_public["primary_unique_candidate_rejected_coordinates"])
        != EXPECTED_AUDIT_REJECTED_COORDINATES
        or producer.get("interpretation")
        != {
            "U": 19750,
            "band": "route_stop",
            "next_route": "forbid QQ assembly; audit falsified at least one primary unique candidate",
        }
    ):
        raise AssertionError("frozen negative outcome or route interpretation changed")
    return primary_public, fresh_public


def load_normalization_bundle(campaign: Path, receipt_path: Path, reconstruction):
    """Load the stable producer schema without sharing any producer code."""

    if not receipt_path.is_absolute():
        receipt_path = campaign / receipt_path
    receipt_path = receipt_path.resolve()
    if file_sha256(campaign / NORMALIZATION_PRODUCER_PATH) != EXPECTED_NORMALIZATION_PRODUCER_HASH:
        raise ValueError("final normalization producer hash changed")
    if file_sha256(receipt_path) != EXPECTED_NORMALIZATION_RECEIPT_HASH:
        raise ValueError("final normalization receipt hash changed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("schema")
        != "hc4.third-colon-koszul-p197-common-minor-normalization.v1"
        or receipt.get("status") != "PASS_SIX_PRIME_P197_COMMON_MINOR_NORMALIZATION"
    ):
        raise ValueError("normalization producer receipt is not a supported PASS")
    hashes = receipt.get("hashes", {})
    r197 = list(map(int, receipt.get("ordered_R197", [])))
    if (
        r197 != reconstruction["r197"]
        or hashes.get("ordered_R197_sha256") != EXPECTED_R197_HASH
        or hashes.get("integer_koszul_stream_sha256") != EXPECTED_KOSZUL_CONTENT_HASH
        or hashes.get("descriptor_stream_sha256") != EXPECTED_DESCRIPTOR_HASH
        or hashes.get("fixed_integer_B_sha256")
        != reconstruction["minor_integer_rows_sha256"]
        or hashes.get("fixed_sparse_decimal_B_sha256")
        != reconstruction["minor_sparse_rows_sha256"]
    ):
        raise AssertionError("normalization receipt algebra/common-minor binding changed")
    manifests = hashes.get("normalized_artifacts", {})
    telemetry = receipt.get("prime_telemetry", {})
    source_manifest = hashes.get("source_identities", {})
    if set(map(int, manifests)) != set(ALL_PRIMES):
        raise ValueError("normalization artifact prime set changed")

    records = {}
    for prime in ALL_PRIMES:
        key = str(prime)
        manifest = manifests[key]
        artifact_path = Path(str(manifest["path"]))
        if not artifact_path.is_absolute():
            artifact_path = campaign / artifact_path
        artifact_path = artifact_path.resolve()
        if (
            campaign.resolve() not in artifact_path.parents
            or file_sha256(artifact_path) != manifest["sha256"]
            or manifest["sha256"] != EXPECTED_NORMALIZED_ARTIFACT_HASHES[prime]
            or artifact_path.stat().st_size != int(manifest["byte_count"])
        ):
            raise ValueError(f"normalized artifact binding failed at prime {prime}")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        source = artifact.get("source", {})
        common_minor = artifact.get("common_minor", {})
        alpha = list(map(int, artifact.get("koszul_coefficient_vector", [])))
        normalized = list(map(int, artifact.get("normalized_coordinate_vector", [])))
        difference = list(map(int, artifact.get("difference_vector", [])))
        checks = artifact.get("checks", {})
        direct_replay = artifact.get("direct_replay", {})
        role = "fresh_audit_only" if prime == AUDIT_PRIME else "primary"
        if (
            artifact.get("schema")
            != "hc4.third-colon-koszul-p197-common-minor-normalized-vector.v1"
            or artifact.get("status")
            != "PASS_P197_COMMON_MINOR_NORMALIZED_MODULAR_IDENTITY"
            or int(artifact.get("characteristic", -1)) != prime
            or artifact.get("role") != role
            or list(map(int, common_minor.get("ordered_coordinates", [])))
            != reconstruction["r197"]
            or common_minor.get("ordered_coordinates_sha256") != EXPECTED_R197_HASH
            or int(common_minor.get("rank", -1)) != EXPECTED_KOSZUL_COUNT
            or not int(common_minor.get("determinant_mod_p", 0))
            or len(alpha) != EXPECTED_KOSZUL_COUNT
            or len(normalized) != EXPECTED_COORDINATE_COUNT
            or len(difference) != EXPECTED_COORDINATE_COUNT
            or any(not 0 <= value < prime for value in alpha + normalized + difference)
            or canonical_hash(alpha) != artifact.get("koszul_coefficient_vector_sha256")
            or canonical_hash(normalized) != artifact.get("normalized_coordinate_vector_sha256")
            or canonical_hash(difference) != artifact.get("difference_vector_sha256")
            or not all(checks.values())
            or not direct_replay.get("difference_image_zero")
            or not direct_replay.get("source_image_equals_target")
            or not direct_replay.get("normalized_image_equals_target")
        ):
            raise AssertionError(f"normalized artifact validation failed at prime {prime}")
        expected_source = source_manifest[key]
        if (
            source.get("artifact_path") != expected_source.get("artifact_path")
            or source.get("artifact_sha256") != expected_source.get("artifact_sha256")
            or source.get("coordinate_vector_sha256")
            != expected_source.get("coordinate_vector_sha256")
            or source.get("receipt_path") != expected_source.get("receipt_path")
            or source.get("receipt_sha256") != expected_source.get("receipt_sha256")
            or expected_source.get("role") != role
        ):
            raise AssertionError(f"source binding mismatch at prime {prime}")
        prime_telemetry = telemetry[key]
        if (
            int(prime_telemetry.get("rank", -1)) != int(common_minor["rank"])
            or int(prime_telemetry.get("determinant_mod_p", -1))
            != int(common_minor["determinant_mod_p"])
            or prime_telemetry.get("coefficient_vector_sha256")
            != artifact["koszul_coefficient_vector_sha256"]
            or prime_telemetry.get("normalized_vector_sha256")
            != artifact["normalized_coordinate_vector_sha256"]
            or prime_telemetry.get("difference_vector_sha256")
            != artifact["difference_vector_sha256"]
        ):
            raise AssertionError(f"normalization telemetry mismatch at prime {prime}")
        records[prime] = {
            "artifact_path": str(artifact_path),
            "artifact_sha256": manifest["sha256"],
            "alpha": alpha,
            "alpha_sha256": artifact["koszul_coefficient_vector_sha256"],
            "normalized": normalized,
            "normalized_sha256": artifact["normalized_coordinate_vector_sha256"],
            "difference": difference,
            "difference_sha256": artifact["difference_vector_sha256"],
            "rank": common_minor["rank"],
            "determinant": common_minor["determinant_mod_p"],
            "source": source,
        }
    return {
        "receipt": receipt,
        "receipt_path": str(receipt_path),
        "receipt_sha256": file_sha256(receipt_path),
        "records": records,
    }


def load_producer_bundle(campaign: Path, receipt_path: Path, reconstruction):
    """Combine final normalization and census bindings once both are frozen."""

    return {"normalization": load_normalization_bundle(campaign, receipt_path, reconstruction)}


def run_normalization_audit(campaign, receipt_path, reconstruction, started):
    telemetry_path = campaign / AUDIT_SOURCE_HASHES["telemetry_path"]
    if file_sha256(telemetry_path) != AUDIT_SOURCE_HASHES["telemetry_sha256"]:
        raise ValueError("fresh audit identity telemetry hash changed")
    audit_telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
    telemetry_gates = audit_telemetry.get("gates", {})
    required_true_gates = (
        "artifact_hash_matches_producer_receipt",
        "external_wall_within_cap",
        "fixed_free_hash_matches_frozen_gauge",
        "gauge_source_hash_matches",
        "maximum_rss_within_cap",
        "only_authorized_characteristic_written",
        "problem_streams_match_frozen_gauge",
        "process_swaps_zero",
        "status_pass_exact_modular_third_colon_identity",
    )
    if (
        audit_telemetry.get("status") != "PASS_RESOURCE_GATED_FIXED_FREE_IDENTITY_TRANSFER"
        or int(audit_telemetry.get("characteristic", -1)) != AUDIT_PRIME
        or not all(telemetry_gates.get(key) is True for key in required_true_gates)
        or int(telemetry_gates.get("identity_replay_mismatch_count", -1)) != 0
        or int(audit_telemetry.get("external_telemetry", {}).get("process_swaps", -1)) != 0
    ):
        raise ValueError("fresh audit identity telemetry is not a bounded PASS")
    bundle = load_normalization_bundle(campaign, receipt_path, reconstruction)
    records = []
    normalized = {}
    for prime in ALL_PRIMES:
        source = load_source_identity(
            campaign,
            prime,
            AUDIT_SOURCE_HASHES if prime == AUDIT_PRIME else None,
        )
        producer_record = bundle["records"][prime]
        if (
            producer_record["source"]["artifact_sha256"] != source["artifact_sha256"]
            or producer_record["source"]["receipt_sha256"] != source["receipt_sha256"]
            or producer_record["source"]["coordinate_vector_sha256"] != source["vector_sha256"]
        ):
            raise AssertionError(f"producer/source manifest mismatch at prime {prime}")
        record = verify_one_normalization(
            reconstruction, source, producer_record, started
        )
        normalized[prime] = record.pop("normalized")
        records.append(record)
    guard(started, "six-prime independent normalization audit")
    return bundle, records, normalized


def normalization_receipt(campaign, producer_path, reconstruction, records, started):
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    guard(started, "normalization-only receipt")
    return {
        "schema": "hc4.third-colon-koszul-p197-common-minor-normalization-independent-audit.v1",
        "status": "PASS_INDEPENDENT_SIX_PRIME_P197_COMMON_MINOR_NORMALIZATION",
        "assurance": "independent exact algebra reconstruction and bounded six-prime replay",
        "claim_boundary": (
            "A PASS independently proves only that the frozen target-blind R197 minor "
            "is invertible at the five primary finite fields and one fresh audit field, "
            "and that it gives the displayed six exact modular Koszul normalizations and "
            "direct Macaulay identity replays. It does not run the M70 census, assemble "
            "QQ multipliers, prove QQ membership, compute a colon or saturation, close "
            "the secant chart, establish nullcone containment, or prove HC4."
        ),
        "independence_boundary": {
            "normalization_producer_imported_or_executed": False,
            "stopped_normalizer_imported_or_executed": False,
            "producer_helpers_imported": False,
            "integer_koszul_rows_reconstructed": True,
            "all_exact_koszul_images_zero": True,
            "rank_determinant_and_solve_implementation": "local sparse Gaussian elimination with shortest-row pivoting and back substitution",
            "source_and_normalized_identities_directly_replayed": True,
        },
        "dimensions": {
            "integer_koszul_matrix_shape": [2053, 38048],
            "integer_koszul_nonzero_count": EXPECTED_KOSZUL_NNZ,
            "common_minor_shape": [2053, 2053],
            "common_minor_nonzero_count": len(reconstruction["minor_entries"]),
        },
        "hashes": {
            "source_sha256": file_sha256(Path(__file__).resolve()),
            "preregistration_sha256": FROZEN_HASHES[
                "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md"
            ],
            "normalization_producer_sha256": EXPECTED_NORMALIZATION_PRODUCER_HASH,
            "normalization_receipt_sha256": EXPECTED_NORMALIZATION_RECEIPT_HASH,
            "fresh_audit_identity_telemetry_sha256": AUDIT_SOURCE_HASHES["telemetry_sha256"],
            "integer_koszul_stream_sha256": EXPECTED_KOSZUL_CONTENT_HASH,
            "ordered_R197_sha256": canonical_hash(reconstruction["r197"]),
            "fixed_integer_B_sha256": reconstruction["minor_integer_rows_sha256"],
            "fixed_sparse_decimal_B_sha256": reconstruction["minor_sparse_rows_sha256"],
        },
        "prime_records": records,
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "process_swap_cap": 0,
            "total_wall_seconds": wall,
            "maximum_rss_native": native_rss_bytes(),
            "process_swaps": process_swaps(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def full_audit_receipt(
    reconstruction,
    normalization_records,
    brute_force,
    primary_public,
    fresh_public,
    census_bundle,
    started,
):
    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    guard(started, "full independent receipt")
    primary_hashes = primary_public["hashes"]
    retained_failures = []
    for relative_path in (
        "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization-independent-audit-failed-telemetry-gate.json",
        "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization-independent-audit-failed-sage-rss.json",
        "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-independent-audit-failed-census-resource-adapter.json",
    ):
        path = Path(__file__).resolve().parent.parent / relative_path
        if path.exists():
            retained_failures.append(
                {
                    "path": relative_path,
                    "sha256": file_sha256(path),
                    "role": "retained fail-closed operational evidence; not part of the PASS route",
                }
            )
    return {
        "schema": "hc4.third-colon-koszul-p197-common-minor-independent-audit.v1",
        "status": "PASS_INDEPENDENT_REPLAY_OF_NEGATIVE_COMMON_MINOR_CENSUS",
        "mathematical_route_outcome": "FRESH_AUDIT_FALSIFIED_PRIMARY_CANDIDATE",
        "assurance": (
            "independent bounded six-prime Koszul normalization, complete M70 census, "
            "and one-way fresh-audit replay of the producer's negative outcome"
        ),
        "claim_boundary": (
            "This PASS certifies independent reproducibility of the displayed finite-field "
            "normalizations and bounded M70/fresh-audit computation. The computation stops "
            "the present rational-reconstruction route: it does not assemble QQ multipliers, "
            "prove QQ membership, compute a colon or saturation, establish residual dimension "
            "114, close the secant chart, prove nullcone containment, or prove HC4."
        ),
        "independence_boundary": {
            "normalization_or_census_producer_imported_or_executed": False,
            "stopped_normalizer_imported_or_executed": False,
            "producer_helpers_imported": False,
            "producer_schema_and_text_stream_wire_format_adapted": True,
            "integer_koszul_rows_reconstructed_from_frozen_algebra": True,
            "rank_determinant_and_solve_implementation": "local sparse Gaussian elimination with shortest-row pivoting and back substitution",
            "CRT_implementation": "local direct CRT basis and reduction",
            "candidate_implementation": "local ordinary Euclidean continued-fraction enumeration",
            "small_modulus_brute_force_implementation": "literal denominator and residue enumeration",
            "all_six_source_and_normalized_identities_directly_replayed": True,
            "fresh_audit_allowed_to_modify_primary_stream": False,
        },
        "dimensions": {
            "integer_koszul_matrix_shape": [2053, 38048],
            "integer_koszul_nonzero_count": EXPECTED_KOSZUL_NNZ,
            "common_minor_shape": [2053, 2053],
            "common_minor_nonzero_count": len(reconstruction["minor_entries"]),
            "coordinates_classified": EXPECTED_COORDINATE_COUNT,
        },
        "hashes": {
            "independent_source_sha256": file_sha256(Path(__file__).resolve()),
            "preregistration_sha256": FROZEN_HASHES[
                "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md"
            ],
            "normalization_producer_sha256": EXPECTED_NORMALIZATION_PRODUCER_HASH,
            "normalization_receipt_sha256": EXPECTED_NORMALIZATION_RECEIPT_HASH,
            "census_producer_sha256": EXPECTED_CENSUS_PRODUCER_HASH,
            "census_receipt_sha256": EXPECTED_CENSUS_RECEIPT_HASH,
            "fresh_audit_identity_telemetry_sha256": AUDIT_SOURCE_HASHES[
                "telemetry_sha256"
            ],
            "integer_koszul_stream_sha256": EXPECTED_KOSZUL_CONTENT_HASH,
            "ordered_R197_sha256": canonical_hash(reconstruction["r197"]),
            "fixed_integer_B_sha256": reconstruction["minor_integer_rows_sha256"],
            "fixed_sparse_decimal_B_sha256": reconstruction[
                "minor_sparse_rows_sha256"
            ],
            "independent_primary_payload_sha256": canonical_hash(primary_public),
            "independent_fresh_audit_payload_sha256": canonical_hash(fresh_public),
            "primary_commitment_sha256": fresh_public[
                "primary_commitment_before_audit_sha256"
            ],
        },
        "normalization_prime_records": normalization_records,
        "candidate_enumerator_brute_force_check": brute_force,
        "primary_replay": {
            "source_characteristics": primary_public["source_characteristics"],
            "selector_characteristics": primary_public["selector_characteristics"],
            "source_modulus": primary_public["source_modulus"],
            "source_modulus_bit_length": primary_public["source_modulus_bit_length"],
            "outcome": primary_public["outcome"],
            "U_no_candidate_plus_ambiguous": primary_public[
                "U_no_candidate_plus_ambiguous"
            ],
            "candidate_count_histogram": primary_public["candidate_enumeration"][
                "candidate_count_histogram"
            ],
            "total_candidates_before_selectors": primary_public[
                "candidate_enumeration"
            ]["total_candidates_before_selectors"],
            "total_extended_euclid_steps": primary_public["candidate_enumeration"][
                "total_extended_euclid_steps"
            ],
            "final_survivor_count_histogram": primary_public[
                "candidate_enumeration"
            ]["final_survivor_count_histogram"],
            "maximum_unique_candidate_height_profile": primary_public[
                "maximum_unique_candidate_height_profile"
            ],
            "hashes": primary_hashes,
            "full_primary_payload_exactly_matches_producer": True,
        },
        "fresh_audit_replay": {
            key: fresh_public[key]
            for key in (
                "characteristic",
                "coordinates_with_primary_survivors",
                "candidates_tested",
                "candidates_rejected",
                "candidates_surviving",
                "primary_unique_candidates_rejected",
                "primary_unique_candidate_rejected_coordinates",
                "ambiguous_sets_reduced_to_zero",
                "ambiguous_sets_reduced_to_one",
                "ambiguous_sets_remaining_multiple",
                "audit_denominator_failures",
                "audit_decision_text_stream_sha256",
                "audit_survivor_text_stream_sha256",
                "audit_survivor_records_sha256",
                "primary_commitment_before_audit_sha256",
                "primary_commitment_after_audit_sha256",
                "primary_counts_or_U_changed",
                "primary_no_candidate_rescued",
            )
        }
        | {
            "audit_survivor_record_count": len(
                fresh_public["audit_survivor_records"]
            ),
            "full_fresh_audit_payload_exactly_matches_producer": True,
        },
        "interpretation": census_bundle["payload"]["interpretation"],
        "reproduction_checks": {
            "all_six_minor_ranks_determinants_and_solves_reproduced": True,
            "all_six_koszul_differences_reproduced": True,
            "all_six_direct_macaulay_replays_pass": True,
            "all_primary_classifications_and_large_vectors_exactly_equal": True,
            "all_primary_output_stream_hashes_reproduced": True,
            "all_primary_candidate_and_height_records_exactly_equal": True,
            "fresh_audit_decision_and_survivor_hashes_reproduced": True,
            "fresh_audit_survivor_records_exactly_equal": True,
            "primary_commitment_unchanged_by_one_way_audit": True,
            "route_stop_interpretation_reproduced": True,
            "no_QQ_multiplier_assembled": True,
            "resource_and_zero_swap_gates_pass": True,
        },
        "retained_operational_failures": retained_failures,
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "process_swap_cap": 0,
            "total_wall_seconds": wall,
            "maximum_rss_native": native_rss_bytes(),
            "process_swaps": process_swaps(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--producer-receipt", type=Path, required=True)
    parser.add_argument(
        "--normalization-only",
        action="store_true",
        help="freeze the independent six-prime normalization stage before the census",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output or campaign / "receipts" / (
        "hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-independent-audit.json"
    )
    if not output.is_absolute():
        output = campaign / output
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("240-second alarm")),
    )
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        reconstruction = reconstruct_algebra(campaign, started)
        if arguments.normalization_only:
            _bundle, records, _normalized = run_normalization_audit(
                campaign, arguments.producer_receipt, reconstruction, started
            )
            result = normalization_receipt(
                campaign, arguments.producer_receipt, reconstruction, records, started
            )
            output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "output": str(output),
                        "wall_seconds": result["resources"]["total_wall_seconds"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        normalization_bundle, records, normalized = run_normalization_audit(
            campaign, arguments.producer_receipt, reconstruction, started
        )
        brute_force = candidate_enumerator_self_test(started)
        primary = run_primary_census(normalized, started)
        fresh = run_fresh_audit(primary, normalized[AUDIT_PRIME], started)
        census_bundle = load_census_receipt(campaign, normalization_bundle)
        primary_public, fresh_public = compare_census_replay(
            primary, fresh, census_bundle
        )
        result = full_audit_receipt(
            reconstruction,
            records,
            brute_force,
            primary_public,
            fresh_public,
            census_bundle,
            started,
        )
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "mathematical_route_outcome": result["mathematical_route_outcome"],
                    "output": str(output),
                    "wall_seconds": result["resources"]["total_wall_seconds"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-p197-common-minor-independent-audit.v1",
            "status": "FAIL_CLOSED_INDEPENDENT_COMMON_MINOR_AUDIT",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No positive mathematical conclusion is licensed by this incomplete or failed audit.",
            "source_sha256": file_sha256(script_path),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_rss_bytes(),
            "process_swaps": process_swaps(),
        }
        output.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n")
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
