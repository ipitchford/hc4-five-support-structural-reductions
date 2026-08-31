#!/usr/bin/env -S sage -python
"""Extend the independently replayed fixed-main target from p^48 to p^54."""

from __future__ import annotations

import argparse
import json
import math
import resource
import struct
import subprocess
import time
from pathlib import Path

import numpy as np

import extend_p181_target_to_36digits as base
import reconstruct_p181_sparse4_exact_rational as rr_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1"
P48_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-48digit-extension-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge.i64csr"
MODULAR = SOURCE / "A_Z_mod181_fixed_gauge.csr"
X48 = P48_SOURCE / "X_mod_181_power_48.json"
Q48 = P48_SOURCE / "terminal_q48.i64le"
P48_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-48digit-extension-independent-audit.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(P48_AUDIT.read_text(encoding="utf-8"))
    base.require(audit.get("status") == "PASS_INDEPENDENT_P181_TARGET_48DIGIT_LIFT_REPLAY", "p48 audit status drift")
    base.require(audit["bound_hashes"]["x48"] == base.digest(X48) and audit["bound_hashes"]["q48"] == base.digest(Q48), "p48 audit input drift")
    coefficient = base.read_coefficient()
    x48 = [int(value) for value in json.loads(X48.read_text(encoding="utf-8"))]
    q = np.frombuffer(Q48.read_bytes(), dtype="<i8").copy()
    base.require(len(x48) == COLUMNS and len(q) == ROWS, "p48 state dimension drift")
    digits = []
    corrections = []
    for digit_index in range(48, 54):
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
            receipt = {"schema": "hc4.third-colon-p181-target-54digit-extension.v1", "status": "STOP_P181_TARGET_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "corrections": corrections, "driver": driver, "claim_boundary": "This STOP concerns the fixed-main p-adic target correction only."}
            path = output / "extension.json"
            path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)}))
            return 4
        base.require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE" and driver.get("replay_mismatches") == 0, f"driver failed at digit {digit_index}")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        base.require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        base.require(divisibility_mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        q = numerator // P
        maximum_q_bits = max(abs(int(value)).bit_length() for value in q)
        base.require(maximum_q_bits < 63, f"q exceeds signed 64-bit at digit {digit_index}")
        digits.append(digit)
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "driver": driver, "digit_sha256": base.digest(digit_path), "correction_rhs_sha256": base.digest(rhs_path), "divisibility_mismatches": divisibility_mismatches, "digit_support": int(np.count_nonzero(digit)), "maximum_q_bit_length": maximum_q_bits, "seconds": time.perf_counter() - digit_started})

    starting_modulus = P**48
    x54 = []
    for column in range(COLUMNS):
        value = x48[column]
        place = starting_modulus
        for digit in digits:
            value += place * int(digit[column])
            place *= P
        x54.append(value)
    terminal_modulus = P**54
    base.require(all(0 <= value < terminal_modulus for value in x54), "X54 residue range drift")
    census = {"coordinate_count": COLUMNS, "resolved_zero_count": 0, "resolved_nonzero_count": 0, "unresolved_count": 0, "maximum_absolute_numerator": 0, "maximum_denominator": 0}
    stability = {"p48_zero_count": 0, "p48_zero_stable_at_p54": 0, "p48_zero_changed_at_p54": 0, "p48_zero_unresolved_at_p54": 0, "p48_nonzero_count": 0, "p48_nonzero_stable_at_p54": 0, "p48_nonzero_changed_at_p54": 0, "p48_nonzero_unresolved_at_p54": 0}
    for old_value, new_value in zip(x48, x54):
        pair48 = rr_base.rr(old_value, starting_modulus)
        pair54 = rr_base.rr(new_value, terminal_modulus)
        if pair54 is None:
            census["unresolved_count"] += 1
        elif pair54[0] == 0:
            census["resolved_zero_count"] += 1
        else:
            census["resolved_nonzero_count"] += 1
            census["maximum_absolute_numerator"] = max(census["maximum_absolute_numerator"], abs(pair54[0]))
            census["maximum_denominator"] = max(census["maximum_denominator"], pair54[1])
        if pair48 == (0, 1):
            stability["p48_zero_count"] += 1
            key = "p48_zero_unresolved_at_p54" if pair54 is None else "p48_zero_stable_at_p54" if pair54 == pair48 else "p48_zero_changed_at_p54"
            stability[key] += 1
        elif pair48 is not None:
            stability["p48_nonzero_count"] += 1
            key = "p48_nonzero_unresolved_at_p54" if pair54 is None else "p48_nonzero_stable_at_p54" if pair54 == pair48 else "p48_nonzero_changed_at_p54"
            stability[key] += 1
    census["equal_height_bound"] = math.isqrt((terminal_modulus - 1) // 2)
    x54_path = output / "X_mod_181_power_54.json"
    q54_path = output / "terminal_q54.i64le"
    x54_path.write_text(json.dumps([str(value) for value in x54], separators=(",", ":")) + "\n", encoding="ascii")
    q54_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    base.require(resources["wall_seconds"] < 1800 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-54digit-extension.v1",
        "status": "PASS_P181_TARGET_54DIGIT_LIFT",
        "inputs": {"integral_sha256": base.digest(INTEGRAL), "modular_csr_sha256": base.digest(MODULAR), "x48_sha256": base.digest(X48), "q48_sha256": base.digest(Q48), "p48_independent_audit_sha256": base.digest(P48_AUDIT), "driver_sha256": base.digest(DRIVER), "frozen_helper_sha256": base.digest(Path(base.__file__))},
        "corrections": corrections,
        "terminal_modulus": str(terminal_modulus),
        "reconstruction_census": census,
        "p48_to_p54_stability": stability,
        "outputs": {path.name: {"sha256": base.digest(path), "bytes": path.stat().st_size} for path in (x54_path, q54_path)},
        "resources": resources,
        "declarations": {"fixed_main_gauge": True, "kernel_adjustment_forbidden": True, "denominator_model_forbidden": True, "exactly_six_new_digits": True, "no_fifty_fifth_digit": True, "exact_target_replay_not_attempted": True},
        "claim_boundary": "A finite p54 PASS is evidence for the fixed-main target lift, a height census, and candidate stability only. Zero unresolved coordinates license a separate exact replay; this PASS alone is not rational target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    path = output / "extension.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": base.digest(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
