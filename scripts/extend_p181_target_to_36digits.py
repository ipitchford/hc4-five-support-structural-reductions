#!/usr/bin/env -S sage -python
"""Extend the independently replayed fixed-main target from p^24 to p^36."""

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
P24_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-24digit-extension-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge.i64csr"
MODULAR = SOURCE / "A_Z_mod181_fixed_gauge.csr"
X24 = P24_SOURCE / "X_mod_181_power_24.json"
Q24 = P24_SOURCE / "terminal_q24.i64le"
P24_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-24digit-extension-independent-audit.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_coefficient():
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy(); cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy(); cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy(); cursor += 8 * nonzeros
    cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(P24_AUDIT.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_24DIGIT_LIFT_REPLAY", "p24 audit status drift")
    require(audit["bound_hashes"]["x24"] == digest(X24) and audit["bound_hashes"]["q24"] == digest(Q24), "p24 audit input drift")
    coefficient = read_coefficient()
    x24 = [int(value) for value in json.loads(X24.read_text(encoding="utf-8"))]
    q = np.frombuffer(Q24.read_bytes(), dtype="<i8").copy()
    require(len(x24) == COLUMNS and len(q) == ROWS, "p24 state dimension drift")
    digits = []
    corrections = []
    for digit_index in range(24, 36):
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
            receipt = {"schema": "hc4.third-colon-p181-target-36digit-extension.v1", "status": "STOP_P181_TARGET_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "corrections": corrections, "driver": driver, "claim_boundary": "This STOP concerns the fixed-main p-adic target correction only."}
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
        maximum_q_bits = max(abs(int(value)).bit_length() for value in q)
        require(maximum_q_bits < 63, f"q exceeds signed 64-bit at digit {digit_index}")
        digits.append(digit)
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "driver": driver, "digit_sha256": digest(digit_path), "correction_rhs_sha256": digest(rhs_path), "divisibility_mismatches": divisibility_mismatches, "digit_support": int(np.count_nonzero(digit)), "maximum_q_bit_length": maximum_q_bits, "seconds": time.perf_counter() - digit_started})

    starting_modulus = P**24
    x36 = []
    for column in range(COLUMNS):
        value = x24[column]
        place = starting_modulus
        for digit in digits:
            value += place * int(digit[column])
            place *= P
        x36.append(value)
    terminal_modulus = P**36
    require(all(0 <= value < terminal_modulus for value in x36), "X36 residue range drift")
    census = {"coordinate_count": COLUMNS, "resolved_zero_count": 0, "resolved_nonzero_count": 0, "unresolved_count": 0, "maximum_absolute_numerator": 0, "maximum_denominator": 0}
    stability = {"p24_zero_count": 0, "p24_zero_stable_at_p36": 0, "p24_zero_changed_at_p36": 0, "p24_zero_unresolved_at_p36": 0, "p24_nonzero_count": 0, "p24_nonzero_stable_at_p36": 0, "p24_nonzero_changed_at_p36": 0, "p24_nonzero_unresolved_at_p36": 0}
    for old_value, new_value in zip(x24, x36):
        pair24 = rr_base.rr(old_value, starting_modulus)
        pair36 = rr_base.rr(new_value, terminal_modulus)
        if pair36 is None:
            census["unresolved_count"] += 1
        elif pair36[0] == 0:
            census["resolved_zero_count"] += 1
        else:
            census["resolved_nonzero_count"] += 1
            census["maximum_absolute_numerator"] = max(census["maximum_absolute_numerator"], abs(pair36[0]))
            census["maximum_denominator"] = max(census["maximum_denominator"], pair36[1])
        if pair24 == (0, 1):
            stability["p24_zero_count"] += 1
            if pair36 is None:
                stability["p24_zero_unresolved_at_p36"] += 1
            elif pair36 == pair24:
                stability["p24_zero_stable_at_p36"] += 1
            else:
                stability["p24_zero_changed_at_p36"] += 1
        elif pair24 is not None:
            stability["p24_nonzero_count"] += 1
            if pair36 is None:
                stability["p24_nonzero_unresolved_at_p36"] += 1
            elif pair36 == pair24:
                stability["p24_nonzero_stable_at_p36"] += 1
            else:
                stability["p24_nonzero_changed_at_p36"] += 1
    census["equal_height_bound"] = math.isqrt((terminal_modulus - 1) // 2)
    x36_path = output / "X_mod_181_power_36.json"
    q36_path = output / "terminal_q36.i64le"
    x36_path.write_text(json.dumps([str(value) for value in x36], separators=(",", ":")) + "\n", encoding="ascii")
    q36_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 2400 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-36digit-extension.v1",
        "status": "PASS_P181_TARGET_36DIGIT_LIFT",
        "inputs": {"integral_sha256": digest(INTEGRAL), "modular_csr_sha256": digest(MODULAR), "x24_sha256": digest(X24), "q24_sha256": digest(Q24), "p24_independent_audit_sha256": digest(P24_AUDIT), "driver_sha256": digest(DRIVER)},
        "corrections": corrections,
        "terminal_modulus": str(terminal_modulus),
        "reconstruction_census": census,
        "p24_to_p36_stability": stability,
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (x36_path, q36_path)},
        "resources": resources,
        "declarations": {"fixed_main_gauge": True, "kernel_adjustment_forbidden": True, "denominator_model_forbidden": True, "exactly_twelve_new_digits": True, "no_thirty_seventh_digit": True, "exact_target_replay_not_attempted": True},
        "claim_boundary": "A finite p36 PASS is evidence for the fixed-main target lift, a height census, and candidate stability only, not rational target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
