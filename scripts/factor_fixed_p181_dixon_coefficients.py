#!/usr/bin/env python3
"""Deterministic coefficient-only factorization for the fixed-p181 pilot."""

from __future__ import annotations

import argparse
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
    payload_u32,
    payload_u64,
    read_array,
    read_descriptors,
    sha256_bytes,
    write_container,
)


P = 181
ROWS = 85_651
GLOBAL_COLUMNS = 38_048
C_COLUMNS = 35_881
F_COLUMNS = 2_167
FREEZE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
    "implementation-freeze.v3"
)
INTEGER_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-integer-system.v1"
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def milestone(name: str, started: float, **diagnostics: object) -> None:
    print(
        json.dumps(
            {
                "milestone": name,
                "elapsed_seconds": time.perf_counter() - started,
                "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                **diagnostics,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )


def load_freeze(campaign: Path, path: Path) -> dict[str, object]:
    if not path.is_absolute():
        path = campaign / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(payload.get("schema") == FREEZE_SCHEMA, "implementation freeze schema drift")
    require(payload.get("status") == "PASS_IMPLEMENTATION_FREEZE", "implementation not frozen")
    relative = str(Path(__file__).resolve().relative_to(campaign))
    require(
        payload["implementation_sources"][relative] == file_hash(Path(__file__).resolve()),
        "factorizer differs from implementation freeze",
    )
    return {"path": str(path), "sha256": file_hash(path)}


def binding_stream(magic: bytes, arrays: dict[str, ArrayPayload], names: list[str]) -> bytes:
    require(len(magic) == 8, "binding magic must be eight bytes")
    stream = bytearray(magic + struct.pack("<I", len(names)))
    for name in names:
        encoded = name.encode("ascii")
        stream.extend(struct.pack("<H", len(encoded)))
        stream.extend(encoded)
        stream.extend(bytes.fromhex(sha256_bytes(arrays[name].payload)))
    return bytes(stream)


def factor(
    equations: list[dict[int, int]], column_count: int = C_COLUMNS
) -> dict[str, object]:
    started = time.perf_counter()
    row_count = len(equations)
    require(row_count >= column_count > 0, "factor dimensions are invalid")
    incidence = [set() for _ in range(column_count)]
    for row_index, equation in enumerate(equations):
        for column in equation:
            incidence[column].add(row_index)

    pivot_source_rows: list[int] = []
    pivot_unknowns: list[int] = []
    pivot_inverses: list[int] = []
    pivot_tail_offsets = [0]
    pivot_tail_columns: list[int] = []
    pivot_tail_values: list[int] = []
    affected_offsets = [0]
    affected_rows: list[int] = []
    affected_factors: list[int] = []
    selected_rows: set[int] = set()

    update_count = 0
    fill_added = 0
    fill_deleted = 0
    current_nonzeros = sum(map(len, equations))
    peak_nonzeros = current_nonzeros
    maximum_row_length = max(map(len, equations), default=0)
    pivot_length_distribution: Counter[int] = Counter()

    for t in range(column_count):
        candidates = [
            row_index
            for row_index in incidence[t]
            if equations[row_index] is not None and t in equations[row_index]
        ]
        require(candidates, f"coefficient rank failure at pivot {t}")
        row_index = min(candidates, key=lambda index: (len(equations[index]), index))
        row = equations[row_index]
        require(row is not None and t in row, "selected pivot row vanished")
        require(all(column >= t for column in row), "earlier pivot column survived")
        raw_pivot = row[t]
        inverse = pow(raw_pivot, -1, P)
        tail = sorted(
            (column, coefficient * inverse % P)
            for column, coefficient in row.items()
            if column != t
        )
        require(all(column > t and value for column, value in tail), "invalid pivot tail")

        pivot_source_rows.append(row_index)
        selected_rows.add(row_index)
        pivot_unknowns.append(t)
        pivot_inverses.append(inverse)
        pivot_tail_columns.extend(column for column, _value in tail)
        pivot_tail_values.extend(value for _column, value in tail)
        pivot_tail_offsets.append(len(pivot_tail_columns))
        pivot_length_distribution[len(row)] += 1

        for column in tuple(row):
            incidence[column].discard(row_index)
        equations[row_index] = None
        current_nonzeros -= len(row)

        affected = sorted(incidence[t])
        incidence[t].clear()
        for other_index in affected:
            other = equations[other_index]
            if other is None or t not in other:
                continue
            factor_value = other.pop(t)
            affected_rows.append(other_index)
            affected_factors.append(factor_value)
            current_nonzeros -= 1
            old_length = len(other) + 1
            for column, normalized_value in tail:
                old_value = other.get(column, 0)
                new_value = (old_value - factor_value * normalized_value) % P
                if new_value:
                    other[column] = new_value
                    if not old_value:
                        incidence[column].add(other_index)
                        current_nonzeros += 1
                        fill_added += 1
                elif old_value:
                    del other[column]
                    incidence[column].discard(other_index)
                    current_nonzeros -= 1
                    fill_deleted += 1
                update_count += 1
            maximum_row_length = max(maximum_row_length, len(other))
            peak_nonzeros = max(peak_nonzeros, current_nonzeros)
            require(t not in other, "pivot elimination failed")
            require(len(other) <= old_length + len(tail), "row accounting impossible")
        affected_offsets.append(len(affected_rows))

    require(len(selected_rows) == column_count, "pivot rows are not distinct")
    final_zero_rows = sorted(set(range(row_count)) - selected_rows)
    require(len(final_zero_rows) == row_count - column_count, "final zero row count changed")
    require(
        all(equations[row_index] == {} for row_index in final_zero_rows),
        "a final coefficient row is nonzero",
    )
    return {
        "pivot_source_rows": pivot_source_rows,
        "pivot_unknowns": pivot_unknowns,
        "pivot_inverses": pivot_inverses,
        "pivot_tail_offsets": pivot_tail_offsets,
        "pivot_tail_columns": pivot_tail_columns,
        "pivot_tail_values": pivot_tail_values,
        "affected_offsets": affected_offsets,
        "affected_rows": affected_rows,
        "affected_factors": affected_factors,
        "final_zero_rows": final_zero_rows,
        "statistics": {
            "update_count": update_count,
            "fill_added": fill_added,
            "fill_deleted": fill_deleted,
            # Filled by main from the immutable input support count.
            "initial_nonzeros": None,
            "peak_live_nonzeros": peak_nonzeros,
            "maximum_active_row_length": maximum_row_length,
            "pivot_length_distribution": dict(sorted(pivot_length_distribution.items())),
            "wall_seconds": time.perf_counter() - started,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--implementation-freeze", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    campaign = Path(__file__).resolve().parents[1]
    freeze = load_freeze(campaign, arguments.implementation_freeze)
    staging = arguments.staging_dir
    if not staging.is_absolute():
        staging = campaign / staging
    integer_path = staging / "integer-system.bin"
    integer_receipt_path = staging / "integer-system.json"
    require(integer_path.is_file() and integer_receipt_path.is_file(), "staged integer system missing")
    integer_receipt = json.loads(integer_receipt_path.read_text(encoding="utf-8"))
    require(integer_receipt.get("schema") == INTEGER_SCHEMA, "integer receipt schema drift")
    require(integer_receipt.get("status") == "PASS_STAGED_CANONICAL_INTEGER_SYSTEM", "integer preprocessing did not pass")
    require(integer_receipt["container"]["sha256"] == file_hash(integer_path), "integer container drift")

    descriptors = read_descriptors(integer_path)
    read_names: list[str] = []

    def load(name: str) -> bytes:
        require(name != "b_Z", "factorizer attempted to read RHS payload")
        payload = read_array(integer_path, descriptors[name])
        read_names.append(name)
        return payload

    row_offsets = decode_u64(load("A_C.row_offsets"))
    columns = decode_u32(load("A_C.column_indices"))
    integer_values = decode_bigints(
        load("A_C.values"), descriptors["A_C.values"].shape[0]
    )
    pivots = decode_u32(load("C_piv"))
    free = decode_u32(load("F"))
    require(len(row_offsets) == ROWS + 1 and row_offsets[-1] == len(columns), "A_C CSR shape drift")
    require(len(columns) == len(integer_values), "A_C value length drift")
    require(len(pivots) == C_COLUMNS and len(free) == F_COLUMNS, "gauge length drift")
    require(sorted(pivots + free) == list(range(GLOBAL_COLUMNS)), "gauge coverage drift")

    equations: list[dict[int, int]] = []
    modular_nonzeros = 0
    for row_index in range(ROWS):
        row = {}
        for position in range(row_offsets[row_index], row_offsets[row_index + 1]):
            value = integer_values[position] % P
            require(value != 0, "A_C coefficient vanished modulo 181")
            column = columns[position]
            require(column not in row, "duplicate A_C column")
            row[column] = value
            modular_nonzeros += 1
        equations.append(row)
    require(modular_nonzeros == len(columns), "A_C support loss")
    initial_nonzeros = modular_nonzeros
    milestone("INPUT_LOADED", started, A_C_nonzeros=initial_nonzeros)

    trace = factor(equations)
    milestone(
        "ELIMINATION_COMPLETE",
        started,
        affected_operation_count=len(trace["affected_rows"]),
        pivot_tail_nonzeros=len(trace["pivot_tail_columns"]),
    )
    trace["statistics"]["initial_nonzeros"] = initial_nonzeros
    del equations

    # Re-extract the selected integer square submatrix in pivot-row order.
    b_row_offsets = [0]
    b_columns = []
    b_integer_values = []
    b_mod_values = []
    for source_row in trace["pivot_source_rows"]:
        for position in range(row_offsets[source_row], row_offsets[source_row + 1]):
            b_columns.append(columns[position])
            integer_value = integer_values[position]
            b_integer_values.append(integer_value)
            b_mod_values.append(integer_value % P)
        b_row_offsets.append(len(b_columns))
    milestone("B181_EXTRACTED", started, B181_nonzeros=len(b_columns))

    arrays = {
        "B181.column_indices": ArrayPayload("u32", (len(b_columns),), payload_u32(b_columns)),
        "B181.row_offsets": ArrayPayload("u64", (len(b_row_offsets),), payload_u64(b_row_offsets)),
        "B181.values_integer": ArrayPayload("bigint", (len(b_integer_values),), payload_bigints(b_integer_values)),
        "B181.values_mod181": ArrayPayload("u8", (len(b_mod_values),), bytes(b_mod_values)),
        "affected_factors": ArrayPayload("u8", (len(trace["affected_factors"]),), bytes(trace["affected_factors"])),
        "affected_offsets": ArrayPayload("u64", (len(trace["affected_offsets"]),), payload_u64(trace["affected_offsets"])),
        "affected_rows": ArrayPayload("u32", (len(trace["affected_rows"]),), payload_u32(trace["affected_rows"])),
        "failure_stream": ArrayPayload("bytes", (12,), b"HC4FAIL1" + struct.pack("<I", 0)),
        "final_zero_rows": ArrayPayload("u32", (len(trace["final_zero_rows"]),), payload_u32(trace["final_zero_rows"])),
        "pivot_inverse": ArrayPayload("u8", (len(trace["pivot_inverses"]),), bytes(trace["pivot_inverses"])),
        "pivot_source_row": ArrayPayload("u32", (len(trace["pivot_source_rows"]),), payload_u32(trace["pivot_source_rows"])),
        "pivot_tail_columns": ArrayPayload("u32", (len(trace["pivot_tail_columns"]),), payload_u32(trace["pivot_tail_columns"])),
        "pivot_tail_offsets": ArrayPayload("u64", (len(trace["pivot_tail_offsets"]),), payload_u64(trace["pivot_tail_offsets"])),
        "pivot_tail_values": ArrayPayload("u8", (len(trace["pivot_tail_values"]),), bytes(trace["pivot_tail_values"])),
        "pivot_unknown": ArrayPayload("u32", (len(pivots),), payload_u32(pivots)),
    }
    trace_names = [
        "pivot_source_row",
        "pivot_unknown",
        "pivot_inverse",
        "pivot_tail_offsets",
        "pivot_tail_columns",
        "pivot_tail_values",
        "affected_offsets",
        "affected_rows",
        "affected_factors",
        "final_zero_rows",
    ]
    trace_binding = binding_stream(b"HC4TRC01", arrays, trace_names)
    arrays["trace_binding"] = ArrayPayload("bytes", (len(trace_binding),), trace_binding)
    milestone("PAYLOADS_PACKED", started)

    factor_path = staging / "factorization.bin"
    container = write_container(factor_path, arrays)
    milestone("CONTAINER_FSYNCED", started, container_bytes=container["byte_count"])
    require("b_Z" not in read_names, "RHS payload read declaration is false")
    receipt = {
        "schema": (
            "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-"
            "factorization.v1"
        ),
        "status": "PASS_STAGED_COEFFICIENT_ONLY_FACTORIZATION",
        "implementation_freeze": freeze,
        "integer_system": {
            "path": str(integer_path),
            "sha256": file_hash(integer_path),
            "receipt_path": str(integer_receipt_path),
            "receipt_sha256": file_hash(integer_receipt_path),
        },
        "dimensions": {
            "rows": ROWS,
            "global_columns": GLOBAL_COLUMNS,
            "C_columns": C_COLUMNS,
            "F_columns": F_COLUMNS,
            "A_C_nonzeros": len(columns),
            "B181_nonzeros": len(b_columns),
            "pivot_count": len(trace["pivot_source_rows"]),
            "final_zero_row_count": len(trace["final_zero_rows"]),
            "pivot_tail_nonzeros": len(trace["pivot_tail_columns"]),
            "affected_operation_count": len(trace["affected_rows"]),
        },
        "trace_statistics": trace["statistics"],
        "trace_binding_sha256": sha256_bytes(trace_binding),
        "read_array_names": read_names,
        "container": container,
        "timings": {"wall_seconds": time.perf_counter() - started},
        "resources": {
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(campaign)),
            "sha256": file_hash(Path(__file__).resolve()),
            "python": sys.version,
        },
        "declarations": {
            "coefficient_only": True,
            "factorizer_b_payload_not_loaded": True,
            "digit_payload_not_loaded": True,
            "no_arithmetic_modulo_181_squared": True,
            "staged_not_promoted": True,
        },
        "claim_boundary": (
            "This staged PASS proves only that the frozen coefficient restriction "
            "has the prescribed deterministic full-rank trace modulo 181. It reads "
            "no RHS and computes no digit, QQ identity, ideal membership, colon, "
            "saturation, secant closure, nullcone containment, or HC4 result."
        ),
    }
    receipt_path = staging / "factorization.json"
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": receipt["status"], "staging": str(staging)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
