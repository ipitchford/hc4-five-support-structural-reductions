#!/usr/bin/env python3
"""Test the frozen stable-denominator recovery rule at p173^54."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
SYSTEM = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
P8 = CAMPAIGN / "artifacts/fourth-colon-p173-augmented-nullspace-8digit-lift-v1"
P54 = CAMPAIGN / "artifacts/fourth-colon-p173-target-54digit-extension-v1"
INTEGRAL = SYSTEM / "A_Z_b_Z_fixed_gauge_p173.i64csr"
X8 = P8 / "X_mod_173_power_8.u64le"
X54 = P54 / "X_mod_173_power_54.json"
P54_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-fourth-colon-p173-54digit-extension-independent-audit.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


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


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI173", "integral magic drift")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)

    audit = json.loads(P54_AUDIT.read_text(encoding="ascii"))
    require(audit.get("status") == "PASS_INDEPENDENT_P173_FOURTH_COLON_54DIGIT_LIFT_REPLAY", "p54 audit status drift")
    require(audit["bound_hashes"]["x54"] == digest(X54), "audited p54 endpoint drift")
    modulus48 = P**48
    modulus54 = P**54
    x48 = [int(value) for value in struct.unpack(f"<{COLUMNS}Q", X8.read_bytes())]
    place = P**8
    for digit_index in range(8, 48):
        digit = list((P54 / f"digit_{digit_index:02d}.u8").read_bytes())
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        x48 = [left + place * right for left, right in zip(x48, digit, strict=True)]
        place *= P
    require(place == modulus48 and all(0 <= value < modulus48 for value in x48), "p48 reconstruction drift")
    x54 = [int(value) for value in json.loads(X54.read_text(encoding="ascii"))]
    require(len(x54) == COLUMNS, "p54 dimension drift")

    pairs48 = [reconstruct(value, modulus48) for value in x48]
    pairs54 = [reconstruct(value, modulus54) for value in x54]
    stable_indices = [
        index for index, (left, right) in enumerate(zip(pairs48, pairs54, strict=True))
        if left is not None and left[0] != 0 and left == right
    ]
    require(len(stable_indices) == 95, "stable nonzero count drift")
    denominator = 1
    for index in stable_indices:
        denominator = math.lcm(denominator, pairs54[index][1])
    require(math.gcd(denominator, P) == 1, "stable denominator is not a p-unit")

    numerators = []
    half = modulus54 // 2
    for residue in x54:
        value = denominator * residue % modulus54
        numerators.append(value - modulus54 if value > half else value)
    offsets, indices, values, rhs = read_integral()
    mismatch_count = 0
    maximum_absolute_residual = 0
    first_mismatches = []
    residual_digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            values[position] * numerators[indices[position]]
            for position in range(offsets[row], offsets[row + 1])
        )
        residual = total - denominator * rhs[row]
        if residual:
            mismatch_count += 1
            if len(first_mismatches) < 20:
                first_mismatches.append({"row": row, "residual": str(residual)})
        maximum_absolute_residual = max(maximum_absolute_residual, abs(residual))
        residual_digest.update(f"{residual}\n".encode("ascii"))

    passed = mismatch_count == 0
    vector_path = output / "primitive_common_denominator_vector.json"
    vector_path.write_text(json.dumps({
        "denominator": denominator,
        "integer_numerators": numerators,
    }, separators=(",", ":")) + "\n", encoding="ascii")
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < 300 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "resource gate failed")
    status = (
        "PASS_P173_FOURTH_COLON_STABLE_DENOMINATOR_EXACT_RATIONAL_RECOVERY"
        if passed else "REJECT_P173_FOURTH_COLON_STABLE_DENOMINATOR_RECOVERY"
    )
    receipt = {
        "schema": "hc4.fourth-colon-p173-stable-denominator-recovery.v1",
        "status": status,
        "inputs": {
            "integral_system_sha256": digest(INTEGRAL),
            "x8_sha256": digest(X8),
            "x54_sha256": digest(X54),
            "p54_independent_audit_sha256": digest(P54_AUDIT),
        },
        "stable_set": {
            "count": len(stable_indices),
            "index_stream_sha256": hashlib.sha256(json.dumps(stable_indices, separators=(",", ":")).encode("ascii")).hexdigest(),
            "denominator_lcm": str(denominator),
            "denominator_bit_length": denominator.bit_length(),
        },
        "candidate_vector": {
            "support_count": sum(value != 0 for value in numerators),
            "maximum_absolute_numerator": max(abs(value) for value in numerators),
            "maximum_numerator_bit_length": max(abs(value).bit_length() for value in numerators),
            "output": {"path": vector_path.name, "sha256": digest(vector_path), "bytes": vector_path.stat().st_size},
        },
        "exact_replay": {
            "row_comparisons": ROWS,
            "mismatch_count": mismatch_count,
            "maximum_absolute_residual": str(maximum_absolute_residual),
            "first_mismatches": first_mismatches,
            "residual_stream_sha256": residual_digest.hexdigest(),
        },
        "resources": resources,
        "declarations": {
            "no_denominator_subset_search": True,
            "no_denominator_factor_or_multiple_search": True,
            "no_alternate_centering": True,
            "no_new_p_adic_digit": True,
        },
        "claim_boundary": (
            "A PASS proves an exact rational solution of the frozen target system and still requires an "
            "independent source-level polynomial audit. A REJECT concerns only this frozen denominator rule; "
            "neither outcome proves colon equality, saturation, nullcone containment, or HC4."
        ),
    }
    receipt_path = output / "recovery.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0 if passed else 4


if __name__ == "__main__":
    raise SystemExit(main())
