#!/usr/bin/env -S sage -python
"""Independent replay of the p181^18 lift and frozen-denominator falsifier."""

from __future__ import annotations

import hashlib
import json
import math
import resource
import struct
import time
from fractions import Fraction
from pathlib import Path

from preprocess_fixed_p181_dixon_integer_system import build_rational_block


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
NONZEROS = 1_354_540
ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-fixed-block-denominator-18digit-test-v1"
ARTIFACT16 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-16digit-extension-v1"
X12 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-12digit-extension-v1/X_mod_181_power_12.json"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-fixed-block-denominator-18digit-test.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-fixed-block-denominator-18digit-test-independent-audit.json"


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
    old_r, remainder = modulus, residue
    old_t, coefficient = 0, 1
    while abs(remainder) > bound:
        quotient = old_r // remainder
        old_r, remainder = remainder, old_r - quotient * remainder
        old_t, coefficient = coefficient, old_t - quotient * coefficient
    numerator, denominator = remainder, coefficient
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


def center(value: int, modulus: int) -> int:
    residue = value % modulus
    return residue - modulus if residue > modulus // 2 else residue


def exact_model_mismatches(
    denominators: list[int],
    groups: list[int],
    residues: list[int],
    modulus: int,
    offsets: list[int],
    indices: list[int],
    values: list[int],
    rhs: list[int],
) -> tuple[int, list[int], str]:
    vector = [
        Fraction(center(denominators[groups[index]] * residues[index], modulus), denominators[groups[index]])
        for index in range(COLUMNS)
    ]
    mismatches = 0
    first_rows = []
    digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        if residual:
            mismatches += 1
            if len(first_rows) < 16:
                first_rows.append(row)
        digest.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    return mismatches, first_rows, digest.hexdigest()


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "18-digit independent audit already exists")
    producer = json.loads((ARTIFACT / "test.json").read_text(encoding="utf-8"))
    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    expected_status = "PASS_P181_18DIGIT_FIXED_DENOMINATOR_MODEL_FALSIFICATION"
    require(producer.get("status") == expected_status, "producer status drift")
    require(terminal.get("status") == expected_status, "terminal status drift")

    offsets, indices, values, rhs = read_integral()
    x16 = [int(value) for value in json.loads((ARTIFACT16 / "X_mod_181_power_16.json").read_text(encoding="utf-8"))]
    require(len(x16) == COLUMNS, "X16 dimension drift")
    modulus = P**16
    product = matvec(offsets, indices, values, x16)
    quotient = []
    starting_mismatches = 0
    for row in range(ROWS):
        residual = rhs[row] - product[row]
        starting_mismatches += int(residual % modulus != 0)
        quotient.append(residual // modulus)
    require(starting_mismatches == 0, "X16 divisibility replay failed")

    x18 = list(x16)
    digit_audits = []
    for digit_index in (16, 17):
        rhs_path = ARTIFACT / f"correction_rhs_digit_{digit_index}.u8"
        digit_path = ARTIFACT / f"digit_{digit_index}.u8"
        expected_rhs = bytes(value % P for value in quotient)
        require(rhs_path.read_bytes() == expected_rhs, f"correction RHS mismatch at digit {digit_index}")
        digit = list(digit_path.read_bytes())
        require(len(digit) == COLUMNS, f"digit dimension drift at {digit_index}")
        digit_product = matvec(offsets, indices, values, digit)
        next_quotient = []
        mismatches = 0
        for row in range(ROWS):
            numerator = quotient[row] - digit_product[row]
            mismatches += int(numerator % P != 0)
            next_quotient.append(numerator // P)
        require(mismatches == 0, f"correction divisibility failed at digit {digit_index}")
        x18 = [left + modulus * right for left, right in zip(x18, digit)]
        modulus *= P
        quotient = next_quotient
        digit_audits.append({
            "digit_index": digit_index,
            "rhs_sha256": file_hash(rhs_path),
            "digit_sha256": file_hash(digit_path),
            "divisibility_mismatches": mismatches,
        })
    require(modulus == P**18, "terminal modulus drift")
    serialized_x18 = [int(value) for value in json.loads((ARTIFACT / "X_mod_181_power_18.json").read_text(encoding="utf-8"))]
    require(x18 == serialized_x18, "X18 serialization mismatch")
    final_product = matvec(offsets, indices, values, x18)
    terminal_mismatches = sum(rhs[row] - final_product[row] != modulus * quotient[row] for row in range(ROWS))
    require(terminal_mismatches == 0, "terminal exact invariant failed")

    x14 = [int(value) for value in json.loads(X12.read_text(encoding="utf-8"))]
    modulus14 = P**12
    for digit_index in (12, 13):
        digit = list((ARTIFACT16 / f"digit_{digit_index}.u8").read_bytes())
        x14 = [left + modulus14 * right for left, right in zip(x14, digit)]
        modulus14 *= P
    require(modulus14 == P**14 and len(x14) == COLUMNS, "X14 reconstruction drift")
    stable = []
    for residue14, residue16 in zip(x14, x16):
        candidate = reconstruct(residue14, P**14)
        stable.append(candidate if candidate is not None and (residue16 * candidate[1] - candidate[0]) % (P**16) == 0 else None)
    require(sum(candidate == (0, 1) for candidate in stable) == 16_831, "stable zero census drift")
    require(sum(candidate is not None and candidate[0] != 0 for candidate in stable) == 1_279, "stable nonzero census drift")

    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    descriptors = build_rational_block(CAMPAIGN)["descriptors"]
    require(len(pivots) == COLUMNS and len(descriptors) == 38_048, "descriptor/gauge dimension drift")
    groups = [int(descriptors[index][0]) for index in pivots]
    require(set(groups) == set(range(19)), "multiplier-block coverage drift")
    block_denominators = [1] * 19
    for group, candidate in zip(groups, stable):
        if candidate is not None and candidate[0] != 0:
            block_denominators[group] = math.lcm(block_denominators[group], candidate[1])
    global_denominator = math.lcm(*block_denominators)
    require(all(value % P for value in block_denominators) and global_denominator % P, "denominator lost p181 unit")

    block_n16 = [center(block_denominators[group] * value, P**16) for group, value in zip(groups, x16)]
    block_n18 = [center(block_denominators[group] * value, P**18) for group, value in zip(groups, x18)]
    global_n16 = [center(global_denominator * value, P**16) for value in x16]
    global_n18 = [center(global_denominator * value, P**18) for value in x18]
    stability = {
        "block_model_stable_16_to_18": sum(left == right for left, right in zip(block_n16, block_n18)),
        "global_model_stable_16_to_18": sum(left == right for left, right in zip(global_n16, global_n18)),
        "block_model_maximum_digit18_bit_length": max(abs(value).bit_length() for value in block_n18),
        "global_model_maximum_digit18_bit_length": max(abs(value).bit_length() for value in global_n18),
    }
    require(stability == producer["numerator_stability"], "numerator-stability replay drift")

    block_mismatches, block_first, block_digest = exact_model_mismatches(
        block_denominators, groups, x18, P**18, offsets, indices, values, rhs
    )
    global_mismatches, global_first, global_digest = exact_model_mismatches(
        [global_denominator], [0] * COLUMNS, x18, P**18, offsets, indices, values, rhs
    )
    model_audits = [
        {
            "model": "19_multiplier_blocks",
            "exact_row_mismatches": block_mismatches,
            "first_mismatch_rows": block_first,
            "residual_stream_sha256": block_digest,
        },
        {
            "model": "single_global_lcm",
            "exact_row_mismatches": global_mismatches,
            "first_mismatch_rows": global_first,
            "residual_stream_sha256": global_digest,
        },
    ]
    for audit, expected in zip(model_audits, producer["models"]):
        require(audit["model"] == expected["model"], "model ordering drift")
        require(audit["exact_row_mismatches"] == expected["exact_row_mismatches"], "model mismatch-count drift")
        require(audit["first_mismatch_rows"] == expected["first_mismatch_rows"], "first mismatch rows drift")
        require(audit["residual_stream_sha256"] == expected["residual_stream_sha256"], "residual digest drift")
    require(block_mismatches > 0 and global_mismatches > 0, "frozen denominator model unexpectedly passed")

    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-fixed-block-denominator-18digit-test-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_18DIGIT_LIFT_AND_FIXED_DENOMINATOR_FALSIFICATION_REPLAY",
        "bound_hashes": {
            "auditor_script": file_hash(Path(__file__)),
            "producer": file_hash(ARTIFACT / "test.json"),
            "terminal": file_hash(TERMINAL),
            "integral": file_hash(INTEGRAL),
            "X16": file_hash(ARTIFACT16 / "X_mod_181_power_16.json"),
            "X18": file_hash(ARTIFACT / "X_mod_181_power_18.json"),
            "gauge": file_hash(GAUGE),
        },
        "lift_checks": {
            "starting_divisibility_mismatches": starting_mismatches,
            "correction_count": len(digit_audits),
            "terminal_modulus": str(modulus),
            "terminal_integer_invariant_mismatches": terminal_mismatches,
        },
        "digit_audits": digit_audits,
        "frozen_denominators": {
            "block_bit_lengths": [value.bit_length() for value in block_denominators],
            "global_bit_length": global_denominator.bit_length(),
        },
        "numerator_stability": stability,
        "model_audits": model_audits,
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "producer_not_imported_or_executed": True,
            "linbox_not_called": True,
            "X18_reconstructed_from_X16_and_raw_digits": True,
            "rational_reconstruction_reimplemented": True,
            "exact_model_replay_reimplemented": True,
            "canonical_source_descriptor_builder_shared": True,
            "no_nineteenth_digit": True,
        },
        "claim_boundary": "This PASS independently certifies the finite lift through 181^18 and falsifies only the frozen 19-block and global denominator models. It is not a QQ identity or any colon, saturation, secant, nullcone, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
