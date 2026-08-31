#!/usr/bin/env python3
"""Lift the audited p=173 fourth-colon target through eight total digits."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import subprocess
import time
from array import array
from collections import Counter
from fractions import Fraction
from pathlib import Path

from fixed_p181_dixon_rr import AMBIGUOUS, NO_CANDIDATE, UNIQUE_NONZERO, UNIQUE_ZERO, classify


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 173
ROWS = 85_688
COLUMNS = 36_587
NONZEROS = 1_487_624
SYSTEM_DIR = CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
INTEGRAL = SYSTEM_DIR / "A_Z_b_Z_fixed_gauge_p173.i64csr"
MODULAR_CSR = SYSTEM_DIR / "A_Z_mod173_fixed_gauge.csr"
DIGIT_ZERO = SYSTEM_DIR / "solution_mod173.u8"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod173_fourth_target_driver"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI173", "integral system magic drift")
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
    return [
        sum(values[pos] * vector[indices[pos]] for pos in range(offsets[row], offsets[row + 1]))
        for row in range(ROWS)
    ]


def rr_snapshot(vector: list[int], modulus: int) -> tuple[bytes, dict[str, object], list[tuple[int, int] | None]]:
    labels = bytearray()
    counts: Counter[int] = Counter()
    candidates: list[tuple[int, int] | None] = []
    max_num = max_den = max_product = 0
    for value in vector:
        outcome = classify(value % modulus, modulus)
        labels.append(outcome.label)
        counts[outcome.label] += 1
        candidate = outcome.candidates[0] if len(outcome.candidates) == 1 else None
        candidates.append(candidate)
        if candidate is not None:
            numerator, denominator = candidate
            max_num = max(max_num, abs(numerator))
            max_den = max(max_den, denominator)
            max_product = max(max_product, 2 * abs(numerator) * denominator)
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
        "maximum_accepted_absolute_numerator": max_num,
        "maximum_accepted_denominator": max_den,
        "maximum_accepted_twice_product": max_product,
        "label_stream_sha256": hashlib.sha256(labels).hexdigest(),
    }, candidates


def exact_replay(
    offsets: list[int], indices: list[int], values: list[int], rhs: list[int],
    candidates: list[tuple[int, int] | None],
) -> tuple[dict[str, object], list[Fraction]]:
    require(all(item is not None for item in candidates), "complete reconstruction required")
    vector = [Fraction(item[0], item[1]) for item in candidates if item is not None]
    mismatches = 0
    digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[pos] * vector[indices[pos]] for pos in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        mismatches += bool(residual)
        digest.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    require(mismatches == 0, "exact rational system replay failed")
    return {
        "mismatches": mismatches,
        "residual_stream_sha256": digest.hexdigest(),
        "maximum_numerator_bit_length": max(abs(item.numerator).bit_length() for item in vector),
        "maximum_denominator_bit_length": max(item.denominator.bit_length() for item in vector),
    }, vector


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)

    offsets, indices, values, rhs = read_integral()
    x = list(DIGIT_ZERO.read_bytes())
    require(len(x) == COLUMNS, "digit-zero length drift")
    product = matvec(offsets, indices, values, x)
    q: list[int] = []
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        require(residual % P == 0, f"digit-zero residual not divisible at row {row}")
        q.append(residual // P)

    p_power = P
    corrections: list[dict[str, object]] = []
    rr: dict[str, object] = {}
    rr_candidates: dict[int, list[tuple[int, int] | None]] = {}

    for digit_index in range(1, 8):
        digit_started = time.perf_counter()
        rhs_path = output / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = output / f"digit_{digit_index}.u8"
        stdout_path = output / f"digit_{digit_index}.stdout.txt"
        stderr_path = output / f"digit_{digit_index}.stderr.txt"
        rhs_path.write_bytes(bytes(value % P for value in q))
        completed = subprocess.run(
            [str(DRIVER), "--csr", str(MODULAR_CSR), "--rhs", str(rhs_path),
             "--solution-output", str(digit_path)],
            cwd=CAMPAIGN, text=True, capture_output=True,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD173":
            receipt = {
                "schema": "hc4.decimic-j2-secant-r10-p173-fourth-colon-8digit-lift.v1",
                "status": "STOP_P173_FOURTH_COLON_LIFT_CORRECTION_OUTSIDE_COLUMN_SPACE",
                "stopped_at_digit": digit_index,
                "corrections": corrections,
                "driver": driver,
                "claim_boundary": "This STOP concerns only the registered fixed-gauge p173 lift.",
            }
            receipt_path = output / "lift.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}))
            return 4
        require(completed.returncode == 0 and driver is not None, f"driver failed at digit {digit_index}")
        require(driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD173_EXPLICIT_TARGET_SOLVE", "driver status drift")
        require(driver.get("augmented_nullity") == 1 and driver.get("replay_mismatches") == 0, "driver integrity drift")

        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS and all(value < P for value in digit), "digit stream drift")
        product_digit = matvec(offsets, indices, values, digit)
        q_next: list[int] = []
        for row in range(ROWS):
            numerator = q[row] - product_digit[row]
            require(numerator % P == 0, f"nondivisible correction residual at digit {digit_index}, row {row}")
            q_next.append(numerator // P)
        x = [value + p_power * digit_value for value, digit_value in zip(x, digit)]
        p_power *= P
        q = q_next
        direct_mismatches = None
        if digit_index == 7:
            direct = matvec(offsets, indices, values, x)
            direct_mismatches = sum(rhs[row] - direct[row] != p_power * q[row] for row in range(ROWS))
            require(direct_mismatches == 0, "terminal integer invariant failed")
        corrections.append({
            "digit_index": digit_index,
            "cumulative_digits": digit_index + 1,
            "modulus": str(p_power),
            "correction_rhs_sha256": file_hash(rhs_path),
            "digit_sha256": file_hash(digit_path),
            "driver": driver,
            "direct_integer_invariant_mismatches": direct_mismatches,
            "maximum_q_bit_length": max(abs(value).bit_length() for value in q),
            "maximum_X_bit_length": max(value.bit_length() for value in x),
            "wall_seconds": time.perf_counter() - digit_started,
        })
        if digit_index + 1 in (4, 6, 8):
            rr_started = time.perf_counter()
            labels, snapshot, candidates = rr_snapshot(x, p_power)
            snapshot["seconds"] = time.perf_counter() - rr_started
            (output / f"rr_labels_{digit_index + 1}.u8").write_bytes(labels)
            rr[str(digit_index + 1)] = snapshot
            rr_candidates[digit_index + 1] = candidates

    require(p_power == P**8 == 802_359_178_476_091_681, "terminal modulus drift")
    x_path = output / "X_mod_173_power_8.u64le"
    x_path.write_bytes(array("Q", x).tobytes())

    held_out = {"eligible_at_digit_6": 0, "matches_through_digit_8": 0}
    for residue8, candidate in zip(x, rr_candidates[6]):
        if candidate is None:
            continue
        held_out["eligible_at_digit_6"] += 1
        numerator, denominator = candidate
        held_out["matches_through_digit_8"] += (residue8 * denominator - numerator) % p_power == 0

    final_candidates = rr_candidates[8]
    complete = all(item is not None for item in final_candidates)
    exact = None
    rational_output = None
    if complete:
        replay_started = time.perf_counter()
        exact, vector = exact_replay(offsets, indices, values, rhs, final_candidates)
        exact["seconds"] = time.perf_counter() - replay_started
        rational_path = output / "rational_solution.json"
        rational_path.write_text(json.dumps([
            {"index": index, "numerator": value.numerator, "denominator": value.denominator}
            for index, value in enumerate(vector)
        ], separators=(",", ":")) + "\n", encoding="utf-8")
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}

    status = (
        "PASS_P173_FOURTH_COLON_8DIGIT_LIFT_AND_EXACT_RATIONAL_SYSTEM_REPLAY"
        if complete and exact is not None else "PASS_P173_FOURTH_COLON_AUGMENTED_NULLSPACE_8DIGIT_LIFT"
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p173-fourth-colon-8digit-lift.v1",
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
        "corrections": corrections,
        "rr_snapshots": rr,
        "digit6_two_digit_holdout": held_out,
        "complete_digit8_rational_reconstruction": complete,
        "exact_rational_integral_system_replay": exact,
        "rational_solution": rational_output,
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {
            "exactly_eight_total_digits": True,
            "no_ninth_digit": True,
            "every_correction_solved_by_augmented_nullspace": True,
            "no_gauge_change_after_observation": True,
        },
        "claim_boundary": (
            "An eight-digit PASS without exact reconstruction is finite p-adic evidence only. "
            "An exact system replay still requires an independent semantic polynomial replay; "
            "no colon equality, saturation, secant, nullcone, or HC4 theorem follows here."
        ),
    }
    receipt_path = output / "lift.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
