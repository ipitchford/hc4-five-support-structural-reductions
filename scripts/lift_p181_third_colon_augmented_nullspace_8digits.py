#!/usr/bin/env python3
"""Lift the audited p181 target solution through exactly eight total digits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import subprocess
import time
from array import array
from collections import Counter
from fractions import Fraction
from pathlib import Path

from fixed_p181_dixon_rr import (
    AMBIGUOUS,
    NO_CANDIDATE,
    UNIQUE_NONZERO,
    UNIQUE_ZERO,
    classify,
)


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
MODULAR_CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
DIGIT_ZERO = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral system magic drift")
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
    require(cursor == len(payload), "integral system trailing bytes")
    return offsets, indices, values, rhs


def matvec(offsets: list[int], indices: list[int], values: list[int], vector: list[int]) -> list[int]:
    output = [0] * ROWS
    for row in range(ROWS):
        output[row] = sum(
            values[position] * vector[indices[position]]
            for position in range(offsets[row], offsets[row + 1])
        )
    return output


def rr_snapshot(vector: list[int], modulus: int) -> tuple[bytes, dict[str, object], list[tuple[int, int] | None]]:
    labels = bytearray()
    counts: Counter[int] = Counter()
    candidates: list[tuple[int, int] | None] = []
    maximum_numerator = 0
    maximum_denominator = 0
    maximum_twice_product = 0
    for value in vector:
        outcome = classify(value % modulus, modulus)
        labels.append(outcome.label)
        counts[outcome.label] += 1
        candidate = outcome.candidates[0] if len(outcome.candidates) == 1 else None
        candidates.append(candidate)
        if candidate is not None:
            numerator, denominator = candidate
            maximum_numerator = max(maximum_numerator, abs(numerator))
            maximum_denominator = max(maximum_denominator, denominator)
            maximum_twice_product = max(maximum_twice_product, 2 * abs(numerator) * denominator)
    aggregate = {
        "NO_CANDIDATE": counts[NO_CANDIDATE],
        "UNIQUE_ZERO": counts[UNIQUE_ZERO],
        "UNIQUE_NONZERO": counts[UNIQUE_NONZERO],
        "AMBIGUOUS": counts[AMBIGUOUS],
    }
    return bytes(labels), {
        "modulus": str(modulus),
        "aggregate_labels": aggregate,
        "unique_coordinate_count": aggregate["UNIQUE_ZERO"] + aggregate["UNIQUE_NONZERO"],
        "maximum_accepted_absolute_numerator": maximum_numerator,
        "maximum_accepted_denominator": maximum_denominator,
        "maximum_accepted_twice_product": maximum_twice_product,
        "label_stream_sha256": hashlib.sha256(labels).hexdigest(),
    }, candidates


def exact_rational_replay(
    offsets: list[int],
    indices: list[int],
    values: list[int],
    rhs: list[int],
    candidates: list[tuple[int, int] | None],
) -> dict[str, object]:
    require(all(item is not None for item in candidates), "rational replay requires complete reconstruction")
    vector = [Fraction(item[0], item[1]) for item in candidates if item is not None]
    mismatches = 0
    digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        if residual:
            mismatches += 1
        digest.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    require(mismatches == 0, "exact rational integral-system replay failed")
    return {
        "mismatches": mismatches,
        "residual_stream_sha256": digest.hexdigest(),
        "maximum_numerator_bit_length": max(abs(item.numerator).bit_length() for item in vector),
        "maximum_denominator_bit_length": max(item.denominator.bit_length() for item in vector),
        "vector": vector,
    }


def write_rational_vector(path: Path, vector: list[Fraction]) -> None:
    records = [
        {"index": index, "numerator": value.numerator, "denominator": value.denominator}
        for index, value in enumerate(vector)
    ]
    path.write_text(json.dumps(records, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    offsets, indices, values, rhs = read_integral()
    x = list(DIGIT_ZERO.read_bytes())
    require(len(x) == COLUMNS, "digit-zero length drift")
    product_x = matvec(offsets, indices, values, x)
    q = []
    for row in range(ROWS):
        residual = rhs[row] - product_x[row]
        require(residual % P == 0, f"digit-zero residual not divisible at row {row}")
        q.append(residual // P)
    p_power = P
    digits = [bytes(x)]
    corrections: list[dict[str, object]] = []
    rr: dict[str, object] = {}
    rr_candidates: dict[int, list[tuple[int, int] | None]] = {}

    for digit_index in range(1, 8):
        digit_started = time.perf_counter()
        correction_rhs = bytes(value % P for value in q)
        correction_rhs_path = output / f"correction_rhs_digit_{digit_index}.u8"
        correction_path = output / f"digit_{digit_index}.u8"
        stdout_path = output / f"digit_{digit_index}.stdout.txt"
        stderr_path = output / f"digit_{digit_index}.stderr.txt"
        correction_rhs_path.write_bytes(correction_rhs)
        completed = subprocess.run(
            [
                str(DRIVER),
                "--csr", str(MODULAR_CSR),
                "--rhs", str(correction_rhs_path),
                "--solution-output", str(correction_path),
            ],
            cwd=CAMPAIGN,
            text=True,
            capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if (
            completed.returncode == 4
            and driver is not None
            and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD181"
        ):
            receipt = {
                "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-8digit-lift.v1",
                "status": "STOP_P181_LIFT_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit": digit_index,
                "completed_cumulative_digits": digit_index,
                "driver": driver,
                "corrections": corrections,
                "claim_boundary": "This exact STOP concerns only the fixed-gauge p181 lift at the registered digit.",
            }
            receipt_path = output / "lift.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": receipt["status"], "digit": digit_index, "receipt": str(receipt_path)}))
            return 4
        require(completed.returncode == 0 and driver is not None, f"correction driver failed at digit {digit_index}")
        require(driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE", "correction driver status drift")
        require(driver.get("augmented_nullity") == 1 and driver.get("replay_mismatches") == 0, "correction solve integrity drift")
        digit = list(correction_path.read_bytes())
        require(len(digit) == COLUMNS and all(value < P for value in digit), "correction digit stream drift")
        product_digit = matvec(offsets, indices, values, digit)
        q_next = []
        divisibility_mismatches = 0
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            if numerator % P:
                divisibility_mismatches += 1
            q_next.append(numerator // P)
        require(divisibility_mismatches == 0, f"nondivisible correction residual at digit {digit_index}")
        require(len(x) == len(digit), "correction vector length mismatch")
        x = [value + p_power * digit_value for value, digit_value in zip(x, digit)]
        p_power *= P
        q = q_next
        digits.append(bytes(digit))
        direct_product = matvec(offsets, indices, values, x) if digit_index == 7 else None
        direct_mismatches = (
            sum(rhs[row] - direct_product[row] != p_power * q[row] for row in range(ROWS))
            if direct_product is not None
            else None
        )
        require(direct_mismatches in (None, 0), "terminal direct integer invariant failed")
        record = {
            "digit_index": digit_index,
            "cumulative_digits": digit_index + 1,
            "modulus": str(p_power),
            "correction_rhs_sha256": file_hash(correction_rhs_path),
            "digit_sha256": file_hash(correction_path),
            "driver": driver,
            "divisibility_mismatches": divisibility_mismatches,
            "direct_integer_invariant_mismatches": direct_mismatches,
            "maximum_q_bit_length": max(abs(value).bit_length() for value in q),
            "maximum_X_bit_length": max(value.bit_length() for value in x),
            "wall_seconds": time.perf_counter() - digit_started,
        }
        corrections.append(record)
        if digit_index + 1 in (4, 6, 8):
            rr_started = time.perf_counter()
            labels, snapshot, candidates = rr_snapshot(x, p_power)
            snapshot["seconds"] = time.perf_counter() - rr_started
            (output / f"rr_labels_{digit_index + 1}.u8").write_bytes(labels)
            rr[str(digit_index + 1)] = snapshot
            rr_candidates[digit_index + 1] = candidates

    require(p_power == P**8 == 1_151_936_657_823_500_641, "terminal modulus drift")
    x_path = output / "X_mod_181_power_8.u64le"
    packed_x = array("Q", x)
    x_path.write_bytes(packed_x.tobytes())
    held_out = {"eligible_at_digit_6": 0, "matches_through_digit_8": 0}
    require(len(x) == len(rr_candidates[6]), "digit-six reconstruction length mismatch")
    for residue8, candidate in zip(x, rr_candidates[6]):
        if candidate is None:
            continue
        held_out["eligible_at_digit_6"] += 1
        numerator, denominator = candidate
        if (residue8 * denominator - numerator) % p_power == 0:
            held_out["matches_through_digit_8"] += 1

    final_candidates = rr_candidates[8]
    complete_reconstruction = all(item is not None for item in final_candidates)
    exact_replay = None
    rational_output = None
    if complete_reconstruction:
        exact_started = time.perf_counter()
        replay = exact_rational_replay(offsets, indices, values, rhs, final_candidates)
        vector = replay.pop("vector")
        replay["seconds"] = time.perf_counter() - exact_started
        exact_replay = replay
        rational_path = output / "rational_solution.json"
        write_rational_vector(rational_path, vector)
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}

    status = (
        "PASS_P181_8DIGIT_LIFT_AND_EXACT_RATIONAL_SYSTEM_REPLAY"
        if complete_reconstruction and exact_replay is not None
        else "PASS_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT"
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-8digit-lift.v1",
        "status": status,
        "inputs": {
            "integral_system_sha256": file_hash(INTEGRAL),
            "modular_csr_sha256": file_hash(MODULAR_CSR),
            "digit_zero_sha256": file_hash(DIGIT_ZERO),
            "driver_sha256": file_hash(DRIVER),
        },
        "dimensions": {"rows": ROWS, "columns": COLUMNS, "nonzeros": NONZEROS, "total_digits": 8},
        "terminal_modulus": str(p_power),
        "terminal_X": {"path": x_path.name, "sha256": file_hash(x_path), "bytes": x_path.stat().st_size},
        "digit_zero_sha256": hashlib.sha256(digits[0]).hexdigest(),
        "corrections": corrections,
        "rr_snapshots": rr,
        "digit6_two_digit_holdout": held_out,
        "complete_digit8_rational_reconstruction": complete_reconstruction,
        "exact_rational_integral_system_replay": exact_replay,
        "rational_solution": rational_output,
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "exactly_eight_total_digits": True,
            "no_ninth_digit": True,
            "quarantined_dixon_bundle_not_read": True,
            "legacy_coordinate_vector_not_read": True,
            "every_correction_solved_by_augmented_nullspace": True,
        },
        "claim_boundary": (
            "An eight-digit PASS without exact reconstruction is finite p-adic evidence only. Exact integral "
            "system replay, if present, still requires independent symbolic replay before a QQ identity claim; "
            "no colon, saturation, secant, nullcone, or HC4 theorem follows here."
        ),
    }
    receipt_path = output / "lift.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
