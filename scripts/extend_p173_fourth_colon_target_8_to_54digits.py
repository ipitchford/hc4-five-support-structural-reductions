#!/usr/bin/env -S sage -python
"""Replay p^8 and extend the fixed-gauge fourth-colon target to p^54."""

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
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
SYSTEM = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
P8 = CAMPAIGN / "artifacts/fourth-colon-p173-augmented-nullspace-8digit-lift-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
MODULAR = SYSTEM / "A_Z_mod173_fixed_gauge.csr"
DIGIT_ZERO = SYSTEM / "solution_mod173.u8"
X8 = P8 / "X_mod_173_power_8.u64le"
P8_RECEIPT = P8 / "lift.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod173_fourth_target_driver"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_system() -> tuple[csr_matrix, np.ndarray]:
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
    cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows, offset=cursor).copy()
    cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64), rhs


def checkpoint_census(vector: list[int], modulus: int) -> tuple[dict[str, int], list[tuple[int, int] | None]]:
    census = {
        "coordinate_count": COLUMNS,
        "resolved_zero_count": 0,
        "resolved_nonzero_count": 0,
        "unresolved_count": 0,
        "maximum_absolute_numerator": 0,
        "maximum_denominator": 0,
        "equal_height_bound": math.isqrt((modulus - 1) // 2),
    }
    pairs: list[tuple[int, int] | None] = []
    for value in vector:
        pair = rr_base.rr(value, modulus)
        pairs.append(pair)
        if pair is None:
            census["unresolved_count"] += 1
        elif pair[0] == 0:
            census["resolved_zero_count"] += 1
        else:
            census["resolved_nonzero_count"] += 1
            census["maximum_absolute_numerator"] = max(census["maximum_absolute_numerator"], abs(pair[0]))
            census["maximum_denominator"] = max(census["maximum_denominator"], pair[1])
    return census, pairs


def stability(old: list[tuple[int, int] | None], new: list[tuple[int, int] | None]) -> dict[str, int]:
    result = {
        "old_resolved_zero_count": 0,
        "old_resolved_zero_stable": 0,
        "old_resolved_zero_changed": 0,
        "old_resolved_zero_became_unresolved": 0,
        "old_resolved_nonzero_count": 0,
        "old_resolved_nonzero_stable": 0,
        "old_resolved_nonzero_changed": 0,
        "old_resolved_nonzero_became_unresolved": 0,
    }
    for previous, current in zip(old, new):
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

    p8_receipt = json.loads(P8_RECEIPT.read_text(encoding="utf-8"))
    require(p8_receipt.get("status") == "PASS_P173_FOURTH_COLON_AUGMENTED_NULLSPACE_8DIGIT_LIFT", "p8 status drift")
    require(p8_receipt["terminal_X"]["sha256"] == digest(X8), "p8 endpoint hash drift")
    coefficient, rhs = read_system()

    digit_arrays = [np.frombuffer(DIGIT_ZERO.read_bytes(), dtype=np.uint8).astype(np.int64)]
    digit_arrays.extend(
        np.frombuffer((P8 / f"digit_{index}.u8").read_bytes(), dtype=np.uint8).astype(np.int64)
        for index in range(1, 8)
    )
    require(all(len(digit) == COLUMNS for digit in digit_arrays), "p8 digit dimension drift")
    q_numerator = rhs - coefficient @ digit_arrays[0]
    require(int(np.count_nonzero(q_numerator % P)) == 0, "digit-zero replay divisibility failure")
    q = q_numerator // P
    replayed_x8 = [int(value) for value in digit_arrays[0]]
    place = P
    replay_records = []
    for index, digit in enumerate(digit_arrays[1:], start=1):
        numerator = q - coefficient @ digit
        mismatches = int(np.count_nonzero(numerator % P))
        require(mismatches == 0, f"saved p8 digit {index} replay divisibility failure")
        q = numerator // P
        replayed_x8 = [value + place * int(item) for value, item in zip(replayed_x8, digit)]
        place *= P
        replay_records.append({
            "digit_index": index,
            "digit_sha256": digest(P8 / f"digit_{index}.u8"),
            "divisibility_mismatches": mismatches,
            "maximum_q_bit_length": max(abs(int(value)).bit_length() for value in q),
        })
    x8_saved = [int(value) for value in np.frombuffer(X8.read_bytes(), dtype="<u8")]
    require(replayed_x8 == x8_saved and place == P**8, "saved p8 endpoint replay mismatch")

    new_digits: list[np.ndarray] = []
    corrections = []
    checkpoint_pairs: dict[int, list[tuple[int, int] | None]] = {}
    checkpoint_data: dict[str, object] = {}
    current_x = list(x8_saved)
    current_place = P**8

    for digit_index in range(8, 54):
        digit_started = time.perf_counter()
        rhs_path = output / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = output / f"digit_{digit_index:02d}.u8"
        stdout_path = output / f"digit_{digit_index:02d}.stdout.txt"
        stderr_path = output / f"digit_{digit_index:02d}.stderr.txt"
        rhs_path.write_bytes((q % P).astype(np.uint8).tobytes(order="C"))
        completed = subprocess.run(
            [str(DRIVER), "--csr", str(MODULAR), "--rhs", str(rhs_path),
             "--solution-output", str(digit_path)],
            cwd=CAMPAIGN, text=True, capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD173":
            receipt = {
                "schema": "hc4.decimic-j2-secant-r10-p173-fourth-colon-54digit-extension.v1",
                "status": "STOP_P173_FOURTH_COLON_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit_index": digit_index,
                "p8_replay": replay_records,
                "corrections": corrections,
                "driver": driver,
                "claim_boundary": "This STOP concerns only the registered fixed-gauge p173 lift.",
            }
            receipt_path = output / "extension.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
            print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}))
            return 4
        require(completed.returncode == 0 and driver is not None, f"driver failed at digit {digit_index}")
        require(driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD173_EXPLICIT_TARGET_SOLVE", "driver status drift")
        require(driver.get("augmented_nullity") == 1 and driver.get("replay_mismatches") == 0, "driver integrity drift")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        numerator = q - coefficient @ digit
        divisibility_mismatches = int(np.count_nonzero(numerator % P))
        require(divisibility_mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        q = numerator // P
        maximum_q_bits = max(abs(int(value)).bit_length() for value in q)
        require(maximum_q_bits < 63, f"q exceeds signed 64-bit at digit {digit_index}")
        new_digits.append(digit)
        current_x = [value + current_place * int(item) for value, item in zip(current_x, digit)]
        current_place *= P
        corrections.append({
            "digit_index": digit_index,
            "cumulative_digits": digit_index + 1,
            "driver": driver,
            "digit_sha256": digest(digit_path),
            "correction_rhs_sha256": digest(rhs_path),
            "divisibility_mismatches": divisibility_mismatches,
            "digit_support": int(np.count_nonzero(digit)),
            "maximum_q_bit_length": maximum_q_bits,
            "seconds": time.perf_counter() - digit_started,
        })
        cumulative = digit_index + 1
        if cumulative in (24, 36, 48, 54):
            census_started = time.perf_counter()
            census, pairs = checkpoint_census(current_x, current_place)
            census["seconds"] = time.perf_counter() - census_started
            checkpoint_pairs[cumulative] = pairs
            checkpoint_data[str(cumulative)] = census

    require(current_place == P**54, "terminal modulus drift")
    x54_path = output / "X_mod_173_power_54.json"
    q54_path = output / "terminal_q54.i64le"
    x54_path.write_text(json.dumps([str(value) for value in current_x], separators=(",", ":")) + "\n", encoding="ascii")
    q54_path.write_bytes(q.astype("<i8").tobytes(order="C"))
    stability_data = {
        "p24_to_p36": stability(checkpoint_pairs[24], checkpoint_pairs[36]),
        "p36_to_p48": stability(checkpoint_pairs[36], checkpoint_pairs[48]),
        "p48_to_p54": stability(checkpoint_pairs[48], checkpoint_pairs[54]),
    }
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 7_200 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p173-fourth-colon-54digit-extension.v1",
        "status": "PASS_P173_FOURTH_COLON_54DIGIT_LIFT",
        "inputs": {
            "integral_sha256": digest(INTEGRAL),
            "modular_csr_sha256": digest(MODULAR),
            "p8_receipt_sha256": digest(P8_RECEIPT),
            "x8_sha256": digest(X8),
            "driver_sha256": digest(DRIVER),
        },
        "p8_independent_history_replay": replay_records,
        "corrections": corrections,
        "terminal_modulus": str(current_place),
        "reconstruction_checkpoints": checkpoint_data,
        "checkpoint_stability": stability_data,
        "outputs": {
            path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
            for path in (x54_path, q54_path)
        },
        "resources": resources,
        "declarations": {
            "fixed_gauge": True,
            "kernel_adjustment_forbidden": True,
            "exactly_forty_six_new_digits": True,
            "no_fifty_fifth_digit": True,
            "exact_target_replay_not_attempted": True,
        },
        "claim_boundary": (
            "A finite p54 PASS is a fixed-gauge lift, reconstruction census, and stability diagnostic. "
            "Even zero unresolved coordinates require separate exact and semantic replays; no colon equality, "
            "saturation, secant closure, nullcone containment, or HC4 theorem follows here."
        ),
    }
    receipt_path = output / "extension.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
