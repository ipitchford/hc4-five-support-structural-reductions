#!/usr/bin/env python3
"""Prospectively frozen producer for the fixed-p181 eight-digit Dixon pilot.

This program never factors a matrix and never chooses a pivot.  It consumes
only the coefficient-only trace frozen by Phase I, applies that trace to the
eight registered right-hand sides, and checks every exact integer recurrence.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
import resource
import struct
import sys
import time
from collections import Counter
from pathlib import Path

from fixed_p181_dixon_codec import (
    ArrayPayload,
    decode_bigints,
    decode_u32,
    decode_u64,
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


P = 181
DIGITS = 8
ROWS = 85_651
GLOBAL_COLUMNS = 38_048
C_COLUMNS = 35_881
F_COLUMNS = 2_167
TERMINAL_MODULUS = 1_151_936_657_823_500_641
EXPECTED_D0_LEGACY = (
    "9932deed637ea317b4483cad9366e1fd1455be7453bc74a64ce78f04c4f57919"
)
FREEZE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
    "implementation-freeze.v3"
)
INDEX_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
    "factorization-freeze.v3"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_hash(values: list[int]) -> str:
    raw = json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return sha256_bytes(raw)


def load_array(path: Path, name: str) -> tuple[bytes, tuple[int, ...]]:
    descriptors = read_descriptors(path)
    require(name in descriptors, f"missing array {name} in {path.name}")
    descriptor = descriptors[name]
    return read_array(path, descriptor), descriptor.shape


def _packed_unsigned(payload: bytes, typecode: str) -> array.array:
    values = array.array(typecode)
    values.frombytes(payload)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def load_u32(path: Path, name: str) -> array.array:
    payload, _shape = load_array(path, name)
    return _packed_unsigned(payload, "I")


def load_u64(path: Path, name: str) -> array.array:
    payload, _shape = load_array(path, name)
    return _packed_unsigned(payload, "Q")


def load_bigints(path: Path, name: str) -> list[int]:
    payload, shape = load_array(path, name)
    require(len(shape) == 1, f"{name} is not a vector")
    return decode_bigints(payload, shape[0])


def load_u8(path: Path, name: str) -> bytes:
    payload, shape = load_array(path, name)
    require(len(shape) == 1 and len(payload) == shape[0], f"{name} is not u8 vector")
    return payload


def verify_freezes(
    campaign: Path, implementation_path: Path, factorization_index_path: Path
) -> dict[str, object]:
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    require(implementation.get("schema") == FREEZE_SCHEMA, "implementation schema drift")
    require(implementation.get("status") == "PASS_IMPLEMENTATION_FREEZE", "implementation not frozen")
    relative = str(Path(__file__).resolve().relative_to(campaign))
    require(
        implementation["implementation_sources"].get(relative)
        == file_hash(Path(__file__).resolve()),
        "producer differs from implementation freeze",
    )
    index = json.loads(factorization_index_path.read_text(encoding="utf-8"))
    require(index.get("schema") == INDEX_SCHEMA, "factorization index schema drift")
    require(index.get("status") == "PASS_FACTORIZATION_FREEZE", "factorization not frozen")
    require(
        index["implementation_freeze"]["sha256"] == file_hash(implementation_path),
        "factorization index binds another implementation freeze",
    )
    declarations = index.get("declarations", {})
    require(declarations.get("coefficient_only") is True, "factorization was not coefficient-only")
    require(
        declarations.get("factorizer_b_payload_not_loaded") is True,
        "factorizer RHS exclusion missing",
    )
    require(
        declarations.get("no_arithmetic_modulo_181_squared") is True,
        "pre-p2 declaration missing",
    )
    bundle = campaign / index["bundle"]["path"]
    require(bundle.is_dir(), "frozen Phase-I bundle missing")
    for name, expected in index["bundle"]["files"].items():
        require(file_hash(bundle / name) == expected, f"frozen bundle drift: {name}")
    return {
        "implementation_freeze": {
            "path": str(implementation_path.relative_to(campaign)),
            "sha256": file_hash(implementation_path),
        },
        "factorization_freeze": {
            "path": str(factorization_index_path.relative_to(campaign)),
            "sha256": file_hash(factorization_index_path),
        },
        "bundle": bundle,
    }


def replay_trace(rhs: list[int], trace: dict[str, object]) -> tuple[list[int], list[int]]:
    """Apply the immutable row trace and reverse substitution modulo 181."""

    column_count = len(trace["pivot_source_row"])
    rho = [value % P for value in rhs]
    eta = [0] * column_count
    for t in range(column_count):
        source = trace["pivot_source_row"][t]
        value = rho[source] * trace["pivot_inverse"][t] % P
        eta[t] = value
        start = trace["affected_offsets"][t]
        end = trace["affected_offsets"][t + 1]
        for position in range(start, end):
            row = trace["affected_rows"][position]
            rho[row] = (rho[row] - trace["affected_factors"][position] * value) % P

    zero_residuals = [rho[row] for row in trace["final_zero_rows"]]
    require(not any(zero_residuals), "transformed RHS is nonzero on a final zero row")

    digit = [0] * column_count
    for t in range(column_count - 1, -1, -1):
        value = eta[t]
        start = trace["pivot_tail_offsets"][t]
        end = trace["pivot_tail_offsets"][t + 1]
        for position in range(start, end):
            value -= trace["pivot_tail_values"][position] * digit[
                trace["pivot_tail_columns"][position]
            ]
        digit[t] = value % P
    return digit, zero_residuals


def csr_matvec(
    row_offsets: list[int], columns: list[int], values: list[int], vector: list[int]
) -> list[int]:
    result = [0] * (len(row_offsets) - 1)
    for row in range(len(result)):
        total = 0
        for position in range(row_offsets[row], row_offsets[row + 1]):
            total += values[position] * vector[columns[position]]
        result[row] = total
    return result


def direct_full_replay(
    integer_path: Path,
    pivots: list[int],
    x_c: list[int],
    modulus: int,
    q: list[int],
) -> dict[str, object]:
    """Uncached A_Z replay; the F coordinates are literally zero."""

    row_offsets = load_u64(integer_path, "A_Z.row_offsets")
    columns = load_u32(integer_path, "A_Z.column_indices")
    values = load_bigints(integer_path, "A_Z.values")
    b = load_bigints(integer_path, "b_Z")
    global_x = dict(zip(pivots, x_c, strict=True))
    mismatch_count = 0
    maximum_absolute_residual = 0
    digest = hashlib.sha256()
    for row in range(ROWS):
        total = 0
        for position in range(row_offsets[row], row_offsets[row + 1]):
            coordinate = columns[position]
            if coordinate in global_x:
                total += values[position] * global_x[coordinate]
        residual = b[row] - total - modulus * q[row]
        mismatch_count += int(residual != 0)
        maximum_absolute_residual = max(maximum_absolute_residual, abs(residual))
        digest.update(str(residual).encode("ascii") + b"\n")
    require(mismatch_count == 0, "uncached direct all-row replay failed")
    return {
        "mismatch_count": mismatch_count,
        "maximum_absolute_residual": maximum_absolute_residual,
        "residual_decimal_line_stream_sha256": digest.hexdigest(),
    }


def binding_stream(arrays: dict[str, ArrayPayload], names: list[str]) -> bytes:
    stream = bytearray(b"HC4RPL01" + struct.pack("<I", len(names)))
    for name in names:
        encoded = name.encode("ascii")
        stream.extend(struct.pack("<H", len(encoded)))
        stream.extend(encoded)
        stream.extend(bytes.fromhex(sha256_bytes(arrays[name].payload)))
    return bytes(stream)


def rr_snapshot(values: list[int], modulus: int) -> tuple[bytes, dict[str, object]]:
    labels = bytearray()
    counts: Counter[int] = Counter()
    maximum_numerator = 0
    maximum_denominator = 0
    maximum_twice_product = 0
    divisions = 0
    convergents = 0
    retained = 0
    for value in values:
        outcome = classify(value % modulus, modulus)
        labels.append(outcome.label)
        counts[outcome.label] += 1
        divisions += outcome.euclidean_divisions
        convergents += outcome.convergents_tested
        retained += len(outcome.candidates)
        for numerator, denominator in outcome.candidates:
            maximum_numerator = max(maximum_numerator, abs(numerator))
            maximum_denominator = max(maximum_denominator, denominator)
            maximum_twice_product = max(
                maximum_twice_product, 2 * abs(numerator) * denominator
            )
    require(len(labels) == C_COLUMNS, "RR label stream length drift")
    aggregate = {
        "NO_CANDIDATE": counts[NO_CANDIDATE],
        "UNIQUE_ZERO": counts[UNIQUE_ZERO],
        "UNIQUE_NONZERO": counts[UNIQUE_NONZERO],
        "AMBIGUOUS": counts[AMBIGUOUS],
    }
    require(sum(aggregate.values()) == C_COLUMNS, "RR aggregate does not cover C")
    return bytes(labels), {
        "modulus": str(modulus),
        "aggregate_labels": aggregate,
        "maximum_accepted_absolute_numerator": maximum_numerator,
        "maximum_accepted_denominator": maximum_denominator,
        "maximum_accepted_twice_product": maximum_twice_product,
        "total_euclidean_divisions": divisions,
        "total_convergents_tested": convergents,
        "candidates_retained": retained,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--implementation-freeze", type=Path, required=True)
    parser.add_argument("--factorization-freeze", type=Path, required=True)
    arguments = parser.parse_args()
    campaign = Path(__file__).resolve().parents[1]
    staging = arguments.staging_dir if arguments.staging_dir.is_absolute() else campaign / arguments.staging_dir
    staging.mkdir(parents=True, exist_ok=False)
    implementation = arguments.implementation_freeze if arguments.implementation_freeze.is_absolute() else campaign / arguments.implementation_freeze
    factor_index = arguments.factorization_freeze if arguments.factorization_freeze.is_absolute() else campaign / arguments.factorization_freeze
    started = time.perf_counter()

    freezes = verify_freezes(campaign, implementation, factor_index)
    bundle = freezes["bundle"]
    integer_path = bundle / "integer-system.bin"
    factor_path = bundle / "factorization.bin"
    pivots = load_u32(integer_path, "C_piv")
    free = load_u32(integer_path, "F")
    d0_full = load_u8(integer_path, "d_0")
    b = load_bigints(integer_path, "b_Z")
    row_offsets = load_u64(integer_path, "A_C.row_offsets")
    columns = load_u32(integer_path, "A_C.column_indices")
    values = load_bigints(integer_path, "A_C.values")
    require(len(pivots) == C_COLUMNS and len(free) == F_COLUMNS, "gauge dimensions drift")
    require(sorted(pivots + free) == list(range(GLOBAL_COLUMNS)), "gauge coverage drift")
    require(compact_hash(list(d0_full)) == EXPECTED_D0_LEGACY, "digit-zero legacy hash drift")
    require(all(d0_full[index] == 0 for index in free), "digit-zero F coordinate is nonzero")
    d0_c = [d0_full[index] for index in pivots]

    trace = {
        "pivot_source_row": load_u32(factor_path, "pivot_source_row"),
        "pivot_unknown": load_u32(factor_path, "pivot_unknown"),
        "pivot_inverse": load_u8(factor_path, "pivot_inverse"),
        "pivot_tail_offsets": load_u64(factor_path, "pivot_tail_offsets"),
        "pivot_tail_columns": load_u32(factor_path, "pivot_tail_columns"),
        "pivot_tail_values": load_u8(factor_path, "pivot_tail_values"),
        "affected_offsets": load_u64(factor_path, "affected_offsets"),
        "affected_rows": load_u32(factor_path, "affected_rows"),
        "affected_factors": load_u8(factor_path, "affected_factors"),
        "final_zero_rows": load_u32(factor_path, "final_zero_rows"),
    }
    require(trace["pivot_unknown"] == pivots, "trace pivot coordinates changed")
    require(len(trace["final_zero_rows"]) == ROWS - C_COLUMNS, "zero-row count drift")
    rr_regression = regression(512)

    arrays: dict[str, ArrayPayload] = {
        "failure_stream": ArrayPayload("bytes", (12,), b"HC4FAIL1" + struct.pack("<I", 0)),
        "q_0": ArrayPayload("bigint", (ROWS,), payload_bigints(b)),
    }
    q_vectors = [b]
    digits: list[list[int]] = []
    x_vectors: list[list[int]] = []
    x = [0] * C_COLUMNS
    product_x = [0] * ROWS
    p_power = 1
    digit_receipts = []
    direct_replays: dict[str, object] = {}
    rr_receipts: dict[str, object] = {}

    for j in range(DIGITS):
        total_started = time.perf_counter()
        usage_before = resource.getrusage(resource.RUSAGE_SELF)
        core_started = time.perf_counter()
        q = q_vectors[j]
        digit, zero_residuals = replay_trace(q, trace)
        repeated_digit, repeated_zero = replay_trace(q, trace)
        require(digit == repeated_digit and zero_residuals == repeated_zero, "trace replay is not byte-stable")
        if j == 0:
            require(digit == d0_c, "trace digit zero differs from frozen p181 solution")
        product_d = csr_matvec(row_offsets, columns, values, digit)
        q_next = []
        flags = bytearray()
        for row in range(ROWS):
            numerator = q[row] - product_d[row]
            flags.append(int(numerator % P == 0))
            require(numerator % P == 0, f"nondivisible Dixon numerator at digit {j}, row {row}")
            q_next.append(numerator // P)
            product_x[row] += p_power * product_d[row]
        x_next = [x[index] + p_power * digit[index] for index in range(C_COLUMNS)]
        next_power = p_power * P
        invariant = [
            b[row] - product_x[row] - next_power * q_next[row]
            for row in range(ROWS)
        ]
        require(not any(invariant), f"cached all-row invariant failed at digit {j}")
        core_seconds = time.perf_counter() - core_started
        usage_after = resource.getrusage(resource.RUSAGE_SELF)

        q_name = f"q_{j}"
        d_name = f"d_{j}"
        x_name = f"X_{j + 1}"
        q_next_name = f"q_{j + 1}"
        zero_name = f"zero_row_residuals_{j}"
        flags_name = f"divisibility_flags_{j}"
        invariant_name = f"all_row_invariant_{j}"
        arrays[d_name] = ArrayPayload("u8", (C_COLUMNS,), bytes(digit))
        arrays[x_name] = ArrayPayload("bigint", (C_COLUMNS,), payload_bigints(x_next))
        arrays[q_next_name] = ArrayPayload("bigint", (ROWS,), payload_bigints(q_next))
        arrays[zero_name] = ArrayPayload("u8", (len(zero_residuals),), bytes(zero_residuals))
        arrays[flags_name] = ArrayPayload("u8", (ROWS,), bytes(flags))
        arrays[invariant_name] = ArrayPayload("bigint", (ROWS,), payload_bigints(invariant))
        binding_names = [q_name, d_name, x_name, q_next_name, zero_name, flags_name, invariant_name]
        replay = binding_stream(arrays, binding_names)
        arrays[f"replay_binding_{j}"] = ArrayPayload("bytes", (len(replay),), replay)

        excluded_started = time.perf_counter()
        if j in (0, 7):
            direct_replays[str(j + 1)] = direct_full_replay(
                integer_path, pivots, x_next, next_power, q_next
            )
        rr_seconds = 0.0
        if j + 1 in (4, 6, 8):
            rr_started = time.perf_counter()
            labels, rr_data = rr_snapshot(x_next, next_power)
            rr_seconds = time.perf_counter() - rr_started
            labels_name = f"rr_labels_{j + 1}"
            arrays[labels_name] = ArrayPayload("u8", (C_COLUMNS,), labels)
            rr_data["label_stream_sha256"] = sha256_bytes(labels)
            rr_data["seconds"] = rr_seconds
            rr_receipts[str(j + 1)] = rr_data
        excluded_seconds = time.perf_counter() - excluded_started
        digit_receipts.append(
            {
                "digit_index": j,
                "core_digit_seconds": core_seconds,
                "total_digit_seconds": time.perf_counter() - total_started,
                "excluded_checkpoint_seconds": excluded_seconds,
                "rr_seconds": rr_seconds,
                "user_seconds_delta": usage_after.ru_utime - usage_before.ru_utime,
                "system_seconds_delta": usage_after.ru_stime - usage_before.ru_stime,
                "maximum_q_bit_length": max((abs(value).bit_length() for value in q_next), default=0),
                "maximum_X_bit_length": max((abs(value).bit_length() for value in x_next), default=0),
                "trace_affected_operations_per_replay": len(trace["affected_rows"]),
                "trace_replay_count": 2,
                "matrix_nonzeros": len(values),
                "output_payload_bytes_before_container": sum(
                    len(arrays[name].payload) for name in binding_names
                ),
                "replay_binding_sha256": sha256_bytes(replay),
            }
        )
        digits.append(digit)
        x_vectors.append(x_next)
        q_vectors.append(q_next)
        x = x_next
        p_power = next_power

    require(p_power == TERMINAL_MODULUS and p_power.bit_length() == 60, "terminal modulus drift")
    output_path = staging / "producer-digits.bin"
    container = write_container(output_path, arrays)
    tail = max(item["core_digit_seconds"] for item in digit_receipts[4:8])
    projected = 120 * tail
    if projected <= 1_800:
        provisional_band = "STRONG_FULL_LIFT_SIGNAL"
    elif projected <= 7_200:
        provisional_band = "INTERMEDIATE_FULL_LIFT_SIGNAL"
    else:
        provisional_band = "STOP_THROUGHPUT_SIGNAL"
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-producer-8digit.v1",
        "status": "PASS_PRODUCER_FIXED_P181_DIXON_8DIGIT_PILOT",
        "freezes": {key: value for key, value in freezes.items() if key != "bundle"},
        "container": container,
        "dimensions": {
            "rows": ROWS,
            "global_columns": GLOBAL_COLUMNS,
            "C_columns": C_COLUMNS,
            "F_columns": F_COLUMNS,
            "digits": DIGITS,
            "terminal_modulus": str(p_power),
            "terminal_modulus_bit_length": p_power.bit_length(),
        },
        "rr_small_modulus_regression": rr_regression,
        "rr_snapshots": rr_receipts,
        "direct_uncached_replays": direct_replays,
        "digit_telemetry": digit_receipts,
        "provisional_producer_only_tail": {
            "tail_seconds": tail,
            "projected_120_digit_seconds": projected,
            "band": provisional_band,
            "controls_terminal_band": False,
        },
        "resources": {
            "internal_wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(campaign)),
            "sha256": file_hash(Path(__file__).resolve()),
            "python": sys.version,
        },
        "declarations": {
            "fixed_characteristic_181": True,
            "x_F_literal_zero": True,
            "exactly_eight_digits": True,
            "no_digit_nine": True,
            "no_individual_rr_candidate_inspected_or_emitted": True,
            "no_QQ_vector_assembled": True,
            "staged_not_promoted": True,
        },
        "claim_boundary": (
            "This staged producer PASS is only an eight-digit finite p-adic replay in "
            "one fixed gauge. It is not a rational solution, QQ identity, ideal membership, "
            "colon, saturation, secant closure, nullcone containment, or HC4 proof."
        ),
    }
    receipt_path = staging / "producer-digits.json"
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": receipt["status"], "staging": str(staging)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
