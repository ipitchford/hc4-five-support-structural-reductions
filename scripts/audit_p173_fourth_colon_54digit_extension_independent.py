#!/usr/bin/env -S sage -python
"""Independently replay the p173 fourth-colon lift through p^54."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import struct
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
P8 = CAMPAIGN / "artifacts/fourth-colon-p173-augmented-nullspace-8digit-lift-v1"
P54 = CAMPAIGN / "artifacts/fourth-colon-p173-target-54digit-extension-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
DIGIT_ZERO = SYSTEM / "solution_mod173.u8"
P8_RECEIPT = P8 / "lift.json"
P54_PRODUCER = P54 / "extension.json"
X8 = P8 / "X_mod_173_power_8.u64le"
X54 = P54 / "X_mod_173_power_54.json"
Q54 = P54 / "terminal_q54.i64le"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-54digit-extension-independent-audit.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_system() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, csr_matrix]:
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
    coefficient = csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)
    return offsets, indices, values, rhs, coefficient


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
        "old_resolved_zero_count": 0,
        "old_resolved_zero_stable": 0,
        "old_resolved_zero_changed": 0,
        "old_resolved_zero_became_unresolved": 0,
        "old_resolved_nonzero_count": 0,
        "old_resolved_nonzero_stable": 0,
        "old_resolved_nonzero_changed": 0,
        "old_resolved_nonzero_became_unresolved": 0,
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
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent p54 audit output already exists")
    p8_receipt = json.loads(P8_RECEIPT.read_text(encoding="ascii"))
    producer = json.loads(P54_PRODUCER.read_text(encoding="ascii"))
    require(p8_receipt.get("status") == "PASS_P173_FOURTH_COLON_AUGMENTED_NULLSPACE_8DIGIT_LIFT", "p8 status drift")
    require(producer.get("status") == "PASS_P173_FOURTH_COLON_54DIGIT_LIFT", "p54 status drift")
    offsets, indices, values, rhs, coefficient = read_system()

    digit_zero = np.frombuffer(DIGIT_ZERO.read_bytes(), dtype=np.uint8).astype(np.int64)
    require(len(digit_zero) == COLUMNS, "digit-zero dimension drift")
    numerator = rhs - coefficient @ digit_zero
    require(int(np.count_nonzero(numerator % P)) == 0, "digit-zero divisibility mismatch")
    q = numerator // P
    x = [int(value) for value in digit_zero]
    modulus = P
    digit_audits = []
    checkpoint_pairs: dict[int, list[tuple[int, int] | None]] = {}
    checkpoint_censuses: dict[str, dict[str, int]] = {}

    for digit_index in range(1, 54):
        source = P8 if digit_index < 8 else P54
        suffix = str(digit_index) if digit_index < 8 else f"{digit_index:02d}"
        rhs_path = source / f"correction_rhs_digit_{suffix}.u8"
        digit_path = source / f"digit_{suffix}.u8"
        require(rhs_path.read_bytes() == bytes(int(value) % P for value in q), f"correction RHS mismatch at digit {digit_index}")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        numerator = q - coefficient @ digit
        mismatches = int(np.count_nonzero(numerator % P))
        require(mismatches == 0, f"digit recurrence mismatch at {digit_index}")
        q = numerator // P
        x = [left + modulus * int(right) for left, right in zip(x, digit, strict=True)]
        modulus *= P
        digit_audits.append({
            "digit_index": digit_index,
            "rhs_sha256": digest(rhs_path),
            "digit_sha256": digest(digit_path),
            "divisibility_mismatches": mismatches,
            "maximum_q_bit_length": max(abs(int(value)).bit_length() for value in q),
        })
        cumulative = digit_index + 1
        if cumulative == 8:
            saved_x8 = [int(value) for value in np.frombuffer(X8.read_bytes(), dtype="<u8")]
            require(x == saved_x8, "p8 endpoint reconstruction mismatch")
        if cumulative in (24, 36, 48, 54):
            current_census, pairs = census(x, modulus)
            checkpoint_censuses[str(cumulative)] = current_census
            checkpoint_pairs[cumulative] = pairs

    require(modulus == P**54, "terminal modulus drift")
    saved_x54 = [int(value) for value in json.loads(X54.read_text(encoding="ascii"))]
    saved_q54 = [item[0] for item in struct.iter_unpack("<q", Q54.read_bytes())]
    require(x == saved_x54 and [int(value) for value in q] == saved_q54, "terminal serialization mismatch")

    terminal_mismatches = 0
    for row in range(ROWS):
        total = sum(
            int(values[position]) * x[int(indices[position])]
            for position in range(int(offsets[row]), int(offsets[row + 1]))
        )
        terminal_mismatches += int(rhs[row]) - total != modulus * int(q[row])
    require(terminal_mismatches == 0, "terminal integer invariant failed")

    producer_censuses = {
        key: {name: value for name, value in record.items() if name != "seconds"}
        for key, record in producer["reconstruction_checkpoints"].items()
    }
    require(checkpoint_censuses == producer_censuses, "checkpoint census mismatch")
    stability_data = {
        "p24_to_p36": stability(checkpoint_pairs[24], checkpoint_pairs[36]),
        "p36_to_p48": stability(checkpoint_pairs[36], checkpoint_pairs[48]),
        "p48_to_p54": stability(checkpoint_pairs[48], checkpoint_pairs[54]),
    }
    require(stability_data == producer["checkpoint_stability"], "checkpoint stability mismatch")

    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.fourth-colon-p173-54digit-extension-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P173_FOURTH_COLON_54DIGIT_LIFT_REPLAY",
        "bound_hashes": {
            "integral": digest(INTEGRAL),
            "p8_receipt": digest(P8_RECEIPT),
            "p54_producer": digest(P54_PRODUCER),
            "x8": digest(X8),
            "x54": digest(X54),
            "q54": digest(Q54),
        },
        "lift_checks": {
            "digit_count_after_digit_zero": len(digit_audits),
            "terminal_modulus": str(modulus),
            "terminal_integer_invariant_mismatches": terminal_mismatches,
        },
        "digit_audits": digit_audits,
        "reconstruction_checkpoints": checkpoint_censuses,
        "checkpoint_stability": stability_data,
        "resources": resources,
        "declarations": {
            "producer_not_imported_or_executed": True,
            "driver_not_called": True,
            "rational_reconstruction_reimplemented": True,
            "x54_reconstructed_from_raw_digits": True,
            "no_new_digit": True,
        },
        "claim_boundary": (
            "This PASS independently certifies the finite fixed-gauge p54 lift, checkpoint censuses, and "
            "stability tables only. It is not rational target membership or any colon, saturation, secant, "
            "nullcone, or HC4 theorem."
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
