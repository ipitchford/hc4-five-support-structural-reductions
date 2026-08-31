#!/usr/bin/env python3
"""Extend the audited p181 lift from eight through twelve total digits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import subprocess
import time
from fractions import Fraction
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
MODULAR_CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
X8 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-8digit-lift-v2/X_mod_181_power_8.u64le"
LIFT_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-8digit-lift-independent-audit.json"
EQUAL_HEIGHT = CAMPAIGN / "artifacts/third-colon-p181-equal-height-reconstruction-v1/equal-height.json"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


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
    return [
        sum(values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1]))
        for row in range(ROWS)
    ]


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
    if (
        denominator <= 0
        or abs(numerator) > bound
        or denominator > bound
        or math.gcd(abs(numerator), denominator) != 1
        or (residue * denominator - numerator) % modulus
    ):
        return None
    return numerator, denominator


def snapshot(vector: list[int], modulus: int) -> tuple[list[tuple[int, int] | None], dict[str, object]]:
    candidates = [reconstruct(value, modulus) for value in vector]
    accepted = [item for item in candidates if item is not None]
    bound = math.isqrt((modulus - 1) // 2)
    return candidates, {
        "modulus": str(modulus),
        "bound": bound,
        "twice_bound_squared_less_than_modulus": 2 * bound * bound < modulus,
        "accepted": len(accepted),
        "rejected": COLUMNS - len(accepted),
        "maximum_absolute_numerator": max((abs(item[0]) for item in accepted), default=0),
        "maximum_denominator": max((item[1] for item in accepted), default=1),
    }


def exact_replay(
    offsets: list[int],
    indices: list[int],
    values: list[int],
    rhs: list[int],
    candidates: list[tuple[int, int] | None],
) -> tuple[list[Fraction], dict[str, object]]:
    require(all(item is not None for item in candidates), "complete vector required")
    vector = [Fraction(item[0], item[1]) for item in candidates if item is not None]
    mismatches = 0
    digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        mismatches += int(bool(residual))
        digest.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    require(mismatches == 0, "exact integral replay failed")
    return vector, {"mismatches": mismatches, "residual_stream_sha256": digest.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(LIFT_AUDIT.read_text(encoding="utf-8"))
    scout = json.loads(EQUAL_HEIGHT.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_REPLAY", "eight-digit audit PASS drift")
    require(scout.get("status") == "PASS_INCOMPLETE_EQUAL_HEIGHT_RECONSTRUCTION_SCOUT", "equal-height scout status drift")
    offsets, indices, values, rhs = read_integral()
    x_payload = X8.read_bytes()
    require(len(x_payload) == COLUMNS * 8, "X8 byte length drift")
    x = [item[0] for item in struct.iter_unpack("<Q", x_payload)]
    modulus = P**8
    product = matvec(offsets, indices, values, x)
    q = []
    starting_divisibility_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        if residual % modulus:
            starting_divisibility_mismatches += 1
        q.append(residual // modulus)
    require(starting_divisibility_mismatches == 0, "X8 exact divisibility replay failed")

    corrections = []
    snapshots: dict[int, list[int]] = {}
    for digit_index in range(8, 12):
        digit_started = time.perf_counter()
        correction_rhs = bytes(value % P for value in q)
        rhs_path = output / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = output / f"digit_{digit_index}.u8"
        stdout_path = output / f"digit_{digit_index}.stdout.txt"
        stderr_path = output / f"digit_{digit_index}.stderr.txt"
        rhs_path.write_bytes(correction_rhs)
        completed = subprocess.run(
            [str(DRIVER), "--csr", str(MODULAR_CSR), "--rhs", str(rhs_path), "--solution-output", str(digit_path)],
            cwd=CAMPAIGN,
            text=True,
            capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver is not None and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD181":
            receipt = {
                "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-12digit-extension.v1",
                "status": "STOP_P181_12DIGIT_EXTENSION_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit": digit_index,
                "corrections": corrections,
                "driver": driver,
            }
            receipt_path = output / "extension.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}))
            return 4
        require(completed.returncode == 0 and driver is not None, f"driver failed at digit {digit_index}")
        require(driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE", "driver status drift")
        require(driver.get("augmented_nullity") == 1 and driver.get("replay_mismatches") == 0, "driver integrity drift")
        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS, "digit length drift")
        product_digit = matvec(offsets, indices, values, digit)
        next_q = []
        divisibility_mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            if numerator % P:
                divisibility_mismatches += 1
            next_q.append(numerator // P)
        require(divisibility_mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        require(len(x) == len(digit), "digit coordinate length mismatch")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        corrections.append(
            {
                "digit_index": digit_index,
                "cumulative_digits": digit_index + 1,
                "modulus": str(modulus),
                "correction_rhs_sha256": file_hash(rhs_path),
                "digit_sha256": file_hash(digit_path),
                "driver": driver,
                "divisibility_mismatches": divisibility_mismatches,
                "maximum_q_bit_length": max(abs(value).bit_length() for value in q),
                "wall_seconds": time.perf_counter() - digit_started,
            }
        )
        if digit_index + 1 in (10, 12):
            snapshots[digit_index + 1] = list(x)

    require(modulus == P**12, "terminal modulus drift")
    terminal_product = matvec(offsets, indices, values, x)
    terminal_invariant_mismatches = sum(rhs[row] - terminal_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_invariant_mismatches == 0, "terminal integer invariant failed")
    x12_path = output / "X_mod_181_power_12.json"
    x12_path.write_text(json.dumps([str(value) for value in x], separators=(",", ":")) + "\n", encoding="utf-8")

    rr: dict[str, object] = {}
    candidates: dict[int, list[tuple[int, int] | None]] = {}
    for digits in (10, 12):
        rr_started = time.perf_counter()
        candidate_set, record = snapshot(snapshots[digits], P**digits)
        record["seconds"] = time.perf_counter() - rr_started
        labels = bytes(item is not None for item in candidate_set)
        labels_path = output / f"equal_height_labels_{digits}.u8"
        labels_path.write_bytes(labels)
        record["label_stream_sha256"] = file_hash(labels_path)
        rr[str(digits)] = record
        candidates[digits] = candidate_set

    held_out = {"eligible_at_digit_10": 0, "matches_through_digit_12": 0}
    for residue12, candidate in zip(snapshots[12], candidates[10]):
        if candidate is None:
            continue
        held_out["eligible_at_digit_10"] += 1
        if (residue12 * candidate[1] - candidate[0]) % (P**12) == 0:
            held_out["matches_through_digit_12"] += 1

    complete = all(item is not None for item in candidates[12])
    exact = None
    rational_output = None
    if complete:
        exact_started = time.perf_counter()
        vector, exact = exact_replay(offsets, indices, values, rhs, candidates[12])
        exact["seconds"] = time.perf_counter() - exact_started
        rational_path = output / "rational_solution.json"
        rational_path.write_text(
            json.dumps(
                [{"index": index, "numerator": value.numerator, "denominator": value.denominator} for index, value in enumerate(vector)],
                separators=(",", ":"),
            ) + "\n",
            encoding="utf-8",
        )
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}

    status = (
        "PASS_P181_12DIGIT_EXTENSION_AND_EXACT_RATIONAL_SYSTEM_REPLAY"
        if complete and exact is not None
        else "PASS_P181_AUGMENTED_NULLSPACE_12DIGIT_EXTENSION"
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-12digit-extension.v1",
        "status": status,
        "inputs": {
            "integral_system_sha256": file_hash(INTEGRAL),
            "X8_sha256": file_hash(X8),
            "eight_digit_audit_sha256": file_hash(LIFT_AUDIT),
            "equal_height_scout_sha256": file_hash(EQUAL_HEIGHT),
        },
        "starting_divisibility_mismatches": starting_divisibility_mismatches,
        "corrections": corrections,
        "terminal_modulus": str(modulus),
        "terminal_X": {"path": x12_path.name, "sha256": file_hash(x12_path), "bytes": x12_path.stat().st_size},
        "terminal_integer_invariant_mismatches": terminal_invariant_mismatches,
        "rr_snapshots": rr,
        "digit10_two_digit_holdout": held_out,
        "complete_digit12_reconstruction": complete,
        "exact_integral_system_replay": exact,
        "rational_solution": rational_output,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {
            "starts_from_independently_audited_X8": True,
            "cached_q8_not_read": True,
            "exactly_four_new_digits": True,
            "no_thirteenth_digit": True,
            "quarantined_dixon_data_not_read": True,
        },
        "claim_boundary": (
            "An incomplete 12-digit PASS is finite p-adic evidence only. Exact integral-system replay, if "
            "present, still requires independent symbolic replay; no colon, saturation, secant, nullcone, "
            "or HC4 theorem follows."
        ),
    }
    receipt_path = output / "extension.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
