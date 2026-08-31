#!/usr/bin/env -S sage -python
"""Build the canonical primitive integer system for the fixed-p181 pilot.

This process may read both coefficients and RHS.  It performs no elimination
and no arithmetic modulo 181^2.  Its output remains staged until the separate
coefficient-only factorizer and wrapper gates pass.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import resource
import struct
import sys
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    THIRD_CANDIDATE,
    canonical_hash,
    load_third_quartic,
)
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    character_weight,
    exact_exponent_tuples,
)
from fixed_p181_dixon_codec import (
    ArrayPayload,
    encode_bigint,
    payload_bigints,
    payload_u32,
    payload_u64,
    sha256_bytes,
    write_container,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


PRIMARY_ARTIFACT = Path(
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
)
PRIMARY_ARTIFACT_SHA256 = (
    "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b"
)
EXPECTED_HASHES = {
    "row_descriptor_sha256": (
        "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
    ),
    "monomial_stream_sha256": (
        "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614"
    ),
    "generator_stream_sha256": (
        "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
    ),
    "target_sha256": (
        "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
    ),
}
EXPECTED_LEGACY = {
    "C_piv": "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d",
    "F": "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1",
    "d_0": "9932deed637ea317b4483cad9366e1fd1455be7453bc74a64ce78f04c4f57919",
}
FREEZE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
    "implementation-freeze.v3"
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compact_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    )


def rational_pair(value: object) -> tuple[int, int]:
    rational = sp.Rational(value)
    return int(rational.p), int(rational.q)


def add_pairs(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    value = Fraction(left[0], left[1]) + Fraction(right[0], right[1])
    return value.numerator, value.denominator


def build_rational_block(campaign: Path) -> dict[str, object]:
    started = time.perf_counter()
    equations, variables, _leading_form, open_factor = homogeneous_saturation_system()
    first_quartic, first_metadata = reconstruct_quartic(campaign, variables)
    second_quartic, second_metadata = load_second_quartic(campaign, variables)
    third_quartic, third_metadata = load_third_quartic(campaign, variables)
    generators = list(equations) + [first_quartic, second_quartic]
    generator_degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * third_quartic)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    require(target_polynomial.total_degree() == 8, "target is not degree eight")

    polynomial_terms = []
    generator_weights = []
    for position, (generator, expected_degree) in enumerate(
        zip(generators, generator_degrees, strict=True)
    ):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), rational_pair(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        weights = {character_weight(exponents) for exponents, _ in terms}
        degrees = {sum(exponents) for exponents, _ in terms}
        require(
            len(weights) == 1 and degrees == {expected_degree},
            f"generator {position} left its block",
        )
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
    require(generator_weights[-2:] == [4, 3], "adjoined characters changed")

    target_terms = [
        (tuple(map(int, exponents)), rational_pair(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    require(
        {character_weight(exponents) for exponents, _ in target_terms} == {3},
        "target character changed",
    )
    target_weight = 3

    pools = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)

    coefficient_ids: dict[tuple[int, int], int] = {}
    coefficient_values: list[tuple[int, int]] = []

    def intern(pair: tuple[int, int]) -> int:
        if pair not in coefficient_ids:
            coefficient_ids[pair] = len(coefficient_values)
            coefficient_values.append(pair)
        return coefficient_ids[pair]

    equation_by_monomial: dict[tuple[int, ...], dict[int, int]] = {}
    descriptors = []
    collision_additions = 0
    for generator_index, (terms, generator_weight, multiplier_degree) in enumerate(
        zip(polynomial_terms, generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        for multiplier in pools.get((multiplier_degree, multiplier_weight), []):
            unknown_index = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(
                    left + right
                    for left, right in zip(exponents, multiplier, strict=True)
                )
                require(
                    character_weight(product) == target_weight and sum(product) == 8,
                    "Macaulay contribution left selected block",
                )
                row = equation_by_monomial.setdefault(product, {})
                if unknown_index in row:
                    collision_additions += 1
                    combined = add_pairs(coefficient_values[row[unknown_index]], pair)
                    if combined[0] == 0:
                        del row[unknown_index]
                    else:
                        row[unknown_index] = intern(combined)
                else:
                    row[unknown_index] = intern(pair)

    target_by_monomial = {exponents: pair for exponents, pair in target_terms}
    for exponents in target_by_monomial:
        equation_by_monomial.setdefault(exponents, {})
    monomials = sorted(equation_by_monomial)
    rows = [equation_by_monomial[monomial] for monomial in monomials]
    rhs = [target_by_monomial.get(monomial, (0, 1)) for monomial in monomials]
    require(len(descriptors) == 38_048, "descriptor count changed")
    return {
        "variables": variables,
        "generators": generators,
        "target_expression": target_expression,
        "target_polynomial": target_polynomial,
        "first_metadata": first_metadata,
        "second_metadata": second_metadata,
        "third_metadata": third_metadata,
        "generator_degrees": generator_degrees,
        "multiplier_degrees": multiplier_degrees,
        "generator_weights": generator_weights,
        "target_weight": target_weight,
        "descriptors": descriptors,
        "monomials": monomials,
        "rows": rows,
        "rhs": rhs,
        "coefficient_values": coefficient_values,
        "collision_additions": collision_additions,
        "build_seconds": time.perf_counter() - started,
    }


def primitive_integer_row(
    row: dict[int, int],
    rhs: tuple[int, int],
    coefficient_values: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], int]:
    entries = [(column, coefficient_values[index]) for column, index in sorted(row.items())]
    denominators = [pair[1] for _column, pair in entries] + [rhs[1]]
    denominator_lcm = math.lcm(*denominators)
    integer_entries = [
        (column, pair[0] * (denominator_lcm // pair[1]))
        for column, pair in entries
    ]
    integer_rhs = rhs[0] * (denominator_lcm // rhs[1])
    nonzero_values = [abs(value) for _column, value in integer_entries if value]
    if integer_rhs:
        nonzero_values.append(abs(integer_rhs))
    require(nonzero_values, "all-zero primitive row")
    content = math.gcd(*nonzero_values)
    integer_entries = [
        (column, value // content) for column, value in integer_entries if value
    ]
    integer_rhs //= content
    first_value = integer_entries[0][1] if integer_entries else integer_rhs
    if first_value < 0:
        integer_entries = [(column, -value) for column, value in integer_entries]
        integer_rhs = -integer_rhs
    return integer_entries, integer_rhs


def verify_freeze(campaign: Path, path: Path) -> dict[str, object]:
    if not path.is_absolute():
        path = campaign / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(payload.get("schema") == FREEZE_SCHEMA, "implementation freeze schema changed")
    require(payload.get("status") == "PASS_IMPLEMENTATION_FREEZE", "implementation not frozen")
    relative_script = str(Path(__file__).resolve().relative_to(campaign))
    require(
        payload["implementation_sources"][relative_script] == file_hash(Path(__file__).resolve()),
        "preprocessor source differs from freeze",
    )
    return {"path": str(path), "sha256": file_hash(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--implementation-freeze", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    campaign = Path(__file__).resolve().parents[1]
    freeze = verify_freeze(campaign, arguments.implementation_freeze)
    staging = arguments.staging_dir
    if not staging.is_absolute():
        staging = campaign / staging
    staging.mkdir(parents=True, exist_ok=False)

    primary_path = campaign / PRIMARY_ARTIFACT
    require(file_hash(primary_path) == PRIMARY_ARTIFACT_SHA256, "primary artifact drift")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    pivots = list(map(int, primary["pivot_unknown_indices"]))
    free = list(map(int, primary["free_unknown_indices"]))
    d0 = list(map(int, primary["coordinate_vector"]))
    require(compact_hash(pivots) == EXPECTED_LEGACY["C_piv"], "C_piv hash drift")
    require(compact_hash(free) == EXPECTED_LEGACY["F"], "F hash drift")
    require(compact_hash(d0) == EXPECTED_LEGACY["d_0"], "d0 hash drift")
    require(sorted(pivots + free) == list(range(38_048)), "gauge coverage drift")
    require(not set(pivots).intersection(free), "gauge overlap")
    require(all(d0[index] == 0 for index in free), "d0 violates x_F=0")

    block = build_rational_block(campaign)
    descriptor_hash = canonical_hash(block["descriptors"])
    monomial_hash = canonical_hash(block["monomials"])
    generator_hash = digest(tuple(block["generators"]))
    target_hash = digest((block["target_expression"],))
    observed_hashes = {
        "row_descriptor_sha256": descriptor_hash,
        "monomial_stream_sha256": monomial_hash,
        "generator_stream_sha256": generator_hash,
        "target_sha256": target_hash,
    }
    require(observed_hashes == EXPECTED_HASHES, "rational block hash drift")
    require(len(block["rows"]) == 85_651, "row count changed")
    require(sum(map(len, block["rows"])) == 1_473_071, "rational nnz changed")
    require(len(block["target_polynomial"].terms()) == 486, "target support changed")

    global_to_local = {global_index: local for local, global_index in enumerate(pivots)}
    row_offsets = [0]
    columns = []
    values = []
    rhs_values = []
    c_row_offsets = [0]
    c_columns = []
    c_values = []
    combined = bytearray(struct.pack("<Q", len(block["rows"])))
    modular_mismatch_count = 0
    maximum_bit_length = 0
    normalization_started = time.perf_counter()
    for row_index, (row, rhs) in enumerate(zip(block["rows"], block["rhs"], strict=True)):
        integer_entries, integer_rhs = primitive_integer_row(
            row, rhs, block["coefficient_values"]
        )
        combined.extend(struct.pack("<IQ", row_index, len(integer_entries)))
        modular_left = 0
        local_entries = []
        for column, value in integer_entries:
            columns.append(column)
            values.append(value)
            combined.extend(struct.pack("<I", column))
            combined.extend(encode_bigint(value))
            maximum_bit_length = max(maximum_bit_length, abs(value).bit_length())
            modular_left = (modular_left + (value % 181) * d0[column]) % 181
            local = global_to_local.get(column)
            if local is not None:
                local_entries.append((local, value))
        for local, value in sorted(local_entries):
            c_columns.append(local)
            c_values.append(value)
        rhs_values.append(integer_rhs)
        combined.extend(encode_bigint(integer_rhs))
        maximum_bit_length = max(maximum_bit_length, abs(integer_rhs).bit_length())
        row_offsets.append(len(columns))
        c_row_offsets.append(len(c_columns))
        if modular_left != integer_rhs % 181:
            modular_mismatch_count += 1
    require(len(columns) == 1_473_071, "primitive A_Z nnz changed")
    require(modular_mismatch_count == 0, "known p181 vector failed primitive system")
    normalization_seconds = time.perf_counter() - normalization_started

    # Release the construction dictionaries before materializing binary payloads.
    build_seconds = block["build_seconds"]
    collision_additions = block["collision_additions"]
    del block
    gc.collect()

    arrays = {
        "A_C.column_indices": ArrayPayload("u32", (len(c_columns),), payload_u32(c_columns)),
        "A_C.row_offsets": ArrayPayload("u64", (len(c_row_offsets),), payload_u64(c_row_offsets)),
        "A_C.values": ArrayPayload("bigint", (len(c_values),), payload_bigints(c_values)),
        "A_Z.column_indices": ArrayPayload("u32", (len(columns),), payload_u32(columns)),
        "A_Z.row_offsets": ArrayPayload("u64", (len(row_offsets),), payload_u64(row_offsets)),
        "A_Z.values": ArrayPayload("bigint", (len(values),), payload_bigints(values)),
        "C_piv": ArrayPayload("u32", (len(pivots),), payload_u32(pivots)),
        "F": ArrayPayload("u32", (len(free),), payload_u32(free)),
        "b_Z": ArrayPayload("bigint", (len(rhs_values),), payload_bigints(rhs_values)),
        "combined_rows": ArrayPayload("bytes", (len(combined),), bytes(combined)),
        "d_0": ArrayPayload("u8", (len(d0),), bytes(d0)),
    }
    binary_path = staging / "integer-system.bin"
    container = write_container(binary_path, arrays)
    receipt = {
        "schema": (
            "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
            "integer-system.v1"
        ),
        "status": "PASS_STAGED_CANONICAL_INTEGER_SYSTEM",
        "implementation_freeze": freeze,
        "primary_artifact": {
            "path": str(PRIMARY_ARTIFACT),
            "sha256": PRIMARY_ARTIFACT_SHA256,
        },
        "legacy_hashes": EXPECTED_LEGACY,
        "algebra_hashes": observed_hashes,
        "dimensions": {
            "rows": len(rhs_values),
            "global_columns": 38_048,
            "A_Z_nonzeros": len(columns),
            "C_columns": len(pivots),
            "F_columns": len(free),
            "A_C_nonzeros": len(c_columns),
            "target_terms": 486,
            "generators": 19,
        },
        "normalization": {
            "policy": "row lcm, positive content gcd, first-nonzero positive",
            "maximum_integer_bit_length": maximum_bit_length,
            "collision_additions": collision_additions,
            "known_p181_vector_mismatch_count": modular_mismatch_count,
        },
        "container": container,
        "timings": {
            "rational_block_build_seconds": build_seconds,
            "primitive_normalization_seconds": normalization_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "resources": {
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(campaign)),
            "sha256": file_hash(Path(__file__).resolve()),
            "python": sys.version,
        },
        "declarations": {
            "preprocessing_only": True,
            "rhs_read": True,
            "no_elimination": True,
            "no_arithmetic_modulo_181_squared": True,
            "staged_not_promoted": True,
        },
        "claim_boundary": (
            "This staged PASS constructs only the canonical integer coefficient "
            "system and verifies the already-known digit-zero vector modulo 181. "
            "It proves no factorization, lift, QQ identity, ideal membership, "
            "colon, saturation, secant closure, nullcone containment, or HC4."
        ),
    }
    receipt_path = staging / "integer-system.json"
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": receipt["status"], "staging": str(staging)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
