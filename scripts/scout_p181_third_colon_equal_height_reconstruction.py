#!/usr/bin/env -S sage -python
"""Equal-height rational reconstruction of the independently audited p181 lift."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from fractions import Fraction
from pathlib import Path

from sage.all import ZZ


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-8digit-lift-v2"
DIGIT_ZERO = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
LIFT_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-8digit-lift-independent-audit.json"


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


def own_reconstruction(residue: int, modulus: int) -> tuple[int, int] | None:
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
    if (
        denominator <= 0
        or abs(numerator) > bound
        or denominator > bound
        or math.gcd(abs(numerator), denominator) != 1
        or (residue * denominator - numerator) % modulus
    ):
        return None
    return numerator, denominator


def sage_reconstruction(residue: int, modulus: int) -> tuple[int, int] | None:
    try:
        value = ZZ(residue).rational_reconstruction(ZZ(modulus))
    except ArithmeticError:
        return None
    return int(value.numerator()), int(value.denominator())


def exact_replay(
    offsets: list[int],
    indices: list[int],
    values: list[int],
    rhs: list[int],
    candidates: list[tuple[int, int] | None],
) -> tuple[list[Fraction], dict[str, object]]:
    require(all(item is not None for item in candidates), "exact replay requires a complete vector")
    vector = [Fraction(item[0], item[1]) for item in candidates if item is not None]
    mismatches = 0
    residual_hash = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        mismatches += int(bool(residual))
        residual_hash.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    require(mismatches == 0, "exact integral-system replay failed")
    return vector, {"mismatches": mismatches, "residual_stream_sha256": residual_hash.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(LIFT_AUDIT.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_REPLAY", "lift audit PASS drift")

    cumulative = list(DIGIT_ZERO.read_bytes())
    modulus = P
    snapshots: dict[int, list[int]] = {}
    for digit_index in range(1, 8):
        digit = list((ARTIFACT / f"digit_{digit_index}.u8").read_bytes())
        require(len(cumulative) == len(digit) == COLUMNS, "digit length drift")
        cumulative = [left + modulus * right for left, right in zip(cumulative, digit)]
        modulus *= P
        if digit_index + 1 in (4, 6, 8):
            snapshots[digit_index + 1] = list(cumulative)

    records: dict[str, object] = {}
    candidate_sets: dict[int, list[tuple[int, int] | None]] = {}
    for digits in (4, 6, 8):
        modulus = P**digits
        bound = math.isqrt((modulus - 1) // 2)
        candidates: list[tuple[int, int] | None] = []
        labels = bytearray()
        maximum_numerator = 0
        maximum_denominator = 0
        for residue in snapshots[digits]:
            own = own_reconstruction(residue, modulus)
            sage = sage_reconstruction(residue, modulus)
            require(own == sage, f"own/Sage reconstruction mismatch at {digits} digits")
            candidates.append(own)
            labels.append(1 if own is not None else 0)
            if own is not None:
                maximum_numerator = max(maximum_numerator, abs(own[0]))
                maximum_denominator = max(maximum_denominator, own[1])
        candidate_sets[digits] = candidates
        accepted = sum(item is not None for item in candidates)
        labels_path = output / f"equal_height_labels_{digits}.u8"
        labels_path.write_bytes(labels)
        records[str(digits)] = {
            "modulus": str(modulus),
            "bound": bound,
            "twice_bound_squared_less_than_modulus": 2 * bound * bound < modulus,
            "accepted": accepted,
            "rejected": COLUMNS - accepted,
            "maximum_absolute_numerator": maximum_numerator,
            "maximum_denominator": maximum_denominator,
            "label_stream_sha256": file_hash(labels_path),
        }

    held_out = {"eligible_at_digit_6": 0, "matches_through_digit_8": 0}
    modulus8 = P**8
    for residue8, candidate in zip(snapshots[8], candidate_sets[6]):
        if candidate is None:
            continue
        held_out["eligible_at_digit_6"] += 1
        if (residue8 * candidate[1] - candidate[0]) % modulus8 == 0:
            held_out["matches_through_digit_8"] += 1

    complete = all(item is not None for item in candidate_sets[8])
    exact = None
    rational_output = None
    if complete:
        offsets, indices, values, rhs = read_integral()
        vector, exact = exact_replay(offsets, indices, values, rhs, candidate_sets[8])
        rational_path = output / "rational_solution.json"
        rational_path.write_text(
            json.dumps(
                [
                    {"index": index, "numerator": value.numerator, "denominator": value.denominator}
                    for index, value in enumerate(vector)
                ],
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}

    status = (
        "PASS_COMPLETE_EQUAL_HEIGHT_RECONSTRUCTION_AND_EXACT_INTEGRAL_REPLAY"
        if complete and exact is not None
        else "PASS_INCOMPLETE_EQUAL_HEIGHT_RECONSTRUCTION_SCOUT"
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-equal-height-reconstruction-scout.v1",
        "status": status,
        "inputs": {
            "lift_audit_sha256": file_hash(LIFT_AUDIT),
            "integral_system_sha256": file_hash(INTEGRAL),
            "terminal_X_sha256": file_hash(ARTIFACT / "X_mod_181_power_8.u64le"),
        },
        "snapshots": records,
        "digit6_two_digit_holdout": held_out,
        "complete_digit8_reconstruction": complete,
        "exact_integral_system_replay": exact,
        "rational_solution": rational_output,
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "own_algorithm_cross_checked_with_sage_on_every_coordinate": True,
            "no_digit_nine": True,
            "rational_vector_emitted_only_after_complete_exact_replay": True,
        },
        "claim_boundary": (
            "An incomplete PASS is bounded height evidence only. A complete exact integral replay, if present, "
            "still requires independent symbolic polynomial replay before a QQ identity claim; no colon, "
            "saturation, secant, nullcone, or HC4 theorem follows."
        ),
    }
    receipt_path = output / "equal-height.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
