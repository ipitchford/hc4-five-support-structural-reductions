#!/usr/bin/env python3
"""Independent exact replay of the p181 extension from 8 to 12 digits."""

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
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-12digit-extension-v1"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-12digit-extension.json"
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
X8 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-8digit-lift-v2/X_mod_181_power_8.u64le"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-12digit-extension-independent-audit.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, NONZEROS), "integral dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * nonzeros])]
    cursor += 8 * nonzeros
    rhs = [item[0] for item in struct.iter_unpack("<q", payload[cursor:cursor + 8 * rows])]
    cursor += 8 * rows
    require(cursor == len(payload), "integral trailing bytes")
    return offsets, indices, values, rhs


def matvec(offsets: list[int], indices: list[int], values: list[int], vector: list[int]) -> list[int]:
    return [sum(values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])) for row in range(ROWS)]


def reconstruct(residue: int, modulus: int) -> tuple[int, int] | None:
    residue %= modulus
    if residue == 0:
        return (0, 1)
    bound = math.isqrt((modulus - 1) // 2)
    old_r, r = modulus, residue
    old_t, t = 0, 1
    while abs(r) > bound:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_t, t = t, old_t - quotient * t
    numerator, denominator = r, t
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if denominator <= 0 or abs(numerator) > bound or denominator > bound or math.gcd(abs(numerator), denominator) != 1 or (residue * denominator - numerator) % modulus:
        return None
    return numerator, denominator


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "12-digit audit already exists")
    producer = json.loads((ARTIFACT / "extension.json").read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_12DIGIT_EXTENSION", "producer PASS drift")
    require(terminal.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_12DIGIT_EXTENSION", "terminal PASS drift")
    offsets, indices, values, rhs = read_integral()
    x = [item[0] for item in struct.iter_unpack("<Q", X8.read_bytes())]
    require(len(x) == COLUMNS, "X8 dimension drift")
    modulus = P**8
    product = matvec(offsets, indices, values, x)
    q = []
    starting_divisibility_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_divisibility_mismatches += int(residual % modulus != 0)
        q.append(residual // modulus)
    require(starting_divisibility_mismatches == 0, "X8 divisibility replay failed")
    digit_audits = []
    snapshots: dict[int, list[int]] = {}
    for digit_index in range(8, 12):
        expected_rhs = bytes(value % P for value in q)
        rhs_path = ARTIFACT / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = ARTIFACT / f"digit_{digit_index}.u8"
        require(rhs_path.read_bytes() == expected_rhs, f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS, "digit dimension drift")
        product_digit = matvec(offsets, indices, values, digit)
        next_q = []
        mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            mismatches += int(numerator % P != 0)
            next_q.append(numerator // P)
        require(mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        digit_audits.append({"digit_index": digit_index, "rhs_sha256": file_hash(rhs_path), "digit_sha256": file_hash(digit_path), "divisibility_mismatches": mismatches})
        if digit_index + 1 in (10, 12):
            snapshots[digit_index + 1] = list(x)
    require(modulus == P**12, "terminal modulus drift")
    expected_x12 = [int(value) for value in json.loads((ARTIFACT / "X_mod_181_power_12.json").read_text(encoding="utf-8"))]
    require(x == expected_x12, "X12 serialization mismatch")
    final_product = matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - final_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal exact invariant failed")
    rr_audits: dict[str, object] = {}
    for digits in (10, 12):
        labels = bytes(reconstruct(value, P**digits) is not None for value in snapshots[digits])
        labels_path = ARTIFACT / f"equal_height_labels_{digits}.u8"
        require(labels == labels_path.read_bytes(), f"equal-height labels drift at {digits}")
        accepted = sum(labels)
        require(accepted == producer["rr_snapshots"][str(digits)]["accepted"], f"accepted count drift at {digits}")
        rr_audits[str(digits)] = {"accepted": accepted, "rejected": COLUMNS - accepted, "label_stream_sha256": hashlib.sha256(labels).hexdigest()}
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-12digit-extension-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_12DIGIT_EXTENSION_REPLAY",
        "bound_hashes": {"producer": file_hash(ARTIFACT / "extension.json"), "terminal": file_hash(TERMINAL), "integral": file_hash(INTEGRAL), "X8": file_hash(X8), "X12": file_hash(ARTIFACT / "X_mod_181_power_12.json")},
        "checks": {"starting_divisibility_mismatches": starting_divisibility_mismatches, "correction_count": len(digit_audits), "terminal_modulus": str(modulus), "terminal_integer_invariant_mismatches": terminal_mismatches},
        "digit_audits": digit_audits,
        "rr_audits": rr_audits,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"producer_not_imported_or_executed": True, "linbox_not_called": True, "cached_q8_not_read": True, "no_thirteenth_digit": True},
        "claim_boundary": "This PASS independently certifies the finite extension through 181^12 and its reconstruction labels. It is not a QQ identity or any colon, saturation, secant, nullcone, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
