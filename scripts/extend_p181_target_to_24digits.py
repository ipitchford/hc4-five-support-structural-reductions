#!/usr/bin/env -S sage -python
"""Extend the independently replayed fixed-main target from p^18 to p^24."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

import reconstruct_p181_sparse4_exact_rational as rr_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1"
P18_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-fixed-block-denominator-18digit-test-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge.i64csr"
MODULAR = SOURCE / "A_Z_mod181_fixed_gauge.csr"
X18 = P18_SOURCE / "X_mod_181_power_18.json"
P18_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-fixed-block-denominator-18digit-test-independent-audit.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral():
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy(); cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy(); cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy(); cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows, offset=cursor).copy(); cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(P18_AUDIT.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_18DIGIT_LIFT_AND_FIXED_DENOMINATOR_FALSIFICATION_REPLAY", "p18 audit status drift")
    require(audit["bound_hashes"]["integral"] == digest(INTEGRAL) and audit["bound_hashes"]["X18"] == digest(X18), "p18 audit input drift")
    offsets, indices, values, rhs = read_integral()
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    x18 = [int(value) for value in json.loads(X18.read_text(encoding="utf-8"))]
    require(len(x18) == COLUMNS, "X18 dimension drift")
    modulus = P**18
    q_values = []
    starting_mismatches = 0
    for row in range(ROWS):
        total = sum(int(values[position]) * x18[int(indices[position])] for position in range(int(offsets[row]), int(offsets[row + 1])))
        residual = int(rhs[row]) - total
        starting_mismatches += residual % modulus != 0
        q_values.append(residual // modulus)
    require(starting_mismatches == 0, "X18 exact divisibility replay failed")
    require(max(abs(value).bit_length() for value in q_values) < 63, "q18 exceeds signed 64-bit continuation")
    q = np.asarray(q_values, dtype=np.int64)
    digits = []
    corrections = []

    for digit_index in range(18, 24):
        digit_started = time.perf_counter()
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = output / f"digit_{digit_index:02d}.u8"
        stdout_path = output / f"digit_{digit_index:02d}.stdout.txt"
        stderr_path = output / f"digit_{digit_index:02d}.stderr.txt"
        rhs_path.write_bytes((q % P).astype(np.uint8).tobytes(order="C"))
        completed = subprocess.run([str(DRIVER), "--csr", str(MODULAR), "--rhs", str(rhs_path), "--solution-output", str(digit_path)], cwd=CAMPAIGN, text=True, capture_output=True)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD181":
            receipt = {"schema": "hc4.third-colon-p181-target-24digit-extension.v1", "status": "STOP_P181_TARGET_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "corrections": corrections, "driver": driver, "claim_boundary": "This STOP concerns the fixed-main p-adic target correction only."}
            path = output / "extension.json"
            path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)}))
            return 4
        require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE" and driver.get("replay_mismatches") == 0, f"driver failed at digit {digit_index}")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        q = numerator // P
        require(max(abs(int(value)).bit_length() for value in q) < 63, f"q exceeds signed 64-bit at digit {digit_index}")
        digits.append(digit)
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "driver": driver, "digit_sha256": digest(digit_path), "correction_rhs_sha256": digest(rhs_path), "divisibility_mismatches": divisibility_mismatches, "digit_support": int(np.count_nonzero(digit)), "maximum_q_bit_length": max(abs(int(value)).bit_length() for value in q), "seconds": time.perf_counter() - digit_started})

    require(modulus == P**18, "starting modulus drift")
    x24 = []
    for column in range(COLUMNS):
        value = x18[column]
        place = modulus
        for digit in digits:
            value += place * int(digit[column])
            place *= P
        x24.append(value)
    terminal_modulus = P**24
    require(all(0 <= value < terminal_modulus for value in x24), "X24 residue range drift")
    unresolved = 0
    resolved_nonzero = 0
    resolved_zero = 0
    maximum_absolute_numerator = 0
    maximum_denominator = 0
    for value in x24:
        pair = rr_base.rr(value, terminal_modulus)
        if pair is None:
            unresolved += 1
        elif pair[0] == 0:
            resolved_zero += 1
        else:
            resolved_nonzero += 1
            maximum_absolute_numerator = max(maximum_absolute_numerator, abs(pair[0]))
            maximum_denominator = max(maximum_denominator, pair[1])
    x24_path = output / "X_mod_181_power_24.json"
    q24_path = output / "terminal_q24.i64le"
    x24_path.write_text(json.dumps([str(value) for value in x24], separators=(",", ":")) + "\n", encoding="ascii")
    q24_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 1800 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-24digit-extension.v1",
        "status": "PASS_P181_TARGET_24DIGIT_LIFT",
        "inputs": {"integral_sha256": digest(INTEGRAL), "modular_csr_sha256": digest(MODULAR), "x18_sha256": digest(X18), "p18_independent_audit_sha256": digest(P18_AUDIT), "driver_sha256": digest(DRIVER)},
        "starting_divisibility_mismatches": starting_mismatches,
        "corrections": corrections,
        "terminal_modulus": str(terminal_modulus),
        "reconstruction_census": {"equal_height_bound": math.isqrt((terminal_modulus - 1) // 2), "coordinate_count": COLUMNS, "unresolved_count": unresolved, "resolved_nonzero_count": resolved_nonzero, "resolved_zero_count": resolved_zero, "maximum_absolute_numerator": maximum_absolute_numerator, "maximum_denominator": maximum_denominator},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (x24_path, q24_path)},
        "resources": resources,
        "declarations": {"fixed_main_gauge": True, "kernel_adjustment_forbidden": True, "denominator_model_forbidden": True, "exactly_six_new_digits": True, "no_twenty_fifth_digit": True, "exact_target_replay_not_attempted": True},
        "claim_boundary": "A finite p24 PASS is evidence for the fixed-main target lift and a height census only, not rational target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
