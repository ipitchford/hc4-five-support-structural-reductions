#!/usr/bin/env -S sage -python
"""Recover and independently replay the retained p^6 correction digits."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
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
P4_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-support18-four-digit-extension-v1"
FAILED = CAMPAIGN / "artifacts/third-colon-p181-support18-six-digit-extension-v1"
EXACT = SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
X4 = P4_SOURCE / "X_mod_181_power_4_sparse4_row_major.u32le"


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
    offsets, indices, values, rhs = lift_base.read_exact(EXACT)
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    x = np.frombuffer(X4.read_bytes(), dtype="<u4").reshape(COLUMNS, RHS_COUNT).astype(np.int64)
    modulus = P**4
    residual = rhs - coefficient @ x
    require(int(np.count_nonzero(residual % modulus)) == 0, "starting p4 invariant drift")
    q = residual // modulus
    replays = []

    for digit_index in (4, 5):
        expected_padded = np.zeros((ROWS, PADDED), dtype=np.uint8)
        expected_padded[:, :RHS_COUNT] = (q % P).astype(np.uint8)
        rhs_path = FAILED / f"correction_rhs_digit_{digit_index:02d}_padded114.u8"
        saved_rhs = rhs_path.read_bytes()
        expected_bytes = expected_padded.tobytes(order="C")
        rhs_mismatches = sum(a != b for a, b in zip(expected_bytes, saved_rhs, strict=True))
        require(rhs_mismatches == 0, f"correction RHS drift at digit {digit_index}")
        padded_solution_path = FAILED / f"digit_{digit_index:02d}_padded114.u8"
        padded_solution = np.frombuffer(padded_solution_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, PADDED)
        digit_path = FAILED / f"digit_{digit_index:02d}_support18_row_major.u8"
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).reshape(COLUMNS, RHS_COUNT).astype(np.int64)
        extraction_mismatches = int(np.count_nonzero(padded_solution[:, :RHS_COUNT].astype(np.int64) - digit))
        tail_nonzeros = int(np.count_nonzero(padded_solution[:, RHS_COUNT:]))
        require(extraction_mismatches == 0 and tail_nonzeros == 0, f"saved digit extraction drift at digit {digit_index}")
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"recurrence divisibility failed at digit {digit_index}")
        q = numerator // P
        x = x + modulus * digit
        modulus *= P
        replays.append({
            "digit_index": digit_index,
            "correction_rhs_byte_comparisons": len(saved_rhs),
            "correction_rhs_byte_mismatches": rhs_mismatches,
            "extracted_digit_mismatches": extraction_mismatches,
            "padded_tail_nonzeros": tail_nonzeros,
            "divisibility_mismatches": divisibility_mismatches,
            "digit_sha256": digest(digit_path),
            "padded_solution_sha256": digest(padded_solution_path),
        })

    require(modulus == P**6 == 35_161_828_327_081, "corrected terminal modulus drift")
    x6_path = output / "X_mod_181_power_6_support18_row_major.u64le"
    q6_path = output / "terminal_q6_support18_row_major.i64le"
    x6_path.write_bytes(x.astype("<u8").tobytes(order="C"))
    q6_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "recovery resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-support18-six-digit-extension-recovery.v2",
        "status": "PASS_P181_SUPPORT18_SIX_DIGIT_LIFT_RECOVERED_V2",
        "replays": replays,
        "terminal_modulus": modulus,
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (x6_path, q6_path)},
        "resources": resources,
        "declarations": {"solver_not_executed": True, "failed_v1_retained": True, "amendment_scope_terminal_modulus_literal_only": True, "no_seventh_digit": True},
        "claim_boundary": "This PASS recovers the finite p6 lift for 18 fixed source-kernel directions. It does not prove a rational lift, target identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "recovery.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
