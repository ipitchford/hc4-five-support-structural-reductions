#!/usr/bin/env -S sage -python
"""Test global and 19-block simultaneous denominator models at p181^16."""

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

from preprocess_fixed_p181_dixon_integer_system import build_rational_block
from scout_p181_third_colon_equal_height_reconstruction import own_reconstruction


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
COLUMNS = 35_881
ARTIFACT16 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-16digit-extension-v1"
X12 = CAMPAIGN / "artifacts/third-colon-p181-augmented-nullspace-12digit-extension-v1/X_mod_181_power_12.json"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
INTEGRAL = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_b_Z_fixed_gauge.i64csr"
AUDIT16 = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-16digit-extension-independent-audit.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    payload = INTEGRAL.read_bytes()
    require(payload[:8] == b"HC4ZI181", "integral magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, COLUMNS, 1_354_540), "integral dimensions drift")
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


def build_x14() -> list[int]:
    x = [int(value) for value in json.loads(X12.read_text(encoding="utf-8"))]
    modulus = P**12
    for digit_index in (12, 13):
        digit = list((ARTIFACT16 / f"digit_{digit_index}.u8").read_bytes())
        require(len(x) == len(digit) == COLUMNS, "digit length drift")
        x = [left + modulus * right for left, right in zip(x, digit)]
        modulus *= P
    require(modulus == P**14, "X14 modulus drift")
    return x


def center(value: int, modulus: int) -> int:
    value %= modulus
    return value - modulus if value > modulus // 2 else value


def replay_model(
    name: str,
    denominators: list[int],
    groups: list[int],
    x16: list[int],
    stable: list[tuple[int, int] | None],
    offsets: list[int],
    indices: list[int],
    values: list[int],
    rhs: list[int],
    modulus: int,
) -> tuple[dict[str, object], list[Fraction] | None]:
    vector = []
    stable_mismatches = 0
    for index, residue in enumerate(x16):
        denominator = denominators[groups[index]]
        numerator = center((denominator % modulus) * residue, modulus)
        value = Fraction(numerator, denominator)
        vector.append(value)
        candidate = stable[index]
        if candidate is not None and value != Fraction(candidate[0], candidate[1]):
            stable_mismatches += 1
    mismatches = 0
    first_mismatch_rows = []
    residual_digest = hashlib.sha256()
    for row in range(ROWS):
        total = sum(
            (values[position] * vector[indices[position]] for position in range(offsets[row], offsets[row + 1])),
            Fraction(0),
        )
        residual = total - rhs[row]
        if residual:
            mismatches += 1
            if len(first_mismatch_rows) < 16:
                first_mismatch_rows.append(row)
        residual_digest.update(f"{residual.numerator}/{residual.denominator}\n".encode("ascii"))
    record = {
        "model": name,
        "denominator_count": len(denominators),
        "denominator_bit_lengths": [value.bit_length() for value in denominators],
        "maximum_denominator_bit_length": max(value.bit_length() for value in denominators),
        "stable_candidate_mismatches": stable_mismatches,
        "exact_row_mismatches": mismatches,
        "first_mismatch_rows": first_mismatch_rows,
        "residual_stream_sha256": residual_digest.hexdigest(),
        "maximum_reconstructed_numerator_bit_length": max(abs(value.numerator).bit_length() for value in vector),
        "maximum_reconstructed_denominator_bit_length": max(value.denominator.bit_length() for value in vector),
    }
    return record, vector if mismatches == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    audit = json.loads(AUDIT16.read_text(encoding="utf-8"))
    require(audit.get("status") == "PASS_INDEPENDENT_P181_AUGMENTED_NULLSPACE_16DIGIT_EXTENSION_REPLAY", "16-digit audit PASS drift")
    x14 = build_x14()
    x16 = [int(value) for value in json.loads((ARTIFACT16 / "X_mod_181_power_16.json").read_text(encoding="utf-8"))]
    require(len(x14) == len(x16) == COLUMNS, "terminal vector length drift")
    modulus14 = P**14
    modulus16 = P**16
    stable: list[tuple[int, int] | None] = []
    for residue14, residue16 in zip(x14, x16):
        candidate = own_reconstruction(residue14, modulus14)
        if candidate is None or (residue16 * candidate[1] - candidate[0]) % modulus16:
            stable.append(None)
        else:
            stable.append(candidate)
    stable_nonzero = sum(item is not None and item[0] != 0 for item in stable)
    stable_zero = sum(item == (0, 1) for item in stable)
    require(stable_nonzero == 1_279 and stable_zero == 16_831, "stable candidate census drift")

    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    block = build_rational_block(CAMPAIGN)
    descriptors = block["descriptors"]
    require(len(pivots) == COLUMNS and len(descriptors) == 38_048, "descriptor/gauge dimensions drift")
    groups = [int(descriptors[global_index][0]) for global_index in pivots]
    require(set(groups) == set(range(19)), "not all multiplier blocks represented")
    block_denominators = [1] * 19
    block_stable_nonzero_counts = [0] * 19
    for group, candidate in zip(groups, stable):
        if candidate is not None and candidate[0] != 0:
            block_denominators[group] = math.lcm(block_denominators[group], candidate[1])
            block_stable_nonzero_counts[group] += 1
    global_denominator = math.lcm(*block_denominators)
    require(global_denominator % P != 0 and all(value % P != 0 for value in block_denominators), "reconstructed denominator lost p181 unit")

    offsets, indices, values, rhs = read_integral()
    block_record, block_vector = replay_model("19_multiplier_blocks", block_denominators, groups, x16, stable, offsets, indices, values, rhs, modulus16)
    global_record, global_vector = replay_model("single_global_lcm", [global_denominator], [0] * COLUMNS, x16, stable, offsets, indices, values, rhs, modulus16)
    passing_model = "19_multiplier_blocks" if block_vector is not None else "single_global_lcm" if global_vector is not None else None
    passing_vector = block_vector if block_vector is not None else global_vector
    rational_output = None
    if passing_vector is not None:
        rational_path = output / "rational_solution.json"
        rational_path.write_text(
            json.dumps([{"index": index, "numerator": value.numerator, "denominator": value.denominator} for index, value in enumerate(passing_vector)], separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        rational_output = {"path": rational_path.name, "sha256": file_hash(rational_path), "bytes": rational_path.stat().st_size}
    status = "PASS_EXACT_BLOCK_DENOMINATOR_RATIONAL_SYSTEM_REPLAY" if passing_model is not None else "PASS_INCOMPLETE_BLOCK_DENOMINATOR_SCOUT"
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-block-denominator-reconstruction-scout.v1",
        "status": status,
        "inputs": {"audit16_sha256": file_hash(AUDIT16), "X16_sha256": file_hash(ARTIFACT16 / "X_mod_181_power_16.json"), "integral_system_sha256": file_hash(INTEGRAL), "gauge_sha256": file_hash(GAUGE)},
        "stable_candidates": {"zero": stable_zero, "nonzero": stable_nonzero, "total": stable_zero + stable_nonzero},
        "block_stable_nonzero_counts": block_stable_nonzero_counts,
        "block_denominator_bit_lengths": [value.bit_length() for value in block_denominators],
        "global_denominator_bit_length": global_denominator.bit_length(),
        "models": [block_record, global_record],
        "passing_model": passing_model,
        "rational_solution": rational_output,
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"only_digit14_candidates_with_two_heldout_digit_match_used": True, "minimal_lcm_denominators_used": True, "no_adaptive_factor_insertion": True, "no_seventeenth_digit": True},
        "claim_boundary": "An incomplete PASS is simultaneous-denominator height evidence only. Exact integral replay, if present, still requires independent symbolic replay; no colon, saturation, secant, nullcone, or HC4 theorem follows.",
    }
    receipt_path = output / "block-denominator.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
