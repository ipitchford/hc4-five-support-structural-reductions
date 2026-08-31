#!/usr/bin/env python3
"""Independent exact replay of the fixed-main target through p^24."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
SOURCE = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1"
P18_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-fixed-block-denominator-18digit-test-v1"
P24_SOURCE = CAMPAIGN / "artifacts/third-colon-p181-target-24digit-extension-v1"
INTEGRAL = SOURCE / "A_Z_b_Z_fixed_gauge.i64csr"
X18 = P18_SOURCE / "X_mod_181_power_18.json"
P18_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-fixed-block-denominator-18digit-test-independent-audit.json"
PRODUCER = P24_SOURCE / "extension.json"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-24digit-extension-terminal.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-24digit-extension-independent-audit.json"


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
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor)); cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]; cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]; cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]; cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def matvec(offsets, indices, values, vector):
    return [sum(values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])) for row in range(ROWS)]


def reconstruct(residue: int, modulus: int):
    residue %= modulus
    if residue == 0:
        return (0, 1)
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
    if denominator <= 0 or abs(numerator) > bound or denominator > bound or math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus:
        return None
    return numerator, denominator


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "p24 independent audit exists")
    p18_audit = json.loads(P18_AUDIT.read_text(encoding="utf-8"))
    producer = json.loads(PRODUCER.read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(p18_audit.get("status") == "PASS_INDEPENDENT_P181_18DIGIT_LIFT_AND_FIXED_DENOMINATOR_FALSIFICATION_REPLAY", "p18 audit status drift")
    require(producer.get("status") == terminal.get("status") == "PASS_P181_TARGET_24DIGIT_LIFT", "p24 status drift")
    offsets, indices, values, rhs = read_integral()
    require(p18_audit["bound_hashes"]["integral"] == digest(INTEGRAL) and p18_audit["bound_hashes"]["X18"] == digest(X18), "p18 input drift")
    x = [int(value) for value in json.loads(X18.read_text(encoding="utf-8"))]
    require(len(x) == COLUMNS, "X18 dimension drift")
    modulus = P**18
    product = matvec(offsets, indices, values, x)
    q = []
    starting_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_mismatches += residual % modulus != 0
        q.append(residual // modulus)
    require(starting_mismatches == 0, "X18 divisibility replay failed")
    digit_audits = []
    for digit_index in range(18, 24):
        rhs_path = P24_SOURCE / f"correction_rhs_digit_{digit_index:02d}.u8"
        digit_path = P24_SOURCE / f"digit_{digit_index:02d}.u8"
        require(rhs_path.read_bytes() == bytes(value % P for value in q), f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        digit_product = matvec(offsets, indices, values, digit)
        next_q = []
        mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - digit_product[row]
            mismatches += numerator % P != 0
            next_q.append(numerator // P)
        require(mismatches == 0, f"digit recurrence mismatch at {digit_index}")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        digit_audits.append({"digit_index": digit_index, "rhs_sha256": digest(rhs_path), "digit_sha256": digest(digit_path), "divisibility_mismatches": mismatches})
    require(modulus == P**24, "terminal modulus drift")
    saved_x = [int(value) for value in json.loads((P24_SOURCE / "X_mod_181_power_24.json").read_text(encoding="utf-8"))]
    saved_q = [item[0] for item in struct.iter_unpack("<q", (P24_SOURCE / "terminal_q24.i64le").read_bytes())]
    require(x == saved_x and q == saved_q, "terminal serialization mismatch")
    final_product = matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - final_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal integer invariant failed")

    unresolved = 0
    resolved_nonzero = 0
    resolved_zero = 0
    maximum_absolute_numerator = 0
    maximum_denominator = 0
    for value in x:
        pair = reconstruct(value, modulus)
        if pair is None:
            unresolved += 1
        elif pair[0] == 0:
            resolved_zero += 1
        else:
            resolved_nonzero += 1
            maximum_absolute_numerator = max(maximum_absolute_numerator, abs(pair[0]))
            maximum_denominator = max(maximum_denominator, pair[1])
    census = {"equal_height_bound": math.isqrt((modulus - 1) // 2), "coordinate_count": COLUMNS, "unresolved_count": unresolved, "resolved_nonzero_count": resolved_nonzero, "resolved_zero_count": resolved_zero, "maximum_absolute_numerator": maximum_absolute_numerator, "maximum_denominator": maximum_denominator}
    require(census == producer["reconstruction_census"], "p24 census mismatch")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "audit resource gate failed")
    receipt = {
        "schema": "hc4.third-colon-p181-target-24digit-extension-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_TARGET_24DIGIT_LIFT_REPLAY",
        "bound_hashes": {"integral": digest(INTEGRAL), "x18": digest(X18), "p18_audit": digest(P18_AUDIT), "producer": digest(PRODUCER), "terminal": digest(TERMINAL), "x24": digest(P24_SOURCE / "X_mod_181_power_24.json"), "q24": digest(P24_SOURCE / "terminal_q24.i64le")},
        "lift_checks": {"starting_divisibility_mismatches": starting_mismatches, "digit_count": len(digit_audits), "terminal_modulus": str(modulus), "terminal_integer_invariant_mismatches": terminal_mismatches},
        "digit_audits": digit_audits,
        "reconstruction_census": census,
        "resources": resources,
        "declarations": {"producer_not_imported_or_executed": True, "driver_not_called": True, "rational_reconstruction_reimplemented": True, "x24_reconstructed_from_x18_and_raw_digits": True, "no_new_digit": True, "target_membership_not_claimed": True},
        "claim_boundary": "This PASS independently certifies the finite fixed-main p24 lift and height census only. It is not rational target membership or any colon, saturation, secant, nullcone, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
