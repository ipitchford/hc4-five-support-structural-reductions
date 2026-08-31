#!/usr/bin/env -S sage -python
"""Second implementation for the fixed-p181 eight-digit Dixon pilot.

The module deliberately does not import the producer, preprocessor, or
factorizer.  It reconstructs the rational Macaulay block, independently
normalizes every row, verifies the frozen elimination trace row by row, and
then repeats the eight exact Dixon recurrences.
"""

from __future__ import annotations

import argparse
import array
import gc
import hashlib
import json
import math
import os
import resource
import struct
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import load_second_quartic
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
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
    decode_bigints,
    encode_bigint,
    payload_bigints,
    read_array,
    read_descriptors,
    sha256_bytes,
    write_container,
)
from fixed_p181_dixon_rr import (
    AMBIGUOUS,
    NO_CANDIDATE,
    UNIQUE_NONZERO,
    UNIQUE_ZERO,
    classify,
    regression,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


P = 181
DIGITS = 8
ROWS = 85_651
GLOBAL_COLUMNS = 38_048
C_COLUMNS = 35_881
F_COLUMNS = 2_167
TERMINAL_MODULUS = 1_151_936_657_823_500_641
EXPECTED_INTERNAL_HASHES = {
    "row_descriptor_sha256": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomial_stream_sha256": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generator_stream_sha256": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
    "target_sha256": "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e",
}
EXPECTED_LEGACY = {
    "C_piv": "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d",
    "F": "2da8418faa5f04e82a5eb6da88268f4e025279fd0dd348d8674cb89c8d0cf8d1",
    "d_0": "9932deed637ea317b4483cad9366e1fd1455be7453bc74a64ce78f04c4f57919",
}
FREEZE_SCHEMA = "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-implementation-freeze.v3"
INDEX_SCHEMA = "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-factorization-freeze.v3"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return sha256_bytes(raw)


def packed(payload: bytes, typecode: str) -> array.array:
    result = array.array(typecode)
    result.frombytes(payload)
    if sys.byteorder != "little":
        result.byteswap()
    return result


def get_payload(path: Path, name: str) -> tuple[bytes, tuple[int, ...]]:
    descriptors = read_descriptors(path)
    require(name in descriptors, f"missing array {name}")
    descriptor = descriptors[name]
    return read_array(path, descriptor), descriptor.shape


def get_u32(path: Path, name: str) -> array.array:
    return packed(get_payload(path, name)[0], "I")


def get_u64(path: Path, name: str) -> array.array:
    return packed(get_payload(path, name)[0], "Q")


def get_u8(path: Path, name: str) -> bytes:
    payload, shape = get_payload(path, name)
    require(len(shape) == 1 and len(payload) == shape[0], f"{name} shape drift")
    return payload


def get_bigints(path: Path, name: str) -> list[int]:
    payload, shape = get_payload(path, name)
    require(len(shape) == 1, f"{name} is not a vector")
    return decode_bigints(payload, shape[0])


def rational_pair(value: object) -> tuple[int, int]:
    value = sp.Rational(value)
    return int(value.p), int(value.q)


def add_pairs(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    value = Fraction(*left) + Fraction(*right)
    return value.numerator, value.denominator


def reconstruct_block(campaign: Path) -> dict[str, object]:
    equations, variables, _leading, open_factor = homogeneous_saturation_system()
    first, _first_meta = reconstruct_quartic(campaign, variables)
    second, _second_meta = load_second_quartic(campaign, variables)
    third, _third_meta = load_third_quartic(campaign, variables)
    generators = list(equations) + [first, second]
    generator_degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    target_expression = sp.expand(open_factor * third)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)

    term_tables = []
    generator_weights = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), rational_pair(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        require({sum(item[0]) for item in terms} == {expected_degree}, "generator degree drift")
        weights = {character_weight(item[0]) for item in terms}
        require(len(weights) == 1, "generator character drift")
        term_tables.append(terms)
        generator_weights.append(next(iter(weights)))
    require(generator_weights[-2:] == [4, 3], "adjoined quartic character drift")

    target_terms = [
        (tuple(map(int, exponents)), rational_pair(coefficient))
        for exponents, coefficient in target_polynomial.terms()
    ]
    require({character_weight(item[0]) for item in target_terms} == {3}, "target character drift")
    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in set(multiplier_degrees):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)

    coefficient_ids: dict[tuple[int, int], int] = {}
    coefficient_values: list[tuple[int, int]] = []

    def intern(pair: tuple[int, int]) -> int:
        if pair not in coefficient_ids:
            coefficient_ids[pair] = len(coefficient_values)
            coefficient_values.append(pair)
        return coefficient_ids[pair]

    rows_by_monomial: dict[tuple[int, ...], dict[int, int]] = {}
    descriptors = []
    for generator_index, (terms, weight, degree) in enumerate(
        zip(term_tables, generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (3 - weight) % CHARACTER_MODULUS
        for multiplier in pools.get((degree, multiplier_weight), []):
            coordinate = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(a + b for a, b in zip(exponents, multiplier, strict=True))
                row = rows_by_monomial.setdefault(product, {})
                if coordinate in row:
                    combined = add_pairs(coefficient_values[row[coordinate]], pair)
                    if combined[0]:
                        row[coordinate] = intern(combined)
                    else:
                        del row[coordinate]
                else:
                    row[coordinate] = intern(pair)
    target_map = dict(target_terms)
    for monomial in target_map:
        rows_by_monomial.setdefault(monomial, {})
    monomials = sorted(rows_by_monomial)
    require(len(descriptors) == GLOBAL_COLUMNS and len(monomials) == ROWS, "block dimensions drift")
    observed = {
        "row_descriptor_sha256": canonical_hash(descriptors),
        "monomial_stream_sha256": canonical_hash(monomials),
        "generator_stream_sha256": digest(tuple(generators)),
        "target_sha256": digest((target_expression,)),
    }
    require(observed == EXPECTED_INTERNAL_HASHES, "independent algebra hash drift")
    return {
        "rows": [rows_by_monomial[item] for item in monomials],
        "rhs": [target_map.get(item, (0, 1)) for item in monomials],
        "coefficients": coefficient_values,
        "observed_hashes": observed,
        "target_terms": len(target_terms),
        "generator_count": len(generators),
    }


def normalize_row(
    row: dict[int, int], rhs: tuple[int, int], coefficients: list[tuple[int, int]]
) -> tuple[list[tuple[int, int]], int]:
    entries = [(column, coefficients[index]) for column, index in sorted(row.items())]
    denominator = math.lcm(*(pair[1] for _column, pair in entries), rhs[1])
    integer_entries = [
        (column, pair[0] * (denominator // pair[1])) for column, pair in entries
    ]
    integer_rhs = rhs[0] * (denominator // rhs[1])
    content_values = [abs(value) for _column, value in integer_entries if value]
    if integer_rhs:
        content_values.append(abs(integer_rhs))
    require(content_values, "all-zero normalized row")
    content = math.gcd(*content_values)
    integer_entries = [(column, value // content) for column, value in integer_entries if value]
    integer_rhs //= content
    first = integer_entries[0][1] if integer_entries else integer_rhs
    if first < 0:
        integer_entries = [(column, -value) for column, value in integer_entries]
        integer_rhs = -integer_rhs
    return integer_entries, integer_rhs


def reconstruct_integer_arrays(
    campaign: Path, integer_path: Path, pivots: list[int]
) -> dict[str, object]:
    """Rebuild every primitive row and compare exact binary payload digests."""

    expected = read_descriptors(integer_path)
    block = reconstruct_block(campaign)
    global_to_local = {coordinate: local for local, coordinate in enumerate(pivots)}
    a_row_offsets = array.array("Q", [0])
    a_columns = array.array("I")
    a_values: list[int] = []
    c_row_offsets = array.array("Q", [0])
    c_columns = array.array("I")
    c_values: list[int] = []
    rhs_values: list[int] = []
    hashes = {name: hashlib.sha256() for name in (
        "A_Z.column_indices", "A_Z.values", "A_C.column_indices", "A_C.values",
        "b_Z", "combined_rows"
    )}
    hashes["combined_rows"].update(struct.pack("<Q", ROWS))
    nnz = 0
    for row_index, (row, rhs) in enumerate(zip(block["rows"], block["rhs"], strict=True)):
        entries, integer_rhs = normalize_row(row, rhs, block["coefficients"])
        hashes["combined_rows"].update(struct.pack("<IQ", row_index, len(entries)))
        local_entries = []
        for coordinate, value in entries:
            a_columns.append(coordinate)
            a_values.append(value)
            hashes["A_Z.column_indices"].update(struct.pack("<I", coordinate))
            encoded = encode_bigint(value)
            hashes["A_Z.values"].update(encoded)
            hashes["combined_rows"].update(struct.pack("<I", coordinate) + encoded)
            local = global_to_local.get(coordinate)
            if local is not None:
                local_entries.append((local, value))
        for local, value in sorted(local_entries):
            c_columns.append(local)
            c_values.append(value)
            hashes["A_C.column_indices"].update(struct.pack("<I", local))
            hashes["A_C.values"].update(encode_bigint(value))
        rhs_values.append(integer_rhs)
        encoded_rhs = encode_bigint(integer_rhs)
        hashes["b_Z"].update(encoded_rhs)
        hashes["combined_rows"].update(encoded_rhs)
        nnz += len(entries)
        a_row_offsets.append(nnz)
        c_row_offsets.append(len(c_columns))
    require(nnz == 1_473_071 and block["target_terms"] == 486 and block["generator_count"] == 19, "support dimensions drift")
    if sys.byteorder != "little":
        a_row_offsets.byteswap(); a_columns.byteswap(); c_row_offsets.byteswap(); c_columns.byteswap()
    observed = {
        **{name: value.hexdigest() for name, value in hashes.items()},
        "A_Z.row_offsets": sha256_bytes(a_row_offsets.tobytes()),
        "A_C.row_offsets": sha256_bytes(c_row_offsets.tobytes()),
    }
    for name, digest_value in observed.items():
        require(expected[name].sha256 == digest_value, f"independent payload mismatch: {name}")
    del block
    gc.collect()
    return {
        "A_Z.row_offsets": a_row_offsets,
        "A_Z.column_indices": a_columns,
        "A_Z.values": a_values,
        "A_C.row_offsets": c_row_offsets,
        "A_C.column_indices": c_columns,
        "A_C.values": c_values,
        "b_Z": rhs_values,
        "payload_hashes": observed,
    }


def build_row_events(trace: dict[str, object]) -> tuple[array.array, array.array, bytes]:
    counts = array.array("Q", [0]) * (ROWS + 1)
    for row in trace["affected_rows"]:
        counts[row + 1] += 1
    for row in range(ROWS):
        counts[row + 1] += counts[row]
    event_pivots = array.array("I", [0]) * len(trace["affected_rows"])
    event_factors = bytearray(len(trace["affected_rows"]))
    cursors = array.array("Q", counts[:-1])
    for pivot in range(C_COLUMNS):
        for position in range(trace["affected_offsets"][pivot], trace["affected_offsets"][pivot + 1]):
            row = trace["affected_rows"][position]
            target = cursors[row]
            event_pivots[target] = pivot
            event_factors[target] = trace["affected_factors"][position]
            cursors[row] += 1
    return counts, event_pivots, bytes(event_factors)


def verify_trace_rowwise(
    arrays: dict[str, object], trace: dict[str, object]
) -> dict[str, object]:
    """Verify every elimination event while holding only one filled row."""

    event_offsets, event_pivots, event_factors = build_row_events(trace)
    pivot_time_by_row = [-1] * ROWS
    for t, row in enumerate(trace["pivot_source_row"]):
        require(pivot_time_by_row[row] == -1, "pivot source row repeated")
        pivot_time_by_row[row] = t
    best: list[tuple[int, int] | None] = [None] * C_COLUMNS
    verified_events = 0
    maximum_live_row = 0
    for row_index in range(ROWS):
        row = {
            arrays["A_C.column_indices"][position]: arrays["A_C.values"][position] % P
            for position in range(
                arrays["A_C.row_offsets"][row_index],
                arrays["A_C.row_offsets"][row_index + 1],
            )
        }
        maximum_live_row = max(maximum_live_row, len(row))
        pivot_time = pivot_time_by_row[row_index]
        previous_event = -1
        for event_position in range(event_offsets[row_index], event_offsets[row_index + 1]):
            t = event_pivots[event_position]
            factor = event_factors[event_position]
            require(t > previous_event and (pivot_time < 0 or t < pivot_time), "row event order drift")
            require(row and min(row) == t and row[t] == factor, "stored affected factor is false")
            candidate = (len(row), row_index)
            best[t] = candidate if best[t] is None or candidate < best[t] else best[t]
            del row[t]
            for position in range(trace["pivot_tail_offsets"][t], trace["pivot_tail_offsets"][t + 1]):
                column = trace["pivot_tail_columns"][position]
                value = (row.get(column, 0) - factor * trace["pivot_tail_values"][position]) % P
                if value:
                    row[column] = value
                elif column in row:
                    del row[column]
            previous_event = t
            verified_events += 1
            maximum_live_row = max(maximum_live_row, len(row))
        if pivot_time >= 0:
            t = pivot_time
            require(row and min(row) == t and row[t] != 0, "pivot row state is false")
            candidate = (len(row), row_index)
            best[t] = candidate if best[t] is None or candidate < best[t] else best[t]
            inverse = pow(row[t], -1, P)
            require(inverse == trace["pivot_inverse"][t], "pivot inverse drift")
            observed_tail = sorted(
                (column, value * inverse % P) for column, value in row.items() if column != t
            )
            start, end = trace["pivot_tail_offsets"][t], trace["pivot_tail_offsets"][t + 1]
            expected_tail = list(zip(trace["pivot_tail_columns"][start:end], trace["pivot_tail_values"][start:end], strict=True))
            require(observed_tail == expected_tail, "normalized pivot tail drift")
        else:
            require(not row, "final zero row retains a coefficient")
    for t in range(C_COLUMNS):
        require(best[t] is not None and best[t][1] == trace["pivot_source_row"][t], "deterministic pivot-choice rule drift")
    require(verified_events == len(trace["affected_rows"]), "not every trace event was verified")
    require(
        sorted(index for index, value in enumerate(pivot_time_by_row) if value < 0)
        == list(trace["final_zero_rows"]),
        "final zero row set drift",
    )
    return {
        "affected_events_verified": verified_events,
        "pivot_rows_verified": C_COLUMNS,
        "deterministic_pivot_choices_verified": C_COLUMNS,
        "maximum_single_live_row_length": maximum_live_row,
        "global_fill_matrix_materialized": False,
    }


def solve_trace(rhs: list[int], trace: dict[str, object]) -> tuple[list[int], bytes]:
    rho = [value % P for value in rhs]
    eta = [0] * C_COLUMNS
    for t in range(C_COLUMNS):
        value = rho[trace["pivot_source_row"][t]] * trace["pivot_inverse"][t] % P
        eta[t] = value
        for position in range(trace["affected_offsets"][t], trace["affected_offsets"][t + 1]):
            row = trace["affected_rows"][position]
            rho[row] = (rho[row] - trace["affected_factors"][position] * value) % P
    zero = bytes(rho[row] for row in trace["final_zero_rows"])
    require(not any(zero), "independent transformed zero-row test failed")
    digit = [0] * C_COLUMNS
    for t in range(C_COLUMNS - 1, -1, -1):
        value = eta[t]
        for position in range(trace["pivot_tail_offsets"][t], trace["pivot_tail_offsets"][t + 1]):
            value -= trace["pivot_tail_values"][position] * digit[trace["pivot_tail_columns"][position]]
        digit[t] = value % P
    return digit, zero


def matvec(row_offsets: object, columns: object, values: list[int], vector: list[int]) -> list[int]:
    result = [0] * ROWS
    for row in range(ROWS):
        result[row] = sum(
            values[position] * vector[columns[position]]
            for position in range(row_offsets[row], row_offsets[row + 1])
        )
    return result


def rr_labels(values: list[int], modulus: int) -> tuple[bytes, dict[str, int]]:
    labels = bytearray()
    counts: Counter[int] = Counter()
    divisions = convergents = retained = 0
    for value in values:
        outcome = classify(value % modulus, modulus)
        labels.append(outcome.label); counts[outcome.label] += 1
        divisions += outcome.euclidean_divisions
        convergents += outcome.convergents_tested
        retained += len(outcome.candidates)
    return bytes(labels), {
        "NO_CANDIDATE": counts[NO_CANDIDATE],
        "UNIQUE_ZERO": counts[UNIQUE_ZERO],
        "UNIQUE_NONZERO": counts[UNIQUE_NONZERO],
        "AMBIGUOUS": counts[AMBIGUOUS],
        "total_euclidean_divisions": divisions,
        "total_convergents_tested": convergents,
        "candidates_retained": retained,
    }


def compare_payload(producer_path: Path, name: str, payload: bytes) -> None:
    descriptors = read_descriptors(producer_path)
    require(name in descriptors, f"producer omitted {name}")
    require(descriptors[name].sha256 == sha256_bytes(payload), f"producer disagreement: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--implementation-freeze", type=Path, required=True)
    parser.add_argument("--factorization-freeze", type=Path, required=True)
    parser.add_argument("--producer-dir", type=Path, required=True)
    args = parser.parse_args()
    campaign = Path(__file__).resolve().parents[1]
    staging = args.staging_dir if args.staging_dir.is_absolute() else campaign / args.staging_dir
    staging.mkdir(parents=True, exist_ok=False)
    implementation_path = args.implementation_freeze if args.implementation_freeze.is_absolute() else campaign / args.implementation_freeze
    index_path = args.factorization_freeze if args.factorization_freeze.is_absolute() else campaign / args.factorization_freeze
    producer_dir = args.producer_dir if args.producer_dir.is_absolute() else campaign / args.producer_dir
    started = time.perf_counter()

    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    require(implementation.get("schema") == FREEZE_SCHEMA and implementation.get("status") == "PASS_IMPLEMENTATION_FREEZE", "implementation freeze invalid")
    relative = str(Path(__file__).resolve().relative_to(campaign))
    require(implementation["implementation_sources"].get(relative) == file_hash(Path(__file__).resolve()), "independent source is not frozen")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    require(index.get("schema") == INDEX_SCHEMA and index.get("status") == "PASS_FACTORIZATION_FREEZE", "factorization freeze invalid")
    require(index["implementation_freeze"]["sha256"] == file_hash(implementation_path), "freeze chain drift")
    bundle = campaign / index["bundle"]["path"]
    for name, expected in index["bundle"]["files"].items():
        require(file_hash(bundle / name) == expected, f"Phase-I bundle drift: {name}")
    producer_receipt_path = producer_dir / "producer-digits.json"
    producer_path = producer_dir / "producer-digits.bin"
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    require(producer_receipt.get("status") == "PASS_PRODUCER_FIXED_P181_DIXON_8DIGIT_PILOT", "producer did not pass")
    require(producer_receipt["container"]["sha256"] == file_hash(producer_path), "producer container drift")

    integer_path = bundle / "integer-system.bin"
    factor_path = bundle / "factorization.bin"
    primary = json.loads((campaign / "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json").read_text(encoding="utf-8"))
    pivots = list(map(int, primary["pivot_unknown_indices"]))
    free = list(map(int, primary["free_unknown_indices"]))
    d0_full = list(map(int, primary["coordinate_vector"]))
    require(compact_hash(pivots) == EXPECTED_LEGACY["C_piv"] and compact_hash(free) == EXPECTED_LEGACY["F"] and compact_hash(d0_full) == EXPECTED_LEGACY["d_0"], "legacy gauge drift")
    require(sorted(pivots + free) == list(range(GLOBAL_COLUMNS)) and all(d0_full[index] == 0 for index in free), "zero-free gauge drift")
    integer_descriptors = read_descriptors(integer_path)
    require(
        integer_descriptors["C_piv"].sha256
        == sha256_bytes(b"".join(struct.pack("<I", value) for value in pivots)),
        "independently loaded C_piv binary payload drift",
    )
    require(
        integer_descriptors["F"].sha256
        == sha256_bytes(b"".join(struct.pack("<I", value) for value in free)),
        "independently loaded F binary payload drift",
    )
    require(
        integer_descriptors["d_0"].sha256 == sha256_bytes(bytes(d0_full)),
        "independently loaded d_0 binary payload drift",
    )
    rebuilt = reconstruct_integer_arrays(campaign, integer_path, pivots)

    trace = {
        "pivot_source_row": get_u32(factor_path, "pivot_source_row"),
        "pivot_unknown": get_u32(factor_path, "pivot_unknown"),
        "pivot_inverse": get_u8(factor_path, "pivot_inverse"),
        "pivot_tail_offsets": get_u64(factor_path, "pivot_tail_offsets"),
        "pivot_tail_columns": get_u32(factor_path, "pivot_tail_columns"),
        "pivot_tail_values": get_u8(factor_path, "pivot_tail_values"),
        "affected_offsets": get_u64(factor_path, "affected_offsets"),
        "affected_rows": get_u32(factor_path, "affected_rows"),
        "affected_factors": get_u8(factor_path, "affected_factors"),
        "final_zero_rows": get_u32(factor_path, "final_zero_rows"),
    }
    require(list(trace["pivot_unknown"]) == pivots, "trace coordinates differ from independently loaded gauge")
    trace_audit = verify_trace_rowwise(rebuilt, trace)
    rr_regression = regression(512)

    arrays = {"failure_stream": ArrayPayload("bytes", (12,), b"HC4FAIL1" + struct.pack("<I", 0))}
    q = rebuilt["b_Z"]
    x = [0] * C_COLUMNS
    product_x = [0] * ROWS
    p_power = 1
    timings = []
    rr_checks = {}
    direct_checks = {}
    for j in range(DIGITS):
        core_started = time.perf_counter()
        digit, zero = solve_trace(q, trace)
        product_d = matvec(rebuilt["A_C.row_offsets"], rebuilt["A_C.column_indices"], rebuilt["A_C.values"], digit)
        q_next = []
        flags = bytearray()
        for row in range(ROWS):
            numerator = q[row] - product_d[row]
            flags.append(int(numerator % P == 0))
            require(numerator % P == 0, f"independent divisibility failure at digit {j}, row {row}")
            q_next.append(numerator // P)
            product_x[row] += p_power * product_d[row]
        x_next = [x[position] + p_power * digit[position] for position in range(C_COLUMNS)]
        next_power = p_power * P
        invariant = [rebuilt["b_Z"][row] - product_x[row] - next_power * q_next[row] for row in range(ROWS)]
        require(not any(invariant), f"independent invariant failure at digit {j}")
        core_seconds = time.perf_counter() - core_started
        own_payloads = {
            f"q_{j}": payload_bigints(q),
            f"d_{j}": bytes(digit),
            f"X_{j + 1}": payload_bigints(x_next),
            f"q_{j + 1}": payload_bigints(q_next),
            f"zero_row_residuals_{j}": zero,
            f"divisibility_flags_{j}": bytes(flags),
            f"all_row_invariant_{j}": payload_bigints(invariant),
        }
        for name, payload in own_payloads.items():
            compare_payload(producer_path, name, payload)
            dtype = "u8" if name.startswith(("d_", "zero_", "divisibility_")) else "bigint"
            length = C_COLUMNS if name.startswith(("d_", "X_")) else (len(zero) if name.startswith("zero_") else ROWS)
            arrays[f"verified.{name}.sha256"] = ArrayPayload("bytes", (32,), bytes.fromhex(sha256_bytes(payload)))
        if j in (0, 7):
            global_x = [0] * GLOBAL_COLUMNS
            for local, coordinate in enumerate(pivots):
                global_x[coordinate] = x_next[local]
            direct_product = matvec(
                rebuilt["A_Z.row_offsets"],
                rebuilt["A_Z.column_indices"],
                rebuilt["A_Z.values"],
                global_x,
            )
            mismatches = sum(rebuilt["b_Z"][row] - direct_product[row] - next_power * q_next[row] != 0 for row in range(ROWS))
            require(mismatches == 0, "independent direct A_Z replay failed")
            direct_checks[str(j + 1)] = {"mismatch_count": mismatches}
        if j + 1 in (4, 6, 8):
            labels, aggregate = rr_labels(x_next, next_power)
            compare_payload(producer_path, f"rr_labels_{j + 1}", labels)
            rr_checks[str(j + 1)] = aggregate | {"label_stream_sha256": sha256_bytes(labels)}
        timings.append({"digit_index": j, "core_digit_seconds": core_seconds})
        q, x, p_power = q_next, x_next, next_power
    require(p_power == TERMINAL_MODULUS and p_power.bit_length() == 60, "terminal modulus drift")

    independent_path = staging / "independent-replay.bin"
    container = write_container(independent_path, arrays)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-independent-8digit.v1",
        "status": "PASS_INDEPENDENT_FIXED_P181_DIXON_8DIGIT_PILOT",
        "implementation_freeze": {"path": str(implementation_path.relative_to(campaign)), "sha256": file_hash(implementation_path)},
        "factorization_freeze": {"path": str(index_path.relative_to(campaign)), "sha256": file_hash(index_path)},
        "producer": {"receipt_path": str(producer_receipt_path.relative_to(campaign)), "receipt_sha256": file_hash(producer_receipt_path), "container_path": str(producer_path.relative_to(campaign)), "container_sha256": file_hash(producer_path)},
        "independent_integer_payload_hashes": rebuilt["payload_hashes"],
        "coefficient_trace_audit": trace_audit,
        "rr_small_modulus_regression": rr_regression,
        "rr_checks": rr_checks,
        "direct_uncached_replays": direct_checks,
        "digit_telemetry": timings,
        "container": container,
        "resources": {"internal_wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "source": {"path": relative, "sha256": file_hash(Path(__file__).resolve()), "python": sys.version},
        "declarations": {"does_not_import_producer_preprocessor_or_factorizer": True, "independently_rebuilt_and_normalized_A_Z_b_Z": True, "every_trace_event_verified": True, "exactly_eight_digits": True, "no_digit_nine": True, "no_QQ_vector_assembled": True, "staged_not_promoted": True},
        "claim_boundary": "This second-implementation PASS remains an eight-digit finite p-adic certificate in one fixed gauge, not a QQ identity, ideal membership, colon, saturation, secant closure, nullcone containment, or HC4 proof.",
    }
    receipt_path = staging / "independent-replay.json"
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": receipt["status"], "staging": str(staging)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
