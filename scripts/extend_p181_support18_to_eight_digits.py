#!/usr/bin/env -S sage -python
"""Extend the recovered next-18 residue from p^6 through exactly p^8."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

import lift_p181_sparse4_to_two_digits as lift_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
RHS_COUNT = 18
PADDED = 114
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
P6_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-six-digit-extension-v2"
EXACT = SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
MODULAR = SOURCE / "integral/A_mod181_coefficient_primitive.csr"
X6 = P6_SOURCE / "X_mod_181_power_6_support18_row_major.u64le"
Q6 = P6_SOURCE / "terminal_q6_support18_row_major.i64le"
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
    lift_base.RHS_COUNT = RHS_COUNT
    offsets, indices, values, _rhs = lift_base.read_exact(EXACT)
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    x = np.frombuffer(X6.read_bytes(), dtype="<u8").reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    q = np.frombuffer(Q6.read_bytes(), dtype="<i8").reshape(ROWS, RHS_COUNT).astype(np.int64)
    modulus = P**6
    require(int(x.min()) >= 0 and int(x.max()) < modulus, "starting p6 residue range drift")
    corrections = []

    for digit_index in (6, 7):
        digit_started = time.perf_counter()
        padded = np.zeros((ROWS, PADDED), dtype=np.uint8)
        padded[:, :RHS_COUNT] = (q % P).astype(np.uint8)
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}_padded114.u8"
        padded_solution_path = output / f"digit_{digit_index:02d}_padded114.u8"
        stdout_path = output / f"digit_{digit_index:02d}.stdout.txt"
        stderr_path = output / f"digit_{digit_index:02d}.stderr.txt"
        rhs_path.write_bytes(padded.tobytes(order="C"))
        completed = subprocess.run([str(DRIVER), "--csr", str(MODULAR), "--rhs", str(rhs_path), "--solution-output", str(padded_solution_path)], cwd=CAMPAIGN, text=True, capture_output=True)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_CANONICAL_RESIDUAL_114_SECTION_NULLITY":
            receipt = {"schema": "hc4.third-colon-p181-support18-eight-digit-extension.v1", "status": "STOP_P181_SUPPORT18_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "corrections": corrections, "driver": driver, "claim_boundary": "This STOP concerns only the fixed support18 correction digit."}
            path = output / "extension.json"
            path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)}))
            return 4
        require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", f"driver failed at digit {digit_index}")
        all_digits = np.frombuffer(padded_solution_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, PADDED)
        tail_nonzeros = int(np.count_nonzero(all_digits[:, RHS_COUNT:]))
        require(tail_nonzeros == 0, f"padded tail nonzero at digit {digit_index}")
        digit = all_digits[:, :RHS_COUNT].astype(np.int64)
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"recurrence divisibility failed at digit {digit_index}")
        q = numerator // P
        x = x + modulus * digit
        modulus *= P
        require(int(x.min()) >= 0 and int(x.max()) < modulus, f"cumulative residue range drift at digit {digit_index}")
        digit_path = output / f"digit_{digit_index:02d}_support18_row_major.u8"
        digit_path.write_bytes(digit.astype(np.uint8).tobytes(order="C"))
        corrections.append({"digit_index": digit_index, "total_digits": digit_index + 1, "driver": driver, "divisibility_mismatches": divisibility_mismatches, "padded_tail_nonzeros": tail_nonzeros, "digit_support": np.count_nonzero(digit, axis=0).astype(int).tolist(), "cumulative_support": np.count_nonzero(x, axis=0).astype(int).tolist(), "maximum_q_bit_length": int(max(abs(int(value)).bit_length() for value in q.flat)), "seconds": time.perf_counter() - digit_started, "digit_sha256": digest(digit_path), "correction_rhs_sha256": digest(rhs_path)})

    require(modulus == P**8 == 1_151_936_657_823_500_641, "terminal p8 modulus drift")
    x8_path = output / "X_mod_181_power_8_support18_row_major.u64le"
    q8_path = output / "terminal_q8_support18_row_major.i64le"
    x8_path.write_bytes(x.astype("<u8").tobytes(order="C"))
    q8_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    receipt = {
        "schema": "hc4.third-colon-p181-support18-eight-digit-extension.v1",
        "status": "PASS_P181_SUPPORT18_EIGHT_DIGIT_LIFT",
        "inputs": {"exact_system_sha256": digest(EXACT), "modular_csr_sha256": digest(MODULAR), "starting_x6_sha256": digest(X6), "starting_q6_sha256": digest(Q6), "driver_sha256": digest(DRIVER)},
        "corrections": corrections,
        "terminal_modulus": modulus,
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (x8_path, q8_path)},
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "declarations": {"starting_p6_recovered_and_replayed": True, "exactly_eight_total_digits": True, "no_ninth_digit": True, "terminal_64bit_representation": True, "padded_zero_rhs_columns": 96},
        "claim_boundary": "A finite eight-digit PASS is evidence for 18 fixed source-kernel directions only, not a rational lift, target identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
