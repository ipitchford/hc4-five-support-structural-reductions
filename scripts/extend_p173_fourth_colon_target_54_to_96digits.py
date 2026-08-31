#!/usr/bin/env -S sage -python
"""Extend the independently audited p173 fourth-colon target to p^96."""

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


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
SYSTEM = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
P54 = CAMPAIGN / "artifacts/fourth-colon-p173-target-54digit-extension-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
MODULAR = SYSTEM / "A_Z_mod173_fixed_gauge.csr"
X54 = P54 / "X_mod_173_power_54.json"
Q54 = P54 / "terminal_q54.i64le"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-54digit-extension-independent-audit.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod173_fourth_target_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_coefficient() -> csr_matrix:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI173", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy()
    cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy()
    cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy()
    cursor += 8 * nonzeros + 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)


def reconstruct(residue: int, modulus: int) -> tuple[int, int] | None:
    residue %= modulus
    if residue == 0:
        return 0, 1
    bound = math.isqrt((modulus - 1) // 2)
    old_r, remainder = modulus, residue
    old_t, coefficient = 0, 1
    while abs(remainder) > bound:
        quotient = old_r // remainder
        old_r, remainder = remainder, old_r - quotient * remainder
        old_t, coefficient = coefficient, old_t - quotient * coefficient
    numerator, denominator = remainder, coefficient
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if denominator <= 0 or abs(numerator) > bound or denominator > bound:
        return None
    if math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus:
        return None
    return numerator, denominator


def census(vector: list[int], modulus: int) -> tuple[dict[str, int], list[tuple[int, int] | None]]:
    result = {
        "coordinate_count": COLUMNS,
        "resolved_zero_count": 0,
        "resolved_nonzero_count": 0,
        "unresolved_count": 0,
        "maximum_absolute_numerator": 0,
        "maximum_denominator": 0,
        "equal_height_bound": math.isqrt((modulus - 1) // 2),
    }
    pairs = []
    for value in vector:
        pair = reconstruct(value, modulus)
        pairs.append(pair)
        if pair is None:
            result["unresolved_count"] += 1
        elif pair[0] == 0:
            result["resolved_zero_count"] += 1
        else:
            result["resolved_nonzero_count"] += 1
            result["maximum_absolute_numerator"] = max(result["maximum_absolute_numerator"], abs(pair[0]))
            result["maximum_denominator"] = max(result["maximum_denominator"], pair[1])
    return result, pairs


def stability(old: list[tuple[int, int] | None], new: list[tuple[int, int] | None]) -> dict[str, int]:
    result = {
        "old_resolved_zero_count": 0, "old_resolved_zero_stable": 0,
        "old_resolved_zero_changed": 0, "old_resolved_zero_became_unresolved": 0,
        "old_resolved_nonzero_count": 0, "old_resolved_nonzero_stable": 0,
        "old_resolved_nonzero_changed": 0, "old_resolved_nonzero_became_unresolved": 0,
    }
    for previous, current in zip(old, new, strict=True):
        if previous is None:
            continue
        kind = "zero" if previous[0] == 0 else "nonzero"
        result[f"old_resolved_{kind}_count"] += 1
        if current is None:
            result[f"old_resolved_{kind}_became_unresolved"] += 1
        elif current == previous:
            result[f"old_resolved_{kind}_stable"] += 1
        else:
            result[f"old_resolved_{kind}_changed"] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(P54_AUDIT.read_text(encoding="ascii"))
    require(audit.get("status") == "PASS_INDEPENDENT_P173_FOURTH_COLON_54DIGIT_LIFT_REPLAY", "p54 audit status drift")
    require(audit["bound_hashes"]["x54"] == digest(X54) and audit["bound_hashes"]["q54"] == digest(Q54), "p54 endpoint drift")
    coefficient = read_coefficient()
    x = [int(value) for value in json.loads(X54.read_text(encoding="ascii"))]
    q = np.frombuffer(Q54.read_bytes(), dtype="<i8").copy()
    require(len(x) == COLUMNS and len(q) == ROWS, "p54 state dimension drift")
    modulus = P**54
    census54, pairs54 = census(x, modulus)
    require(census54["unresolved_count"] == 8_961, "p54 census drift")
    checkpoint_pairs = {54: pairs54}
    checkpoint_data = {"54": census54}
    corrections = []

    for digit_index in range(54, 96):
        digit_started = time.perf_counter()
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = output / f"digit_{digit_index:02d}.u8"
        stdout_path = output / f"digit_{digit_index:02d}.stdout.txt"
        stderr_path = output / f"digit_{digit_index:02d}.stderr.txt"
        rhs_path.write_bytes((q % P).astype(np.uint8).tobytes(order="C"))
        completed = subprocess.run(
            [str(DRIVER), "--csr", str(MODULAR), "--rhs", str(rhs_path), "--solution-output", str(digit_path)],
            cwd=CAMPAIGN, text=True, capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD173":
            receipt = {"schema": "hc4.fourth-colon-p173-96digit-extension.v1", "status": "STOP_P173_FOURTH_COLON_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit_index": digit_index, "corrections": corrections, "driver": driver}
            path = output / "extension.json"; path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(path)})); return 4
        require(completed.returncode == 0 and driver and driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD173_EXPLICIT_TARGET_SOLVE" and driver.get("replay_mismatches") == 0, f"driver failed at digit {digit_index}")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        numerator = q - coefficient @ digit
        mismatches = int(np.count_nonzero(numerator % P))
        require(len(digit) == COLUMNS and mismatches == 0, f"correction recurrence failed at digit {digit_index}")
        q = numerator // P
        x = [left + modulus * int(right) for left, right in zip(x, digit, strict=True)]
        modulus *= P
        maximum_q_bits = max(abs(int(value)).bit_length() for value in q)
        require(maximum_q_bits < 63, f"q exceeds int64 at digit {digit_index}")
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "driver": driver, "digit_sha256": digest(digit_path), "correction_rhs_sha256": digest(rhs_path), "divisibility_mismatches": mismatches, "maximum_q_bit_length": maximum_q_bits, "seconds": time.perf_counter() - digit_started})
        cumulative = digit_index + 1
        if cumulative in (72, 84, 96):
            snapshot, pairs = census(x, modulus)
            checkpoint_data[str(cumulative)] = snapshot
            checkpoint_pairs[cumulative] = pairs

    require(modulus == P**96, "terminal modulus drift")
    x_path = output / "X_mod_173_power_96.json"
    q_path = output / "terminal_q96.i64le"
    x_path.write_text(json.dumps([str(value) for value in x], separators=(",", ":")) + "\n", encoding="ascii")
    q_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    stability_data = {
        "p54_to_p72": stability(checkpoint_pairs[54], checkpoint_pairs[72]),
        "p72_to_p84": stability(checkpoint_pairs[72], checkpoint_pairs[84]),
        "p84_to_p96": stability(checkpoint_pairs[84], checkpoint_pairs[96]),
    }
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 6_000 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.fourth-colon-p173-96digit-extension.v1",
        "status": "PASS_P173_FOURTH_COLON_96DIGIT_LIFT",
        "inputs": {"integral_sha256": digest(INTEGRAL), "modular_csr_sha256": digest(MODULAR), "x54_sha256": digest(X54), "q54_sha256": digest(Q54), "p54_independent_audit_sha256": digest(P54_AUDIT), "driver_sha256": digest(DRIVER)},
        "corrections": corrections,
        "terminal_modulus": str(modulus),
        "reconstruction_checkpoints": checkpoint_data,
        "checkpoint_stability": stability_data,
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (x_path, q_path)},
        "resources": resources,
        "declarations": {"fixed_gauge": True, "kernel_adjustment_forbidden": True, "exactly_forty_two_new_digits": True, "no_ninety_seventh_digit": True, "exact_target_replay_not_attempted": True},
        "claim_boundary": "A p96 PASS is a finite fixed-gauge lift and height diagnostic only. Exact and source-level replays remain separate; no colon equality, saturation, nullcone containment, or HC4 theorem follows."
    }
    path = output / "extension.json"; path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(path), "sha256": digest(path)})); return 0


if __name__ == "__main__":
    raise SystemExit(main())
