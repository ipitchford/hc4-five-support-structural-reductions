#!/usr/bin/env -S sage -python
"""Independent modular-row audit of the source-clean ``M*h3`` RHS artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import time
from pathlib import Path

from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    build_character_block,
)
from scout_decimic_nullcone_hsop import digest


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
CSR = CAMPAIGN / (
    "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/"
    "A_C_mod181_target_free.csr"
)
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
CSR_SHA256 = "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef"
GAUGE_SHA256 = "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2"
TARGET_SHA256 = "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csr() -> tuple[list[int], list[int], bytes]:
    payload = CSR.read_bytes()
    require(file_hash(CSR) == CSR_SHA256, "CSR hash drift")
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85_651, 35_881, 1_354_540), "CSR dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = payload[cursor:cursor + nonzeros]
    cursor += nonzeros
    require(cursor == len(payload), "CSR trailing bytes")
    return offsets, indices, values


def read_pivots() -> list[int]:
    payload = GAUGE.read_bytes()
    require(file_hash(GAUGE) == GAUGE_SHA256, "pivot gauge hash drift")
    pivots = [item[0] for item in struct.iter_unpack("<I", payload)]
    require(len(pivots) == 35_881 and len(set(pivots)) == len(pivots), "pivot gauge drift")
    return pivots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    artifact = arguments.artifact_dir if arguments.artifact_dir.is_absolute() else CAMPAIGN / arguments.artifact_dir
    output = arguments.output if arguments.output.is_absolute() else CAMPAIGN / arguments.output
    require(not output.exists(), "audit output already exists")
    receipt_path = artifact / "target-rhs.json"
    rhs_path = artifact / "target_rhs_mod181.u8"
    scales_path = artifact / "coefficient_row_scales_mod181.u8"
    exact_path = artifact / "target_rhs_nonzero_rational.json"
    producer = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(producer.get("status") == "PASS_SOURCE_CLEAN_P181_EXPLICIT_TARGET_RHS_RECONSTRUCTION", "producer PASS drift")
    rhs = rhs_path.read_bytes()
    scales = scales_path.read_bytes()
    exact_rows = json.loads(exact_path.read_text(encoding="utf-8"))
    require(len(rhs) == len(scales) == 85_651, "RHS or scale length drift")
    require(len(exact_rows) == 486, "exact nonzero target support drift")
    for path in (rhs_path, scales_path, exact_path):
        record = producer["outputs"][path.name]
        require(file_hash(path) == record["sha256"] and path.stat().st_size == record["bytes"], f"producer output drift: {path.name}")

    pivots = read_pivots()
    global_to_local = {global_column: local for local, global_column in enumerate(pivots)}
    offsets, indices, values = read_csr()
    block = build_character_block(CAMPAIGN, P, require_full_support=True)
    require(len(block["sparse_equations"]) == 85_651, "independent row count drift")
    require(len(block["right_hand_side"]) == 85_651, "independent RHS row count drift")
    require(digest((block["target_expression"],)) == TARGET_SHA256, "independent target hash drift")

    scale_mismatches = 0
    rhs_mismatches = 0
    support_mismatches = 0
    nonzero_raw_target = 0
    independently_derived = bytearray()
    for row_index, (raw_row, raw_rhs) in enumerate(
        zip(block["sparse_equations"], block["right_hand_side"], strict=True)
    ):
        raw_selected = {
            global_to_local[global_column]: int(value) % P
            for global_column, value in raw_row.items()
            if global_column in global_to_local
        }
        actual = {
            indices[position]: values[position]
            for position in range(offsets[row_index], offsets[row_index + 1])
        }
        if set(raw_selected) != set(actual) or not actual:
            support_mismatches += 1
            independently_derived.append(0)
            continue
        first_local = min(actual)
        raw_first = raw_selected[first_local]
        require(raw_first != 0, "independent selected coefficient vanished")
        scale = actual[first_local] * pow(raw_first, -1, P) % P
        if scale == 0 or any(actual[local] != scale * value % P for local, value in raw_selected.items()):
            scale_mismatches += 1
        if scales[row_index] != scale:
            scale_mismatches += 1
        expected_rhs = scale * int(raw_rhs) % P
        independently_derived.append(expected_rhs)
        if rhs[row_index] != expected_rhs:
            rhs_mismatches += 1
        if raw_rhs:
            nonzero_raw_target += 1

    require(support_mismatches == 0, "independent selected support mismatch")
    require(scale_mismatches == 0, "independent row-scale mismatch")
    require(rhs_mismatches == 0, "independent target RHS mismatch")
    require(nonzero_raw_target == 486, "independent target support count drift")
    require(bytes(independently_derived) == rhs, "coordinatewise independent RHS mismatch")
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-explicit-target-rhs-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_EXPLICIT_TARGET_RHS_REPLAY",
        "producer": {"path": str(receipt_path.relative_to(CAMPAIGN)), "sha256": file_hash(receipt_path)},
        "bound_inputs": {
            str(CSR.relative_to(CAMPAIGN)): file_hash(CSR),
            str(GAUGE.relative_to(CAMPAIGN)): file_hash(GAUGE),
        },
        "checks": {
            "rows": 85_651,
            "selected_columns": 35_881,
            "selected_nonzeros": 1_354_540,
            "raw_target_nonzero_rows": nonzero_raw_target,
            "support_mismatches": support_mismatches,
            "row_scale_mismatches": scale_mismatches,
            "rhs_mismatches": rhs_mismatches,
            "target_sha256": TARGET_SHA256,
            "independently_derived_rhs_sha256": hashlib.sha256(independently_derived).hexdigest(),
            "producer_rhs_sha256": file_hash(rhs_path),
        },
        "method": (
            "Rebuild the unscaled modular Macaulay block; derive each row scalar from the first selected "
            "coefficient shared with the promoted CSR; verify that scalar on every selected coefficient; "
            "then apply it to the independently rebuilt raw target coefficient."
        ),
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "producer_module_not_imported": True,
            "existing_multiplier_or_solution_not_read": True,
            "linbox_not_called": True,
            "no_elimination_or_solve": True,
            "no_mod181_squared": True,
        },
        "claim_boundary": (
            "This independent PASS certifies only row alignment, scaling, and coefficients of the explicit "
            "M*h3 right-hand side over GF(181). It does not prove membership or any characteristic-zero, "
            "colon, saturation, secant, nullcone, or HC4 statement."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(output), "sha256": file_hash(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
