#!/usr/bin/env -S sage -python
"""Extend the independently audited sparse-four lift from p^2 to p^4."""

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

from lift_p181_sparse4_to_two_digits import read_exact, rr_census, exact_replay


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
RHS_COUNT = 4
PADDED = 114
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-sparse4-two-digit-lift-v2"
EXACT = SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
MODULAR = SOURCE / "integral/A_mod181_coefficient_primitive.csr"
X2 = SOURCE / "lift/X_mod_181_power_2_sparse4_row_major.u16le"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_p181_canonical_residual_114_section_driver"


def file_hash(path: Path) -> str:
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
    offsets, indices, values, rhs = read_exact(EXACT)
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    x = np.frombuffer(X2.read_bytes(), dtype="<u2").reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    modulus = P**2
    residual = rhs - coefficient @ x
    require(int(np.count_nonzero(residual % modulus)) == 0, "starting p2 invariant drift")
    q = residual // modulus
    corrections = []
    rr_snapshots = {}
    final_candidates = None

    for digit_index in (2, 3):
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
        if completed.returncode == 4 and driver is not None and driver.get("status") == "STOP_CANONICAL_RESIDUAL_114_SECTION_NULLITY":
            receipt = {"schema": "hc4.third-colon-p181-sparse4-four-digit-extension.v1", "status": "STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "completed_total_digits": digit_index, "corrections": corrections, "driver": driver, "claim_boundary": "This STOP concerns only the registered sparse-four correction digit."}
            path = output / "extension.json"; path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)})); return 4
        require(completed.returncode == 0 and driver is not None and driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", f"driver failed at digit {digit_index}")
        all_digits = np.frombuffer(padded_solution_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, PADDED)
        tail_nonzeros = int(np.count_nonzero(all_digits[:, RHS_COUNT:]))
        require(tail_nonzeros == 0, f"padded tail nonzero at digit {digit_index}")
        digit = all_digits[:, :RHS_COUNT].astype(np.int64)
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"divisibility failed at digit {digit_index}")
        q = numerator // P
        x = x + modulus * digit
        modulus *= P
        direct_mismatches = int(np.count_nonzero(rhs - coefficient @ x - modulus * q))
        require(direct_mismatches == 0, f"direct invariant failed at digit {digit_index}")
        digit_path = output / f"digit_{digit_index:02d}_sparse4_row_major.u8"
        digit_path.write_bytes(digit.astype(np.uint8).tobytes(order="C"))
        labels, candidates, per_column = rr_census(x, modulus)
        labels_path = output / f"rr_labels_total_digits_{digit_index + 1:02d}.u8"
        labels_path.write_bytes(labels)
        complete = all(candidate is not None for column in candidates for candidate in column)
        rr_snapshots[str(digit_index + 1)] = {"modulus": modulus, "complete": complete, "per_column": per_column, "label_stream_sha256": file_hash(labels_path)}
        final_candidates = candidates
        corrections.append({"digit_index": digit_index, "total_digits": digit_index + 1, "driver": driver, "divisibility_mismatches": divisibility_mismatches, "direct_integer_invariant_mismatches": direct_mismatches, "padded_tail_nonzeros": tail_nonzeros, "digit_support": np.count_nonzero(digit, axis=0).astype(int).tolist(), "cumulative_support": np.count_nonzero(x, axis=0).astype(int).tolist(), "maximum_q_bit_length": int(max(abs(int(v)).bit_length() for v in q.flat)), "seconds": time.perf_counter() - digit_started, "digit_sha256": file_hash(digit_path), "correction_rhs_sha256": file_hash(rhs_path)})

    require(modulus == P**4 == 1_073_283_121, "terminal p4 modulus drift")
    x4_path = output / "X_mod_181_power_4_sparse4_row_major.u32le"
    x4_path.write_bytes(x.astype("<u4").tobytes(order="C"))
    complete = rr_snapshots["4"]["complete"]
    exact_result = rational_output = None
    status = "PASS_P181_SPARSE4_FOUR_DIGIT_LIFT"
    if complete:
        vectors, exact_result = exact_replay(offsets, indices, values, rhs, final_candidates)
        rational_path = output / "rational_sparse4_solution.json"
        rational_path.write_text(json.dumps([[[v.numerator, v.denominator] for v in row] for row in vectors], separators=(",", ":")) + "\n", encoding="ascii")
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}
        status = "PASS_P181_SPARSE4_FOUR_DIGIT_EXACT_RATIONAL_REPLAY"
    receipt = {"schema": "hc4.third-colon-p181-sparse4-four-digit-extension.v1", "status": status, "inputs": {"exact_system_sha256": file_hash(EXACT), "modular_csr_sha256": file_hash(MODULAR), "starting_x2_sha256": file_hash(X2), "driver_sha256": file_hash(DRIVER)}, "corrections": corrections, "terminal_modulus": modulus, "terminal_X": {"path": x4_path.name, "sha256": file_hash(x4_path), "bytes": x4_path.stat().st_size}, "rational_reconstruction": {"snapshots": rr_snapshots, "complete_at_p4": complete, "exact_replay": exact_result, "rational_output": rational_output}, "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, "declarations": {"starting_p2_independently_audited": True, "exactly_four_total_digits": True, "no_fifth_digit": True, "padded_zero_rhs_columns": 110}, "claim_boundary": "A finite four-digit PASS is evidence for four fixed canonical residual sections only, not a general QQ lift, colon, saturation, secant closure, nullcone containment, or HC4 theorem. An exact replay, if present, establishes only four rational residual syzygies in the fixed chart."}
    path = output / "extension.json"; path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(path), "sha256": file_hash(path)})); return 0


if __name__ == "__main__":
    raise SystemExit(main())

