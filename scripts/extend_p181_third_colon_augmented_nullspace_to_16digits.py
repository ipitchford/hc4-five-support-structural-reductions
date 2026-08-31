#!/usr/bin/env python3
"""Extend the independently audited p181 solution from 12 to 16 digits."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

from extend_p181_third_colon_augmented_nullspace_to_12digits import (
    CAMPAIGN,
    COLUMNS,
    DRIVER,
    INTEGRAL,
    MODULAR_CSR,
    P,
    ROWS,
    exact_replay,
    file_hash,
    matvec,
    read_integral,
    require,
    snapshot,
)


X12 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-12digit-extension-v1/X_mod_181_power_12.json"
AUDIT12 = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-12digit-extension-independent-audit.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(AUDIT12.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_12DIGIT_EXTENSION_REPLAY", "12-digit audit PASS drift")
    offsets, indices, values, rhs = read_integral()
    x = [int(value) for value in json.loads(X12.read_text(encoding="utf-8"))]
    require(len(x) == COLUMNS, "X12 length drift")
    modulus = P**12
    product = matvec(offsets, indices, values, x)
    q = []
    starting_divisibility_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_divisibility_mismatches += int(residual % modulus != 0)
        q.append(residual // modulus)
    require(starting_divisibility_mismatches == 0, "X12 exact divisibility replay failed")

    corrections = []
    snapshots: dict[int, list[int]] = {}
    for digit_index in range(12, 16):
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
            receipt = {"schema": "hc4.decimic-j2-secant-r10-p181-16digit-extension.v1", "status": "STOP_P181_16DIGIT_EXTENSION_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit": digit_index, "corrections": corrections, "driver": driver}
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
        mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            mismatches += int(numerator % P != 0)
            next_q.append(numerator // P)
        require(mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
        q = next_q
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "modulus": str(modulus), "correction_rhs_sha256": file_hash(rhs_path), "digit_sha256": file_hash(digit_path), "driver": driver, "divisibility_mismatches": mismatches, "maximum_q_bit_length": max(abs(value).bit_length() for value in q), "wall_seconds": time.perf_counter() - digit_started})
        if digit_index + 1 in (14, 16):
            snapshots[digit_index + 1] = list(x)

    require(modulus == P**16, "terminal modulus drift")
    terminal_product = matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - terminal_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal integer invariant failed")
    x16_path = output / "X_mod_181_power_16.json"
    x16_path.write_text(json.dumps([str(value) for value in x], separators=(",", ":")) + "\n", encoding="utf-8")

    rr: dict[str, object] = {}
    candidates: dict[int, list[tuple[int, int] | None]] = {}
    for digits in (14, 16):
        rr_started = time.perf_counter()
        candidate_set, record = snapshot(snapshots[digits], P**digits)
        record["seconds"] = time.perf_counter() - rr_started
        labels = bytes(item is not None for item in candidate_set)
        labels_path = output / f"equal_height_labels_{digits}.u8"
        labels_path.write_bytes(labels)
        record["label_stream_sha256"] = file_hash(labels_path)
        rr[str(digits)] = record
        candidates[digits] = candidate_set
    held_out = {"eligible_at_digit_14": 0, "matches_through_digit_16": 0}
    for residue16, candidate in zip(snapshots[16], candidates[14]):
        if candidate is None:
            continue
        held_out["eligible_at_digit_14"] += 1
        if (residue16 * candidate[1] - candidate[0]) % (P**16) == 0:
            held_out["matches_through_digit_16"] += 1

    complete = all(item is not None for item in candidates[16])
    exact = None
    rational_output = None
    if complete:
        exact_started = time.perf_counter()
        vector, exact = exact_replay(offsets, indices, values, rhs, candidates[16])
        exact["seconds"] = time.perf_counter() - exact_started
        rational_path = output / "rational_solution.json"
        rational_path.write_text(json.dumps([{"index": index, "numerator": value.numerator, "denominator": value.denominator} for index, value in enumerate(vector)], separators=(",", ":")) + "\n", encoding="utf-8")
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}
    status = "PASS_P181_16DIGIT_EXTENSION_AND_EXACT_RATIONAL_SYSTEM_REPLAY" if complete and exact is not None else "PASS_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION"
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-16digit-extension.v1",
        "status": status,
        "inputs": {"integral_system_sha256": file_hash(INTEGRAL), "X12_sha256": file_hash(X12), "audit12_sha256": file_hash(AUDIT12)},
        "starting_divisibility_mismatches": starting_divisibility_mismatches,
        "corrections": corrections,
        "terminal_modulus": str(modulus),
        "terminal_X": {"path": x16_path.name, "sha256": file_hash(x16_path), "bytes": x16_path.stat().st_size},
        "terminal_integer_invariant_mismatches": terminal_mismatches,
        "rr_snapshots": rr,
        "digit14_two_digit_holdout": held_out,
        "complete_digit16_reconstruction": complete,
        "exact_integral_system_replay": exact,
        "rational_solution": rational_output,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"starts_from_independently_audited_X12": True, "cached_q12_not_read": True, "exactly_four_new_digits": True, "no_seventeenth_digit": True},
        "claim_boundary": "An incomplete 16-digit PASS is finite p-adic/height evidence only. Exact integral replay, if present, still requires independent symbolic replay; no colon, saturation, secant, nullcone, or HC4 theorem follows.",
    }
    receipt_path = output / "extension.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
