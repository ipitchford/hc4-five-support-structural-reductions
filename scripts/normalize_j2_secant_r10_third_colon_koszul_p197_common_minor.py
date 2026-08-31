#!/usr/bin/env sage-python
"""Produce the frozen p197-common-minor Koszul normalization at six primes."""

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


PRIMARY_PRIMES = (181, 173, 197, 2147483647, 2147483629)
AUDIT_PRIME = 2147482867
PRIMES = PRIMARY_PRIMES + (AUDIT_PRIME,)
R197_HASH = "dfb318fa370a3bc01bf4013d760c8ffdfff61c695caeee2ec7151f91dd212164"
STOPPED_R181_HASH = "c7b305a434025cf4b9eea5aa720f38f419fbed7da121f5b2bba2e9a60c7676dd"
DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
K_HASH = "bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856"
FREE_HASH = "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1"
PIVOT_SET_HASH = "2e59d83eba84cab80823a8277b2b40f1af518a02e7ae5de595baed358de01a1c"
WALL_CAP_SECONDS = 180.0
RSS_CAP_BYTES = 1_500_000_000

SOURCE_ARTIFACTS = {
    181: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json",
    173: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p173.json",
    197: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p197.json",
    2147483647: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483647.json",
    2147483629: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147483629.json",
    2147482867: "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867.json",
}
SOURCE_RECEIPTS = {
    prime: path.replace("artifacts/j2-", "receipts/hsop-j2-")
    for prime, path in SOURCE_ARTIFACTS.items()
}
SOURCE_HASHES = {
    181: ("e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b", "f04bc461e8b15c012c229d1de13eb940316bad35914f12a34ab3fc112b29f14c"),
    173: ("b434b3103e253d22e3f751196ec32b91fa6fc73a6f6d72414222453e4971043c", "ddaed2462174438e89b31cfacb95ee2adf7971bf2290c58422031baab9314f44"),
    197: ("f199970f9ca6860b57a8dd89f5d23da084a5fe85a146ca353259d958e1b38272", "671df724adb16f279f9be31dfe0c87f90b0d48f02a9ea6161245f26d86c701fe"),
    2147483647: ("a5a6027afc33afd5374f77b7e72dc945bf1c055e0ce79941d077b04445ca21ad", "dba8ffbaf933500d5e532f9f4b19f356b20710383614b9d8b03200980e611f79"),
    2147483629: ("2b9ed0814159eb6ce3d96e45904e991d3e281f2c0cadd1df008180d35eac6a90", "f572ebb40bbb4d590506210737347b0c6c964927ac866d9fba410621d4e354bb"),
    2147482867: ("101c4679e8c0512ccc00682107283c9add82a019476ab5a7bf9e586b41c9512f", "fb306ea450ffa84942ae7cc6a231c5c680664cdd6f6933f78e5369022d808277"),
}
FROZEN_HASHES = {
    "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md": "b203a118b302c50394a0188501e32d12cc077c85fca2b1513bed770f59a112f8",
    "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md": "927b640211638c5610b05ab34e663f77ead79565d86ad7d28784c0f1e94f1819",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization.json": "0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-p197-independent-singularity-audit.json": "e97001a1c7232e903192e649f440fc8bfe81277229793a9905469288dec8936f",
    "research/THIRD_COLON_KOSZUL_FULL_RANK_MODULAR_AUDIT_REGISTRATION.md": "86843c6d3a525087c4d940f9004fb0bac7176b1f1ec07720a48231285a69a614",
    "scripts/audit_j2_secant_r10_third_colon_koszul_full_rank_modular.py": "e2a6f919f99e537342f27b316e3e8003c3a28f82f667ff05a2e023de0aa4482b",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-full-rank-modular-audit.json": "86598ea5b5df670017d0d104978f5c8db7eef6f9313b3aac511f0ea6a5ad4dc2",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py": "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json": "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
    "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867-telemetry.json": "c0034711d93855a51abef069b31751a545bac2c8e8adec2b5c60137fdf37be1a",
    "artifacts/j2-secant-r10-first-colon-kernel-qq.json": "2c6b84ad400634a0f54aa54c3ebfb49b6ae3453240335713f07681fa5773d130",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
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


def load_r197(campaign: Path):
    path = campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-full-rank-modular-audit.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS_FULL_KOSZUL_RANK_AT_173_181_197":
        raise ValueError("full-rank audit status changed")
    record = payload.get("prime_records", {}).get("197", {}).get("custom_rank_telemetry", {})
    coordinates = list(map(int, record.get("pivot_coordinates", [])))
    if len(coordinates) != 2053 or len(set(coordinates)) != 2053:
        raise ValueError("malformed ordered R197 coordinate list")
    if canonical_hash(coordinates) != R197_HASH or record.get("pivot_coordinates_sha256") != R197_HASH:
        raise ValueError("ordered R197 hash changed")
    if R197_HASH == STOPPED_R181_HASH:
        raise AssertionError("stopped coordinate set was reused")
    return coordinates


def reconstruct(campaign: Path, ind, started: float, initial_swaps: int):
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading, open_factor = homogeneous_saturation_system()
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
    h3_terms, h3_expression = ind.artifact_terms(
        campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
        "terms", variables, 248, 2,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = cubic_expressions + [h_expression, h2_expression]
    degrees = [3] * 17 + [4, 4]
    characters = []
    for terms in generator_terms:
        observed = {ind.character(exponents) for exponents, _ in terms}
        if len(observed) != 1:
            raise ValueError("generator character changed")
        characters.append(next(iter(observed)))
    if ind.expression_hash(generator_expressions) != GENERATOR_HASH:
        raise ValueError("generator stream changed")
    pools = {}
    for degree in (4, 5):
        for monomial in ind.exponent_tuples(18, degree):
            pools.setdefault((degree, ind.character(monomial)), []).append(monomial)
    descriptors = []
    for index, (degree, character) in enumerate(zip(degrees, characters, strict=True)):
        descriptors.extend(
            (index, monomial)
            for monomial in pools[(8 - degree, (3 - character) % 12)]
        )
    if len(descriptors) != 38048 or canonical_hash(descriptors) != DESCRIPTOR_HASH:
        raise ValueError("descriptor stream changed")
    descriptor_index = {descriptor: index for index, descriptor in enumerate(descriptors)}
    columns = []
    stream = hashlib.sha256()
    pair_counts = Counter()
    for left in range(19):
        for right in range(left + 1, 19):
            residual_degree = 8 - degrees[left] - degrees[right]
            if residual_degree < 0:
                continue
            residual_character = (3 - characters[left] - characters[right]) % 12
            for residual in ind.exponent_tuples(18, residual_degree):
                if ind.character(residual) != residual_character:
                    continue
                column = ind.primitive_column(left, right, residual, generator_terms, descriptor_index)
                columns.append(column)
                ind.framed_update(stream, [[coordinate, str(value)] for coordinate, value in column])
                pair_counts[(degrees[left], degrees[right])] += 1
        guard(started, initial_swaps, "Koszul reconstruction")
    if len(columns) != 2053 or sum(map(len, columns)) != 154939:
        raise ValueError("Koszul dimensions changed")
    if pair_counts != Counter({(3, 3): 1993, (3, 4): 60}) or stream.hexdigest() != K_HASH:
        raise ValueError("Koszul stream changed")
    target_polynomial = sp.Poly(sp.expand(open_factor * h3_expression), *variables, domain=sp.QQ)
    target_terms = [
        (tuple(map(int, exponents)), Fraction(int(coefficient.p), int(coefficient.q)))
        for exponents, coefficient in target_polynomial.terms()
    ]
    if len(target_terms) != 486 or {sum(exponents) for exponents, _ in target_terms} != {8}:
        raise ValueError("target polynomial changed")
    return columns, descriptors, generator_terms, target_terms


def load_sources(campaign: Path):
    payloads = {}
    bindings = {}
    reference_signature = None
    for prime in PRIMES:
        artifact_path = campaign / SOURCE_ARTIFACTS[prime]
        receipt_path = campaign / SOURCE_RECEIPTS[prime]
        artifact_hash = sha256_bytes(artifact_path.read_bytes())
        receipt_hash = sha256_bytes(receipt_path.read_bytes())
        if (artifact_hash, receipt_hash) != SOURCE_HASHES[prime]:
            raise ValueError(f"source binding changed at p{prime}")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        replay = receipt.get("same_process_sparse_replay", {})
        if (
            int(artifact.get("characteristic", -1)) != prime
            or int(receipt.get("characteristic", -1)) != prime
            or receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
            or not replay.get("completed") or not replay.get("identity_zero")
            or int(replay.get("mismatch_count", -1)) != 0
            or receipt.get("certificate", {}).get("sha256") != artifact_hash
        ):
            raise ValueError(f"source identity is not certified at p{prime}")
        vector = list(map(int, artifact.get("coordinate_vector", [])))
        if len(vector) != 38048 or any(value < 0 or value >= prime for value in vector):
            raise ValueError(f"malformed source vector at p{prime}")
        if canonical_hash(vector) != artifact.get("coordinate_vector_sha256"):
            raise ValueError(f"source vector hash changed at p{prime}")
        free = list(map(int, artifact.get("free_unknown_indices", [])))
        pivots = list(map(int, artifact.get("pivot_unknown_indices", [])))
        if canonical_hash(free) != FREE_HASH or canonical_hash(sorted(pivots)) != PIVOT_SET_HASH:
            raise ValueError(f"fixed-free gauge changed at p{prime}")
        if prime != 181:
            gauge = artifact.get("gauge_source", {})
            if gauge.get("sha256") != SOURCE_HASHES[181][0] or gauge.get("free_unknown_indices_sha256") != FREE_HASH:
                raise ValueError(f"gauge provenance changed at p{prime}")
        signature = {
            key: artifact.get(key)
            for key in (
                "schema", "row_descriptor_sha256", "monomial_stream_sha256",
                "generator_stream_sha256", "target_sha256",
                "free_unknown_indices_sha256", "target_character_weight",
            )
        }
        signature["pivot_unknown_set_sha256"] = canonical_hash(sorted(pivots))
        if reference_signature is None:
            reference_signature = signature
        elif signature != reference_signature:
            raise ValueError(f"problem/gauge signature changed at p{prime}")
        payloads[prime] = {"payload": artifact, "vector": vector}
        bindings[str(prime)] = {
            "role": "fresh_audit_only" if prime == AUDIT_PRIME else "primary",
            "artifact_path": SOURCE_ARTIFACTS[prime],
            "artifact_sha256": artifact_hash,
            "receipt_path": SOURCE_RECEIPTS[prime],
            "receipt_sha256": receipt_hash,
            "coordinate_vector_sha256": artifact["coordinate_vector_sha256"],
        }
    return payloads, bindings, canonical_hash(reference_signature)


def build_minor_rows(columns, coordinates):
    position = {coordinate: index for index, coordinate in enumerate(coordinates)}
    rows = [[] for _ in coordinates]
    for variable, column in enumerate(columns):
        for coordinate, value in column:
            if coordinate in position:
                rows[position[coordinate]].append((variable, value))
    return rows


def solve_minor(integer_rows, rhs_values, prime, started, initial_swaps):
    size = len(integer_rows)
    rows = [{column: value % prime for column, value in row if value % prime} for row in integer_rows]
    rhs = [value % prime for value in rhs_values]
    initial_nnz = sum(map(len, rows))
    maximum_nnz = initial_nnz
    maximum_row = max(map(len, rows))
    determinant = 1
    swaps = updates = 0
    for column in range(size):
        candidates = [row for row in range(column, size) if rows[row].get(column, 0)]
        if not candidates:
            raise ValueError(f"R197 minor is singular at p{prime}, rank below {column + 1}")
        pivot_index = min(candidates, key=lambda row: (len(rows[row]), row))
        if pivot_index != column:
            rows[column], rows[pivot_index] = rows[pivot_index], rows[column]
            rhs[column], rhs[pivot_index] = rhs[pivot_index], rhs[column]
            determinant = -determinant
            swaps += 1
        pivot = rows[column][column]
        determinant = determinant * pivot % prime
        inverse = pow(pivot, -1, prime)
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
            maximum_nnz = max(maximum_nnz, sum(map(len, rows)))
            maximum_row = max(maximum_row, max(map(len, rows)))
            guard(started, initial_swaps, f"minor solve p{prime}")
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
        raise AssertionError(f"minor solve replay failed at p{prime}")
    return solution, {
        "rank": size,
        "determinant_mod_p": determinant % prime,
        "row_swap_count": swaps,
        "coefficient_update_count": updates,
        "initial_nonzero_count": initial_nnz,
        "maximum_sampled_nonzero_count": maximum_nnz,
        "maximum_sampled_row_length": maximum_row,
        "algorithm": "sparse Gaussian elimination of fixed B=K[:,R197]^T with row swaps",
    }


def residue(value: Fraction, prime: int) -> int:
    if value.denominator % prime == 0:
        raise ZeroDivisionError(f"rational input denominator vanishes modulo p{prime}")
    return value.numerator % prime * pow(value.denominator % prime, -1, prime) % prime


def polynomial_image(vector, prime, descriptors, generator_terms):
    modular_terms = [
        [(exponents, residue(coefficient, prime)) for exponents, coefficient in terms]
        for terms in generator_terms
    ]
    image = {}
    updates = 0
    for coordinate, multiplier_value in enumerate(vector):
        if not multiplier_value:
            continue
        generator, multiplier = descriptors[coordinate]
        for exponents, coefficient in modular_terms[generator]:
            product = tuple(a + b for a, b in zip(multiplier, exponents, strict=True))
            updated = (image.get(product, 0) + multiplier_value * coefficient) % prime
            if updated:
                image[product] = updated
            else:
                image.pop(product, None)
            updates += 1
    records = [[list(exponents), value] for exponents, value in sorted(image.items())]
    return image, canonical_hash(records), updates


def normalize_one(prime, source_vector, columns, coordinates, integer_rows, descriptors, generator_terms, target_terms, started, initial_swaps):
    stage_started = time.perf_counter()
    rhs = [(-source_vector[coordinate]) % prime for coordinate in coordinates]
    alpha, solve = solve_minor(integer_rows, rhs, prime, started, initial_swaps)
    if solve["rank"] != 2053 or not solve["determinant_mod_p"]:
        raise ValueError(f"common minor failed at p{prime}")
    difference = [0] * 38048
    combination_updates = 0
    for coefficient, column in zip(alpha, columns, strict=True):
        if not coefficient:
            continue
        for coordinate, value in column:
            difference[coordinate] = (difference[coordinate] + coefficient * value) % prime
            combination_updates += 1
    normalized = [(old + delta) % prime for old, delta in zip(source_vector, difference, strict=True)]
    if any(normalized[coordinate] for coordinate in coordinates):
        raise AssertionError(f"selected zero replay failed at p{prime}")
    if [(new - old) % prime for new, old in zip(normalized, source_vector, strict=True)] != difference:
        raise AssertionError(f"difference replay failed at p{prime}")

    target = {exponents: residue(coefficient, prime) for exponents, coefficient in target_terms}
    target = {key: value for key, value in target.items() if value}
    target_records = [[list(exponents), value] for exponents, value in sorted(target.items())]
    source_image, source_image_hash, source_updates = polynomial_image(source_vector, prime, descriptors, generator_terms)
    difference_image, difference_image_hash, difference_updates = polynomial_image(difference, prime, descriptors, generator_terms)
    normalized_image, normalized_image_hash, normalized_updates = polynomial_image(normalized, prime, descriptors, generator_terms)
    if source_image != target or difference_image or normalized_image != target:
        raise AssertionError(f"direct modular identity replay failed at p{prime}")
    guard(started, initial_swaps, f"direct replay p{prime}")
    artifact = {
        "schema": "hc4.third-colon-koszul-p197-common-minor-normalized-vector.v1",
        "status": "PASS_P197_COMMON_MINOR_NORMALIZED_MODULAR_IDENTITY",
        "characteristic": prime,
        "role": "fresh_audit_only" if prime == AUDIT_PRIME else "primary",
        "claim_boundary": (
            "This artifact proves only one exact modular projection of an already-certified finite-field identity along exact integer Koszul syzygies using the frozen p197-derived common minor. It is not a QQ reconstruction, QQ membership proof, colon, saturation, secant, nullcone, or HC4 result."
        ),
        "source": {
            "artifact_path": SOURCE_ARTIFACTS[prime],
            "artifact_sha256": SOURCE_HASHES[prime][0],
            "receipt_path": SOURCE_RECEIPTS[prime],
            "receipt_sha256": SOURCE_HASHES[prime][1],
            "coordinate_vector_sha256": canonical_hash(source_vector),
        },
        "common_minor": {
            "shape": [2053, 2053],
            "ordered_coordinates": coordinates,
            "ordered_coordinates_sha256": R197_HASH,
            **solve,
        },
        "koszul_coefficient_vector": alpha,
        "koszul_coefficient_vector_sha256": canonical_hash(alpha),
        "koszul_coefficient_support_count": sum(value != 0 for value in alpha),
        "difference_vector": difference,
        "difference_vector_sha256": canonical_hash(difference),
        "difference_support_count": sum(value != 0 for value in difference),
        "normalized_coordinate_vector": normalized,
        "normalized_coordinate_vector_sha256": canonical_hash(normalized),
        "normalized_support_count": sum(value != 0 for value in normalized),
        "direct_replay": {
            "source_image_equals_target": True,
            "difference_image_zero": True,
            "normalized_image_equals_target": True,
            "source_image_sha256": source_image_hash,
            "difference_image_sha256": difference_image_hash,
            "normalized_image_sha256": normalized_image_hash,
            "target_image_sha256": canonical_hash(target_records),
            "source_update_count": source_updates,
            "difference_update_count": difference_updates,
            "normalized_update_count": normalized_updates,
        },
        "checks": {
            "all_2053_selected_coordinates_zero": True,
            "difference_equals_recorded_koszul_combination": True,
            "direct_source_replay_zero_remainder": True,
            "direct_difference_replay_zero_image": True,
            "direct_normalized_replay_zero_remainder": True,
            "combination_update_count": combination_updates,
        },
        "wall_seconds": time.perf_counter() - stage_started,
    }
    return artifact


def run(campaign: Path, started: float, initial_swaps: int):
    for relative, expected in FROZEN_HASHES.items():
        if sha256_bytes((campaign / relative).read_bytes()) != expected:
            raise ValueError(f"frozen input changed: {relative}")
    for prime in PRIMES:
        if sha256_bytes((campaign / SOURCE_ARTIFACTS[prime]).read_bytes()) != SOURCE_HASHES[prime][0]:
            raise ValueError(f"source artifact changed at p{prime}")
        if sha256_bytes((campaign / SOURCE_RECEIPTS[prime]).read_bytes()) != SOURCE_HASHES[prime][1]:
            raise ValueError(f"source receipt changed at p{prime}")
    transfer_telemetry_path = campaign / "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867-telemetry.json"
    transfer_telemetry = json.loads(transfer_telemetry_path.read_text(encoding="utf-8"))
    transfer_gates = transfer_telemetry.get("gates", {})
    if (
        transfer_telemetry.get("status") != "PASS_RESOURCE_GATED_FIXED_FREE_IDENTITY_TRANSFER"
        or int(transfer_telemetry.get("characteristic", -1)) != AUDIT_PRIME
        or int(transfer_telemetry.get("algebra_process_count", -1)) != 1
        or int(transfer_telemetry.get("caps", {}).get("external_wall_seconds", -1)) != 90
        or int(transfer_telemetry.get("caps", {}).get("maximum_rss_bytes", -1)) != 1_500_000_000
        or int(transfer_telemetry.get("external_telemetry", {}).get("process_swaps", -1)) != 0
        or int(transfer_gates.get("identity_replay_mismatch_count", -1)) != 0
        or not all(
            bool(value)
            for key, value in transfer_gates.items()
            if key != "identity_replay_mismatch_count"
        )
        or transfer_telemetry.get("artifact", {}).get("sha256") != SOURCE_HASHES[AUDIT_PRIME][0]
        or transfer_telemetry.get("producer_receipt", {}).get("sha256") != SOURCE_HASHES[AUDIT_PRIME][1]
    ):
        raise ValueError("fresh audit transfer resource telemetry failed")
    sys.path.insert(0, str(campaign / "scripts"))
    if "normalize_j2_secant_r10_third_colon_koszul_fixed_minor" in sys.modules:
        raise AssertionError("stopped normalizer entered runtime")
    import audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit as ind

    build_started = time.perf_counter()
    coordinates = load_r197(campaign)
    columns, descriptors, generator_terms, target_terms = reconstruct(campaign, ind, started, initial_swaps)
    integer_rows = build_minor_rows(columns, coordinates)
    sparse_decimal = [[[column, str(value)] for column, value in row] for row in integer_rows]
    integer_minor_hash = canonical_hash(integer_rows)
    sparse_decimal_hash = canonical_hash(sparse_decimal)
    sources, source_bindings, problem_signature_hash = load_sources(campaign)
    build_seconds = time.perf_counter() - build_started
    guard(started, initial_swaps, "input and common-minor build")

    artifacts = {}
    prime_telemetry = {}
    for prime in PRIMES:
        artifact = normalize_one(
            prime, sources[prime]["vector"], columns, coordinates, integer_rows,
            descriptors, generator_terms, target_terms, started, initial_swaps,
        )
        artifacts[prime] = artifact
        prime_telemetry[str(prime)] = {
            "role": artifact["role"],
            "rank": artifact["common_minor"]["rank"],
            "determinant_mod_p": artifact["common_minor"]["determinant_mod_p"],
            "row_swap_count": artifact["common_minor"]["row_swap_count"],
            "coefficient_vector_sha256": artifact["koszul_coefficient_vector_sha256"],
            "normalized_vector_sha256": artifact["normalized_coordinate_vector_sha256"],
            "difference_vector_sha256": artifact["difference_vector_sha256"],
            "normalized_support_count": artifact["normalized_support_count"],
            "direct_replay": artifact["direct_replay"],
            "wall_seconds": artifact["wall_seconds"],
        }
        gc.collect()
        guard(started, initial_swaps, f"completed p{prime}")

    output_bindings = {}
    for prime in PRIMES:
        relative = f"artifacts/j2-secant-r10-third-colon-koszul-p197-common-minor-normalized-p{prime}.json"
        path = campaign / relative
        path.write_text(json.dumps(artifacts[prime], indent=2, sort_keys=True) + "\n", encoding="ascii")
        output_bindings[str(prime)] = {
            "path": relative,
            "sha256": sha256_bytes(path.read_bytes()),
            "byte_count": path.stat().st_size,
        }
    guard(started, initial_swaps, "artifact freeze")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    final_swaps = int(usage.ru_nswap)
    return {
        "schema": "hc4.third-colon-koszul-p197-common-minor-normalization.v1",
        "status": "PASS_SIX_PRIME_P197_COMMON_MINOR_NORMALIZATION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "confirmatory exact modular common-minor normalization with prospective fresh-audit fibre",
        "claim_boundary": (
            "A PASS proves only that the frozen target-blind p197-derived minor coherently normalized five already-certified primary modular identities and one prospectively fixed audit identity, with direct modular replays. It does not reconstruct QQ multipliers, run or interpret the M70 census, prove QQ membership, compute a colon or saturation, close a secant chart, establish nullcone containment, or prove HC4."
        ),
        "retrospective_feasibility_disclosure": {
            "R197_construction": "retrospective but target-blind",
            "five_primary_minor_invertibility_and_transformed_support_hashes": "retrospective and confirmatory",
            "serialized_normalized_coefficient_values_and_all_CRT_EEA_M70_outcomes": "prospective when opened by this archival producer; feasibility had computed only hashes and support summaries in memory",
            "p173_p197_selector_role": "confirmatory primary selectors; not fully held out",
            "fresh_p2147482867_design_and_outcomes": "prospective audit-only",
            "R197_changed_after_feasibility_observation": False,
        },
        "protocol": {
            "preregistration_path": "research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md",
            "preregistration_sha256": FROZEN_HASHES["research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md"],
            "primary_characteristics": list(PRIMARY_PRIMES),
            "fresh_audit_characteristic": AUDIT_PRIME,
            "stopped_R181_reused": False,
            "alternative_minor_or_prime_searched": False,
            "m70_census_performed": False,
            "fresh_audit_transfer_telemetry": {
                "path": "receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867-telemetry.json",
                "sha256": FROZEN_HASHES["receipts/hsop-j2-secant-r10-third-colon-identity-extended-sparse-p181-transfer-p2147482867-telemetry.json"],
                "external_wall_seconds": transfer_telemetry["external_telemetry"]["real_seconds"],
                "maximum_rss_native_bytes": transfer_telemetry["external_telemetry"]["maximum_rss_native_bytes"],
                "process_swaps": transfer_telemetry["external_telemetry"]["process_swaps"],
                "all_gates_pass": True,
            },
        },
        "dimensions": {
            "koszul_matrix_shape": [2053, 38048],
            "koszul_nonzero_count": sum(map(len, columns)),
            "fixed_common_minor_shape": [2053, 2053],
            "fixed_common_minor_nonzero_count": sum(map(len, integer_rows)),
        },
        "hashes": {
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "frozen_inputs": FROZEN_HASHES,
            "source_identities": source_bindings,
            "problem_signature_sha256": problem_signature_hash,
            "descriptor_stream_sha256": DESCRIPTOR_HASH,
            "integer_koszul_stream_sha256": K_HASH,
            "ordered_R197_sha256": canonical_hash(coordinates),
            "fixed_integer_B_sha256": integer_minor_hash,
            "fixed_sparse_decimal_B_sha256": sparse_decimal_hash,
            "normalized_artifacts": output_bindings,
        },
        "ordered_R197": coordinates,
        "prime_telemetry": prime_telemetry,
        "checks": {
            "all_six_ranks_equal_2053": all(record["rank"] == 2053 for record in prime_telemetry.values()),
            "all_six_determinants_nonzero": all(record["determinant_mod_p"] for record in prime_telemetry.values()),
            "all_six_selected_coordinate_sets_zero": True,
            "all_six_differences_exact_koszul_combinations": True,
            "all_eighteen_direct_source_difference_normalized_replays_pass": True,
            "all_six_problem_and_gauge_streams_identical": True,
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
            "input_koszul_common_minor_build_seconds": build_seconds,
            "total_wall_seconds": time.perf_counter() - started,
        },
    }


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-normalization.json"
    signal.signal(signal.SIGALRM, lambda _signum, _frame: (_ for _ in ()).throw(TimeoutError("180-second alarm")))
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        receipt = run(campaign, started, initial_swaps)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": receipt["status"], "output": str(output), "wall_seconds": receipt["timings"]["total_wall_seconds"]}, sort_keys=True))
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-p197-common-minor-normalization.v1",
            "status": "FAIL_CLOSED_P197_COMMON_MINOR_NORMALIZATION",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": "No normalized artifact, census result, rational reconstruction, QQ identity, colon, saturation, secant, nullcone, or HC4 conclusion is licensed by this failed run.",
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "preregistration_sha256": FROZEN_HASHES["research/THIRD_COLON_KOSZUL_P197_COMMON_MINOR_NORMALIZATION_PREREGISTRATION.md"],
            "normalized_artifacts_written": False,
            "m70_census_performed": False,
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
