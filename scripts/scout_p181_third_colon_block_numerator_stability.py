#!/usr/bin/env -S sage -python
"""Measure centered numerator stabilization under frozen block denominators."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from pathlib import Path

from preprocess_fixed_p181_dixon_integer_system import build_rational_block
from scout_p181_third_colon_block_denominator_reconstruction import (
    ARTIFACT16,
    CAMPAIGN,
    COLUMNS,
    GAUGE,
    P,
    X12,
    build_x14,
    center,
    file_hash,
    require,
)
from scout_p181_third_colon_equal_height_reconstruction import own_reconstruction


BLOCK_SCOUT = CAMPAIGN / "artifacts/third-colon-p181-block-denominator-reconstruction-v1/block-denominator.json"


def summary(n14: list[int], n16: list[int], groups: list[int]) -> dict[str, object]:
    stable = [left == right for left, right in zip(n14, n16)]
    smaller_half = P**14 // 2
    return {
        "stable_total": sum(stable),
        "unstable_total": COLUMNS - sum(stable),
        "stable_by_block": [sum(flag for flag, group in zip(stable, groups) if group == index) for index in range(19)],
        "coordinates_with_digit16_numerator_inside_digit14_half_window": sum(abs(value) < smaller_half for value in n16),
        "maximum_digit14_numerator_bit_length": max(abs(value).bit_length() for value in n14),
        "maximum_digit16_numerator_bit_length": max(abs(value).bit_length() for value in n16),
        "digit16_bit_length_histogram": {str(bits): sum(abs(value).bit_length() == bits for value in n16) for bits in sorted({abs(value).bit_length() for value in n16})},
        "stable_stream_sha256": hashlib.sha256(bytes(stable)).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    prior = json.loads(BLOCK_SCOUT.read_text(encoding="utf-8"))
    require(prior.get("status") == "PASS_INCOMPLETE_BLOCK_DENOMINATOR_SCOUT", "block scout status drift")
    x14 = build_x14()
    x16 = [int(value) for value in json.loads((ARTIFACT16 / "X_mod_181_power_16.json").read_text(encoding="utf-8"))]
    modulus14, modulus16 = P**14, P**16
    stable_candidates = []
    for left, right in zip(x14, x16):
        candidate = own_reconstruction(left, modulus14)
        stable_candidates.append(candidate if candidate is not None and (right * candidate[1] - candidate[0]) % modulus16 == 0 else None)
    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    descriptors = build_rational_block(CAMPAIGN)["descriptors"]
    groups = [int(descriptors[global_index][0]) for global_index in pivots]
    denominators = [1] * 19
    for group, candidate in zip(groups, stable_candidates):
        if candidate is not None and candidate[0] != 0:
            denominators[group] = math.lcm(denominators[group], candidate[1])
    global_denominator = math.lcm(*denominators)
    block_n14 = [center((denominators[group] % modulus14) * value, modulus14) for value, group in zip(x14, groups)]
    block_n16 = [center((denominators[group] % modulus16) * value, modulus16) for value, group in zip(x16, groups)]
    global_n14 = [center((global_denominator % modulus14) * value, modulus14) for value in x14]
    global_n16 = [center((global_denominator % modulus16) * value, modulus16) for value in x16]
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-block-numerator-stability.v1",
        "status": "PASS_BLOCK_NUMERATOR_STABILITY_DIAGNOSTIC",
        "inputs": {"block_scout_sha256": file_hash(BLOCK_SCOUT), "X16_sha256": file_hash(ARTIFACT16 / "X_mod_181_power_16.json")},
        "block_denominator_bit_lengths": [value.bit_length() for value in denominators],
        "global_denominator_bit_length": global_denominator.bit_length(),
        "block_model": summary(block_n14, block_n16, groups),
        "global_model": summary(global_n14, global_n16, [0] * COLUMNS),
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"denominators_recomputed_without_adaptation": True, "no_new_digit": True, "no_solve": True},
        "claim_boundary": "This is a fixed-denominator numerator-stability diagnostic only; it proves no rational identity or downstream geometric theorem.",
    }
    receipt_path = output / "numerator-stability.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
