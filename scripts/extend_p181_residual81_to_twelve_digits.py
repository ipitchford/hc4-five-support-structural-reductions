#!/usr/bin/env -S sage -python
"""Extend the sole p^10-unresolved residual direction through p^12."""

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
SUPPORT7_RHS = 7
SUPPORT18_BATCH_COLUMN = 15
SUPPORT7_COLUMN = 4
RESIDUAL_INDEX = 81
PADDED = 114
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
P8_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-eight-digit-extension-v1"
P10_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support7-ten-digit-extension-v1"
EXACT = SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
MODULAR = SOURCE / "integral/A_mod181_coefficient_primitive.csr"
X8 = P8_SOURCE / "X_mod_181_power_8_support18_row_major.u64le"
D8 = P10_SOURCE / "digit_08_support7_row_major.u8"
D9 = P10_SOURCE / "digit_09_support7_row_major.u8"
Q10 = P10_SOURCE / "terminal_q10_support7_row_major.i64le"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_p181_canonical_residual_114_section_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


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
    x8 = np.frombuffer(X8.read_bytes(), dtype="<u8").reshape(COLUMNS, FULL_RHS)[:, SUPPORT18_BATCH_COLUMN].copy()
    d8 = np.frombuffer(D8.read_bytes(), dtype=np.uint8).reshape(COLUMNS, SUPPORT7_RHS)[:, SUPPORT7_COLUMN].astype(np.int64)
    d9 = np.frombuffer(D9.read_bytes(), dtype=np.uint8).reshape(COLUMNS, SUPPORT7_RHS)[:, SUPPORT7_COLUMN].astype(np.int64)
    q = np.frombuffer(Q10.read_bytes(), dtype="<i8").reshape(ROWS, SUPPORT7_RHS)[:, SUPPORT7_COLUMN:SUPPORT7_COLUMN + 1].copy()
    corrections = []
    digits = []

    for digit_index in (10, 11):
        digit_started = time.perf_counter()
        padded = np.zeros((ROWS, PADDED), dtype=np.uint8)
        padded[:, 0] = (q[:, 0] % P).astype(np.uint8)
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
                "schema": "hc4.third-colon-p181-residual81-twelve-digit-extension.v1",
                "status": "STOP_P181_RESIDUAL81_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit_index": digit_index,
                "corrections": corrections,
                "driver": driver,
                "claim_boundary": "This STOP concerns only the fixed residual81 correction digit.",
            }
            path = output / "extension.json"
            path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)}))
            return 4
        require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", f"driver failed at digit {digit_index}")
        all_digits = np.frombuffer(padded_solution_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, PADDED)
        tail_nonzeros = int(np.count_nonzero(all_digits[:, 1:]))
        require(tail_nonzeros == 0, f"padded tail nonzero at digit {digit_index}")
        digit = all_digits[:, :1].astype(np.int64)
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"recurrence divisibility failed at digit {digit_index}")
        q = numerator // P
        digit_path = output / f"digit_{digit_index:02d}_residual81.u8"
        digit_path.write_bytes(digit[:, 0].astype(np.uint8).tobytes(order="C"))
        digits.append(digit[:, 0])
        corrections.append({
            "digit_index": digit_index,
            "total_digits": digit_index + 1,
            "driver": driver,
            "divisibility_mismatches": divisibility_mismatches,
            "padded_tail_nonzeros": tail_nonzeros,
            "digit_support": int(np.count_nonzero(digit)),
            "maximum_q_bit_length": int(max(abs(int(value)).bit_length() for value in q.flat)),
            "seconds": time.perf_counter() - digit_started,
            "digit_sha256": digest(digit_path),
            "correction_rhs_sha256": digest(rhs_path),
        })

    modulus = P**12
    unresolved = 0
    resolved_nonzero = 0
    resolved_zero = 0
    maximum_absolute_numerator = 0
    maximum_denominator = 0
    for row in range(COLUMNS):
        residue = int(x8[row]) + (P**8) * int(d8[row]) + (P**9) * int(d9[row])
        residue += (P**10) * int(digits[0][row]) + (P**11) * int(digits[1][row])
        pair = rr_base.rr(residue, modulus)
        if pair is None:
            unresolved += 1
        elif pair[0] == 0:
            resolved_zero += 1
        else:
            resolved_nonzero += 1
            maximum_absolute_numerator = max(maximum_absolute_numerator, abs(pair[0]))
            maximum_denominator = max(maximum_denominator, pair[1])

    q12_path = output / "terminal_q12_residual81.i64le"
    q12_path.write_bytes(q[:, 0].astype("<i8").tobytes(order="C"))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 3_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    output_files = [output / "digit_10_residual81.u8", output / "digit_11_residual81.u8", q12_path]
    receipt = {
        "schema": "hc4.third-colon-p181-residual81-twelve-digit-extension.v1",
        "status": "PASS_P181_RESIDUAL81_TWELVE_DIGIT_LIFT",
        "selection": {"support18_batch_local_column": SUPPORT18_BATCH_COLUMN, "support7_local_column": SUPPORT7_COLUMN, "residual_local_index": RESIDUAL_INDEX},
        "inputs": {"exact_system_sha256": digest(EXACT), "modular_csr_sha256": digest(MODULAR), "starting_x8_sha256": digest(X8), "digit8_support7_sha256": digest(D8), "digit9_support7_sha256": digest(D9), "starting_q10_sha256": digest(Q10), "driver_sha256": digest(DRIVER)},
        "corrections": corrections,
        "reconstruction_census": {"modulus": modulus, "equal_height_bound": math.isqrt((modulus - 1) // 2), "coordinate_count": COLUMNS, "unresolved_count": unresolved, "resolved_nonzero_count": resolved_nonzero, "resolved_zero_count": resolved_zero, "maximum_absolute_numerator": maximum_absolute_numerator, "maximum_denominator": maximum_denominator},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in output_files},
        "resources": resources,
        "declarations": {"starting_p10_replayed": True, "exactly_twelve_total_digits": True, "no_thirteenth_digit": True, "single_preselected_column": True, "padded_zero_rhs_columns": 113, "exact_replay_not_attempted": True},
        "claim_boundary": "A finite twelve-digit PASS concerns one fixed source-kernel direction and a reconstruction census only, not a rational lift, target identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
