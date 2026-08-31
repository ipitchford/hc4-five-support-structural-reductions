#!/usr/bin/env python3
"""Lift four sparse canonical residual sections through exactly p^2."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import subprocess
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

from fixed_p181_dixon_rr import AMBIGUOUS, NO_CANDIDATE, UNIQUE_NONZERO, UNIQUE_ZERO, classify


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
RHS_COUNT = 4
PADDED_RHS_COUNT = 114
DRIVER = CAMPAIGN / "artifacts/bin/linbox_p181_canonical_residual_114_section_driver"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_exact(path: Path):
    payload = path.read_bytes()
    require(payload[:8] == b"HC4S4181", "sparse-four exact magic drift")
    rows, columns, nonzeros, rhs_count = struct.unpack_from("<QQQQ", payload, 8)
    require((rows, columns, rhs_count) == (ROWS, COLUMNS, RHS_COUNT), "sparse-four exact dimensions drift")
    cursor = 40
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy()
    cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy()
    cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy()
    cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows * rhs_count, offset=cursor).copy().reshape(rows, rhs_count)
    cursor += 8 * rows * rhs_count
    require(cursor == len(payload), "sparse-four exact trailing bytes")
    return offsets, indices, values, rhs


def rr_census(x, modulus):
    labels = bytearray()
    candidates = []
    per_column = []
    for column in range(RHS_COUNT):
        counts = Counter()
        column_candidates = []
        for residue in x[:, column]:
            outcome = classify(int(residue), modulus)
            labels.append(outcome.label)
            counts[outcome.label] += 1
            column_candidates.append(outcome.candidates[0] if len(outcome.candidates) == 1 else None)
        candidates.append(column_candidates)
        per_column.append({
            "NO_CANDIDATE": counts[NO_CANDIDATE],
            "UNIQUE_ZERO": counts[UNIQUE_ZERO],
            "UNIQUE_NONZERO": counts[UNIQUE_NONZERO],
            "AMBIGUOUS": counts[AMBIGUOUS],
        })
    return bytes(labels), candidates, per_column


def exact_replay(offsets, indices, values, rhs, candidates):
    vectors = [[Fraction(*candidates[column][row]) for column in range(RHS_COUNT)] for row in range(COLUMNS)]
    mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        total = [Fraction(0) for _ in range(RHS_COUNT)]
        for position in range(int(offsets[row]), int(offsets[row + 1])):
            value = int(values[position])
            vector = vectors[int(indices[position])]
            for column in range(RHS_COUNT):
                total[column] += value * vector[column]
        for column in range(RHS_COUNT):
            residual = total[column] - int(rhs[row, column])
            mismatches += residual != 0
            residual_hash.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    require(mismatches == 0, "complete two-digit reconstruction failed exact replay")
    return vectors, {"mismatch_count": mismatches, "residual_stream_sha256": residual_hash.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integral-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    integral = arguments.integral_dir if arguments.integral_dir.is_absolute() else CAMPAIGN / arguments.integral_dir
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    exact_path = integral / "A_Z_b4_Z_coefficient_primitive.i64csr"
    modular_path = integral / "A_mod181_coefficient_primitive.csr"
    digit_zero_path = integral / "digit_00_sparse4_row_major.u8"
    offsets, indices, values, rhs = read_exact(exact_path)
    digit_zero_payload = digit_zero_path.read_bytes()
    require(len(digit_zero_payload) == COLUMNS * RHS_COUNT, "digit-zero byte length drift")
    digit_zero = np.frombuffer(digit_zero_payload, dtype=np.uint8).reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    product_zero = coefficient @ digit_zero
    residual = rhs - product_zero
    digit_zero_divisibility_mismatches = int(np.count_nonzero(residual % P))
    require(digit_zero_divisibility_mismatches == 0, "digit-zero exact divisibility failed")
    q1 = residual // P

    padded = np.zeros((ROWS, PADDED_RHS_COUNT), dtype=np.uint8)
    padded[:, :RHS_COUNT] = (q1 % P).astype(np.uint8)
    correction_rhs_path = output / "correction_rhs_digit_01_padded114.u8"
    correction114_path = output / "digit_01_padded114.u8"
    correction_rhs_path.write_bytes(padded.tobytes(order="C"))
    completed = subprocess.run(
        [str(DRIVER), "--csr", str(modular_path), "--rhs", str(correction_rhs_path), "--solution-output", str(correction114_path)],
        cwd=CAMPAIGN, text=True, capture_output=True,
    )
    (output / "driver.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "driver.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    driver = json.loads(lines[0]) if len(lines) == 1 else None
    if completed.returncode == 4 and driver is not None and driver.get("status") == "STOP_CANONICAL_RESIDUAL_114_SECTION_NULLITY":
        receipt = {
            "schema": "hc4.third-colon-p181-sparse4-two-digit-lift.v1",
            "status": "STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE",
            "driver": driver,
            "digit_zero_divisibility_mismatches": digit_zero_divisibility_mismatches,
            "claim_boundary": "This STOP falsifies only the registered p^2 lift of at least one of the four fixed canonical residual sections.",
        }
        receipt_path = output / "lift.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}))
        return 4
    require(completed.returncode == 0 and driver is not None, "padded correction driver failed")
    require(driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", "padded correction driver status drift")
    correction_payload = correction114_path.read_bytes()
    require(len(correction_payload) == COLUMNS * PADDED_RHS_COUNT, "padded correction length drift")
    correction114 = np.frombuffer(correction_payload, dtype=np.uint8).reshape(COLUMNS, PADDED_RHS_COUNT)
    padded_tail_nonzeros = int(np.count_nonzero(correction114[:, RHS_COUNT:]))
    require(padded_tail_nonzeros == 0, "padded zero-column correction became nonzero")
    digit_one = correction114[:, :RHS_COUNT].astype(np.int64)
    product_one = coefficient @ digit_one
    second_numerator = q1 - product_one
    digit_one_divisibility_mismatches = int(np.count_nonzero(second_numerator % P))
    require(digit_one_divisibility_mismatches == 0, "digit-one exact divisibility failed")
    q2 = second_numerator // P
    modulus = P**2
    x2 = digit_zero + P * digit_one
    direct_residual = rhs - coefficient @ x2
    direct_invariant_mismatches = int(np.count_nonzero(direct_residual - modulus * q2))
    require(direct_invariant_mismatches == 0, "two-digit direct integer invariant failed")
    digit_one_path = output / "digit_01_sparse4_row_major.u8"
    x2_path = output / "X_mod_181_power_2_sparse4_row_major.u16le"
    digit_one_path.write_bytes(digit_one.astype(np.uint8).tobytes(order="C"))
    x2_path.write_bytes(x2.astype("<u2").tobytes(order="C"))

    labels, candidates, per_column = rr_census(x2, modulus)
    labels_path = output / "rr_labels_digit_02_column_major.u8"
    labels_path.write_bytes(labels)
    complete = all(candidate is not None for column in candidates for candidate in column)
    exact_result = None
    rational_output = None
    status = "PASS_P181_SPARSE4_TWO_DIGIT_LIFT"
    if complete:
        vectors, exact_result = exact_replay(offsets, indices, values, rhs, candidates)
        rational_path = output / "rational_sparse4_solution.json"
        rational_path.write_text(json.dumps([[[value.numerator, value.denominator] for value in row] for row in vectors], separators=(",", ":")) + "\n", encoding="ascii")
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}
        status = "PASS_P181_SPARSE4_TWO_DIGIT_EXACT_RATIONAL_REPLAY"

    receipt = {
        "schema": "hc4.third-colon-p181-sparse4-two-digit-lift.v1",
        "status": status,
        "inputs": {"exact_system_sha256": file_hash(exact_path), "modular_csr_sha256": file_hash(modular_path), "digit_zero_sha256": file_hash(digit_zero_path), "driver_sha256": file_hash(DRIVER)},
        "dimensions": {"rows": ROWS, "columns": COLUMNS, "rhs_count": RHS_COUNT, "padded_rhs_count": PADDED_RHS_COUNT, "exact_nonzeros": len(indices)},
        "driver": driver,
        "checks": {"digit_zero_divisibility_mismatches": digit_zero_divisibility_mismatches, "digit_one_divisibility_mismatches": digit_one_divisibility_mismatches, "direct_integer_invariant_mismatches": direct_invariant_mismatches, "padded_tail_nonzeros": padded_tail_nonzeros},
        "support": {"digit_zero": np.count_nonzero(digit_zero, axis=0).astype(int).tolist(), "digit_one": np.count_nonzero(digit_one, axis=0).astype(int).tolist(), "two_digit_residues": np.count_nonzero(x2, axis=0).astype(int).tolist()},
        "heights": {"maximum_q1_bit_length": int(max(abs(int(value)).bit_length() for value in q1.flat)), "maximum_q2_bit_length": int(max(abs(int(value)).bit_length() for value in q2.flat)), "maximum_two_digit_residue": int(x2.max())},
        "terminal_modulus": modulus,
        "outputs": {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size} for path in (correction_rhs_path, correction114_path, digit_one_path, x2_path, labels_path)},
        "rational_reconstruction": {"per_column": per_column, "complete": complete, "label_stream_sha256": file_hash(labels_path), "exact_replay": exact_result, "rational_output": rational_output},
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"exactly_two_total_digits": True, "no_third_digit": True, "padded_zero_rhs_columns": 110, "old_target_rhs_not_read": True, "old_target_solution_not_read": True},
        "claim_boundary": "A two-digit PASS is finite p-adic evidence for four fixed canonical residual sections only. It does not prove a QQ lift, target membership, colon, saturation, secant closure, nullcone containment, or HC4. An exact replay, if present, establishes only four rational residual syzygies in the fixed chart.",
    }
    receipt_path = output / "lift.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

