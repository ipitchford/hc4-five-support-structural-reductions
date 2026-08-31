#!/usr/bin/env -S sage -python
"""Independently replay the p173 fourth-colon lift from p^54 through p^96."""

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
P54 = CAMPAIGN / "artifacts/fourth-colon-p173-target-54digit-extension-v1"
P96 = CAMPAIGN / "artifacts/fourth-colon-p173-target-96digit-extension-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
X54 = P54 / "X_mod_173_power_54.json"
Q54 = P54 / "terminal_q54.i64le"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-54digit-extension-independent-audit.json"
PRODUCER = P96 / "extension.json"
X96 = P96 / "X_mod_173_power_96.json"
Q96 = P96 / "terminal_q96.i64le"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-96digit-extension-independent-audit.json"


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
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy(); cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy(); cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype="<i8", count=nonzeros, offset=cursor).copy(); cursor += 8 * nonzeros
    rhs = np.frombuffer(payload, dtype="<i8", count=rows, offset=cursor).copy(); cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs, csr_matrix((values, indices, offsets), shape=(ROWS, COLUMNS), dtype=np.int64)


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
    if denominator < 0: numerator, denominator = -numerator, -denominator
    if denominator <= 0 or abs(numerator) > bound or denominator > bound: return None
    if math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus: return None
    return numerator, denominator


def census(vector: list[int], modulus: int) -> tuple[dict[str, int], list[tuple[int, int] | None]]:
    result = {"coordinate_count": COLUMNS, "resolved_zero_count": 0, "resolved_nonzero_count": 0, "unresolved_count": 0, "maximum_absolute_numerator": 0, "maximum_denominator": 0, "equal_height_bound": math.isqrt((modulus - 1) // 2)}
    pairs = []
    for value in vector:
        pair = reconstruct(value, modulus); pairs.append(pair)
        if pair is None: result["unresolved_count"] += 1
        elif pair[0] == 0: result["resolved_zero_count"] += 1
        else:
            result["resolved_nonzero_count"] += 1
            result["maximum_absolute_numerator"] = max(result["maximum_absolute_numerator"], abs(pair[0]))
            result["maximum_denominator"] = max(result["maximum_denominator"], pair[1])
    return result, pairs


def stability(old: list[tuple[int, int] | None], new: list[tuple[int, int] | None]) -> dict[str, int]:
    result = {"old_resolved_zero_count": 0, "old_resolved_zero_stable": 0, "old_resolved_zero_changed": 0, "old_resolved_zero_became_unresolved": 0, "old_resolved_nonzero_count": 0, "old_resolved_nonzero_stable": 0, "old_resolved_nonzero_changed": 0, "old_resolved_nonzero_became_unresolved": 0}
    for previous, current in zip(old, new, strict=True):
        if previous is None: continue
        kind = "zero" if previous[0] == 0 else "nonzero"; result[f"old_resolved_{kind}_count"] += 1
        if current is None: result[f"old_resolved_{kind}_became_unresolved"] += 1
        elif current == previous: result[f"old_resolved_{kind}_stable"] += 1
        else: result[f"old_resolved_{kind}_changed"] += 1
    return result


def main() -> int:
    started = time.perf_counter(); require(not OUTPUT.exists(), "p96 audit output already exists")
    prior = json.loads(P54_AUDIT.read_text(encoding="ascii")); producer = json.loads(PRODUCER.read_text(encoding="ascii"))
    require(prior.get("status") == "PASS_INDEPENDENT_P173_FOURTH_COLON_54DIGIT_LIFT_REPLAY", "p54 audit drift")
    require(producer.get("status") == "PASS_P173_FOURTH_COLON_96DIGIT_LIFT", "p96 producer status drift")
    offsets, indices, values, rhs, coefficient = read_system()
    x = [int(value) for value in json.loads(X54.read_text(encoding="ascii"))]
    q = np.frombuffer(Q54.read_bytes(), dtype="<i8").copy(); modulus = P**54
    checkpoints = {}; pairs_by_digit = {}; digit_audits = []
    snapshot, pairs = census(x, modulus); checkpoints["54"] = snapshot; pairs_by_digit[54] = pairs
    for digit_index in range(54, 96):
        rhs_path = P96 / f"correction_rhs_digit_{digit_index:02d}.u8"; digit_path = P96 / f"digit_{digit_index:02d}.u8"
        require(rhs_path.read_bytes() == bytes(int(value) % P for value in q), f"RHS mismatch at {digit_index}")
        digit = np.frombuffer(digit_path.read_bytes(), dtype=np.uint8).astype(np.int64)
        numerator = q - coefficient @ digit; mismatches = int(np.count_nonzero(numerator % P))
        require(len(digit) == COLUMNS and mismatches == 0, f"recurrence mismatch at {digit_index}")
        q = numerator // P; x = [left + modulus * int(right) for left, right in zip(x, digit, strict=True)]; modulus *= P
        digit_audits.append({"digit_index": digit_index, "rhs_sha256": digest(rhs_path), "digit_sha256": digest(digit_path), "divisibility_mismatches": mismatches})
        cumulative = digit_index + 1
        if cumulative in (72, 84, 96):
            snapshot, pairs = census(x, modulus); checkpoints[str(cumulative)] = snapshot; pairs_by_digit[cumulative] = pairs
    require(modulus == P**96, "terminal modulus drift")
    saved_x = [int(value) for value in json.loads(X96.read_text(encoding="ascii"))]
    saved_q = [item[0] for item in struct.iter_unpack("<q", Q96.read_bytes())]
    require(x == saved_x and [int(value) for value in q] == saved_q, "terminal serialization mismatch")
    terminal_mismatches = 0
    for row in range(ROWS):
        total = sum(int(values[position]) * x[int(indices[position])] for position in range(int(offsets[row]), int(offsets[row + 1])))
        terminal_mismatches += int(rhs[row]) - total != modulus * int(q[row])
    require(terminal_mismatches == 0, "terminal integer invariant mismatch")
    require(checkpoints == producer["reconstruction_checkpoints"], "census mismatch")
    stability_data = {"p54_to_p72": stability(pairs_by_digit[54], pairs_by_digit[72]), "p72_to_p84": stability(pairs_by_digit[72], pairs_by_digit[84]), "p84_to_p96": stability(pairs_by_digit[84], pairs_by_digit[96])}
    require(stability_data == producer["checkpoint_stability"], "stability mismatch")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 600 and resources["maximum_rss_native"] < 2_000_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    receipt = {"schema": "hc4.fourth-colon-p173-96digit-independent-audit.v1", "status": "PASS_INDEPENDENT_P173_FOURTH_COLON_96DIGIT_LIFT_REPLAY", "bound_hashes": {"integral": digest(INTEGRAL), "x54": digest(X54), "q54": digest(Q54), "p54_audit": digest(P54_AUDIT), "producer": digest(PRODUCER), "x96": digest(X96), "q96": digest(Q96)}, "lift_checks": {"digit_count": len(digit_audits), "terminal_modulus": str(modulus), "terminal_integer_invariant_mismatches": terminal_mismatches}, "digit_audits": digit_audits, "reconstruction_checkpoints": checkpoints, "checkpoint_stability": stability_data, "resources": resources, "declarations": {"producer_not_imported_or_executed": True, "driver_not_called": True, "rational_reconstruction_reimplemented": True, "no_new_digit": True}, "claim_boundary": "This PASS independently certifies the finite p96 lift and diagnostics only; it is not rational membership, a polynomial identity, colon equality, saturation, nullcone containment, or HC4."}
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)})); return 0


if __name__ == "__main__": raise SystemExit(main())
