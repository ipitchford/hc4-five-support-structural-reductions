#!/usr/bin/env -S sage -python
"""Extend the seven p^8-unresolved support-18 columns through p^10."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

import lift_p181_sparse4_to_two_digits as lift_base
import reconstruct_p181_sparse4_exact_rational as rr_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
FULL_RHS = 18
ACTIVE_BATCH = (6, 11, 13, 14, 15, 16, 17)
ACTIVE_RESIDUAL = (15, 78, 91, 104, 81, 10, 13)
ACTIVE_RHS = len(ACTIVE_BATCH)
PADDED = 114
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
P8_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1"
EXACT = SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
MODULAR = SOURCE / "integral/A_mod181_coefficient_primitive.csr"
X8 = P8_SOURCE / "X_mod_181_power_8_support18_row_major.u64le"
Q8 = P8_SOURCE / "terminal_q8_support18_row_major.i64le"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_p181_canonical_residual_114_section_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconstruction_census(x8: np.ndarray, digits: list[np.ndarray]) -> dict:
    modulus = P**10
    unresolved_by_column = [0] * ACTIVE_RHS
    resolved_nonzero_by_column = [0] * ACTIVE_RHS
    resolved_zero_by_column = [0] * ACTIVE_RHS
    maximum_absolute_numerator = [0] * ACTIVE_RHS
    maximum_denominator = [0] * ACTIVE_RHS
    for row in range(COLUMNS):
        for column in range(ACTIVE_RHS):
            residue = int(x8[row, column])
            residue += (P**8) * int(digits[0][row, column])
            residue += (P**9) * int(digits[1][row, column])
            pair = rr_base.rr(residue, modulus)
            if pair is None:
                unresolved_by_column[column] += 1
            elif pair[0] == 0:
                resolved_zero_by_column[column] += 1
            else:
                resolved_nonzero_by_column[column] += 1
                maximum_absolute_numerator[column] = max(maximum_absolute_numerator[column], abs(pair[0]))
                maximum_denominator[column] = max(maximum_denominator[column], pair[1])
    return {
        "modulus": modulus,
        "equal_height_bound": math.isqrt((modulus - 1) // 2),
        "coordinate_count": COLUMNS * ACTIVE_RHS,
        "unresolved_count": sum(unresolved_by_column),
        "unresolved_by_column": unresolved_by_column,
        "resolved_nonzero_by_column": resolved_nonzero_by_column,
        "resolved_zero_by_column": resolved_zero_by_column,
        "maximum_absolute_numerator_by_column": maximum_absolute_numerator,
        "maximum_denominator_by_column": maximum_denominator,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    lift_base.RHS_COUNT = FULL_RHS
    offsets, indices, values, _rhs = lift_base.read_exact(EXACT)
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    active = np.asarray(ACTIVE_BATCH, dtype=np.int64)
    x8_all = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)
    x8 = x8_all[:, active].copy()
    q8_all = np.frombuffer(Q8.read_bytes(), dtype="<i8").reshape(ROWS, FULL_RHS)
    q = q8_all[:, active].copy()
    corrections = []
    digits = []

    for digit_index in (8, 9):
        digit_started = time.perf_counter()
        padded = np.zeros((ROWS, PADDED), dtype=np.uint8)
        padded[:, :ACTIVE_RHS] = (q % P).astype(np.uint8)
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}_padded114.u8"
        padded_solution_path = output / f"digit_{digit_index:02d}_padded114.u8"
        stdout_path = output / f"digit_{digit_index:02d}.stdout.txt"
        stderr_path = output / f"digit_{digit_index:02d}.stderr.txt"
        rhs_path.write_bytes(padded.tobytes(order="C"))
        completed = subprocess.run(
            [str(DRIVER), "--csr", str(MODULAR), "--rhs", str(rhs_path), "--solution-output", str(padded_solution_path)],
            cwd=CAMPAIGN,
            text=True,
            capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_CANONICAL_RESIDUAL_114_SECTION_NULLITY":
            receipt = {
                "schema": "hc4.third-colon-p181-support7-ten-digit-extension.v1",
                "status": "STOP_P181_SUPPORT7_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit_index": digit_index,
                "corrections": corrections,
                "driver": driver,
                "claim_boundary": "This STOP concerns only the fixed support7 correction digit.",
            }
            path = output / "extension.json"
            path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)}))
            return 4
        require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", f"driver failed at digit {digit_index}")
        all_digits = np.frombuffer(padded_solution_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, PADDED)
        tail_nonzeros = int(np.count_nonzero(all_digits[:, ACTIVE_RHS:]))
        require(tail_nonzeros == 0, f"padded tail nonzero at digit {digit_index}")
        digit = all_digits[:, :ACTIVE_RHS].astype(np.int64)
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"recurrence divisibility failed at digit {digit_index}")
        q = numerator // P
        digit_path = output / f"digit_{digit_index:02d}_support7_row_major.u8"
        digit_path.write_bytes(digit.astype(np.uint8).tobytes(order="C"))
        digits.append(digit)
        corrections.append({
            "digit_index": digit_index,
            "total_digits": digit_index + 1,
            "driver": driver,
            "divisibility_mismatches": divisibility_mismatches,
            "padded_tail_nonzeros": tail_nonzeros,
            "digit_support": np.count_nonzero(digit, axis=0).astype(int).tolist(),
            "maximum_q_bit_length": int(max(abs(int(value)).bit_length() for value in q.flat)),
            "seconds": time.perf_counter() - digit_started,
            "digit_sha256": digest(digit_path),
            "correction_rhs_sha256": digest(rhs_path),
        })

    q10_path = output / "terminal_q10_support7_row_major.i64le"
    q10_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    census = reconstruction_census(x8, digits)
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 3_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    output_files = [output / "digit_08_support7_row_major.u8", output / "digit_09_support7_row_major.u8", q10_path]
    receipt = {
        "schema": "hc4.third-colon-p181-support7-ten-digit-extension.v1",
        "status": "PASS_P181_SUPPORT7_TEN_DIGIT_LIFT",
        "selection": {"support18_batch_local_columns": list(ACTIVE_BATCH), "residual_local_indices": list(ACTIVE_RESIDUAL)},
        "inputs": {"exact_system_sha256": digest(EXACT), "modular_csr_sha256": digest(MODULAR), "starting_x8_sha256": digest(X8), "starting_q8_sha256": digest(Q8), "driver_sha256": digest(DRIVER)},
        "corrections": corrections,
        "reconstruction_census": census,
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in output_files},
        "resources": resources,
        "declarations": {"starting_p8_replayed": True, "exactly_ten_total_digits": True, "no_eleventh_digit": True, "base_digit_representation": True, "padded_zero_rhs_columns": PADDED - ACTIVE_RHS, "exact_replay_not_attempted": True},
        "claim_boundary": "A finite ten-digit PASS concerns seven fixed source-kernel directions and a reconstruction census only, not a rational lift, target identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
