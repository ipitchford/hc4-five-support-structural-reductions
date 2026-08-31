#!/usr/bin/env -S sage -python
"""Add two held-out p181 digits and test the frozen denominator models."""

from __future__ import annotations

import argparse
import json
import math
import resource
import subprocess
import time
from pathlib import Path

from preprocess_fixed_p181_dixon_integer_system import build_rational_block
from scout_p181_third_colon_block_denominator_reconstruction import (
    ARTIFACT16,
    CAMPAIGN,
    COLUMNS,
    GAUGE,
    INTEGRAL,
    P,
    ROWS,
    build_x14,
    center,
    file_hash,
    read_integral,
    replay_model,
    require,
)
from scout_p181_third_colon_equal_height_reconstruction import own_reconstruction


AUDIT16 = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-16digit-extension-independent-audit.json"
MODULAR_CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
DRIVER = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"


def matvec(offsets: list[int], indices: list[int], values: list[int], vector: list[int]) -> list[int]:
    return [sum(values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])) for row in range(ROWS)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(AUDIT16.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION_REPLAY", "16-digit audit PASS drift")
    offsets, indices, values, rhs = read_integral()
    x16 = [int(value) for value in json.loads((ARTIFACT16 / "X_mod_181_power_16.json").read_text(encoding="utf-8"))]
    modulus = P**16
    product = matvec(offsets, indices, values, x16)
    q = []
    starting_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_mismatches += int(residual % modulus != 0)
        q.append(residual // modulus)
    require(starting_mismatches == 0, "X16 exact divisibility replay failed")

    x = list(x16)
    corrections = []
    for digit_index in (16, 17):
        digit_started = time.perf_counter()
        correction_rhs = bytes(value % P for value in q)
        rhs_path = output / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = output / f"digit_{digit_index}.u8"
        stdout_path = output / f"digit_{digit_index}.stdout.txt"
        stderr_path = output / f"digit_{digit_index}.stderr.txt"
        rhs_path.write_bytes(correction_rhs)
        completed = subprocess.run([str(DRIVER), "--csr", str(MODULAR_CSR), "--rhs", str(rhs_path), "--solution-output", str(digit_path)], cwd=CAMPAIGN, text=True, capture_output=True)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        driver = json.loads(lines[0]) if len(lines) == 1 else None
        if completed.returncode == 4 and driver is not None and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD181":
            receipt = {"schema": "hc4.decimic-j2-secant-r10-p181-fixed-block-denominator-18digit-test.v1", "status": "STOP_P181_18DIGIT_TEST_CORRECTION_OUTSIDE_COLUMN_SPACE", "stopped_at_digit": digit_index, "corrections": corrections, "driver": driver}
            receipt_path = output / "test.json"
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}))
            return 4
        require(completed.returncode == 0 and driver is not None, f"driver failed at digit {digit_index}")
        require(driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE" and driver.get("replay_mismatches") == 0, "driver integrity drift")
        digit = list(digit_path.read_bytes())
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
        corrections.append({"digit_index": digit_index, "cumulative_digits": digit_index + 1, "driver": driver, "digit_sha256": file_hash(digit_path), "correction_rhs_sha256": file_hash(rhs_path), "divisibility_mismatches": mismatches, "wall_seconds": time.perf_counter() - digit_started})
    require(modulus == P**18, "terminal modulus drift")
    terminal_product = matvec(offsets, indices, values, x)
    terminal_mismatches = sum(rhs[row] - terminal_product[row] != modulus * q[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal exact invariant failed")
    x18_path = output / "X_mod_181_power_18.json"
    x18_path.write_text(json.dumps([str(value) for value in x], separators=(",", ":")) + "\n", encoding="utf-8")

    x14 = build_x14()
    stable = []
    for residue14, residue16 in zip(x14, x16):
        candidate = own_reconstruction(residue14, P**14)
        stable.append(candidate if candidate is not None and (residue16 * candidate[1] - candidate[0]) % (P**16) == 0 else None)
    pivots = [item[0] for item in __import__("struct").iter_unpack("<I", GAUGE.read_bytes())]
    descriptors = build_rational_block(CAMPAIGN)["descriptors"]
    groups = [int(descriptors[global_index][0]) for global_index in pivots]
    denominators = [1] * 19
    for group, candidate in zip(groups, stable):
        if candidate is not None and candidate[0] != 0:
            denominators[group] = math.lcm(denominators[group], candidate[1])
    global_denominator = math.lcm(*denominators)
    block_n16 = [center((denominators[group] % (P**16)) * value, P**16) for value, group in zip(x16, groups)]
    block_n18 = [center((denominators[group] % modulus) * value, modulus) for value, group in zip(x, groups)]
    global_n16 = [center((global_denominator % (P**16)) * value, P**16) for value in x16]
    global_n18 = [center((global_denominator % modulus) * value, modulus) for value in x]
    block_stable = sum(left == right for left, right in zip(block_n16, block_n18))
    global_stable = sum(left == right for left, right in zip(global_n16, global_n18))

    block_record, block_vector = replay_model("19_multiplier_blocks", denominators, groups, x, stable, offsets, indices, values, rhs, modulus)
    global_record, global_vector = replay_model("single_global_lcm", [global_denominator], [0] * COLUMNS, x, stable, offsets, indices, values, rhs, modulus)
    passing_model = "19_multiplier_blocks" if block_vector is not None else "single_global_lcm" if global_vector is not None else None
    passing_vector = block_vector if block_vector is not None else global_vector
    rational_output = None
    if passing_vector is not None:
        rational_path = output / "rational_solution.json"
        rational_path.write_text(json.dumps([{"index": index, "numerator": value.numerator, "denominator": value.denominator} for index, value in enumerate(passing_vector)], separators=(",", ":")) + "\n", encoding="utf-8")
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}
    status = "PASS_P181_18DIGIT_FIXED_DENOMINATOR_EXACT_RATIONAL_SYSTEM_REPLAY" if passing_model is not None else "PASS_P181_18DIGIT_FIXED_DENOMINATOR_MODEL_FALSIFICATION"
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-fixed-block-denominator-18digit-test.v1",
        "status": status,
        "inputs": {"audit16_sha256": file_hash(AUDIT16), "X16_sha256": file_hash(ARTIFACT16 / "X_mod_181_power_16.json"), "integral_sha256": file_hash(INTEGRAL)},
        "starting_divisibility_mismatches": starting_mismatches,
        "corrections": corrections,
        "terminal_modulus": str(modulus),
        "terminal_X": {"path": x18_path.name, "sha256": file_hash(x18_path), "bytes": x18_path.stat().st_size},
        "terminal_integer_invariant_mismatches": terminal_mismatches,
        "frozen_denominators": {"block_bit_lengths": [value.bit_length() for value in denominators], "global_bit_length": global_denominator.bit_length()},
        "numerator_stability": {"block_model_stable_16_to_18": block_stable, "global_model_stable_16_to_18": global_stable, "block_model_maximum_digit18_bit_length": max(abs(value).bit_length() for value in block_n18), "global_model_maximum_digit18_bit_length": max(abs(value).bit_length() for value in global_n18)},
        "models": [block_record, global_record],
        "passing_model": passing_model,
        "rational_solution": rational_output,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"denominators_frozen_from_digits_14_and_16": True, "new_digits_not_used_to_adapt_model": True, "exactly_two_new_digits": True, "no_nineteenth_digit": True},
        "claim_boundary": "A model-falsification PASS preserves only the exact finite p181^18 lift and rejects these denominator models. Exact integral replay, if present, still requires independent symbolic replay; no downstream geometric theorem follows.",
    }
    receipt_path = output / "test.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
