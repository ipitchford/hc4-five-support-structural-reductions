#!/usr/bin/env sage-python
"""Bounded LinBox rank benchmark for the frozen third-colon p=103 block.

This is intentionally separate from the proof-producing identity solver.  It
removes only the independently certified one-coordinate target-free incidence
component and compares the sparse ranks of A and [A|b].  Equal ranks are a
modular membership decision from LinBox's black-box rank routine, but do not
produce original-generator multipliers or a characteristic-zero identity.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import GF, matrix
from sage.env import SAGE_VERSION

from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    build_character_block,
)


CHARACTERISTIC = 103
ISOLATED_UNKNOWN = 2220
EXPECTED_ISOLATED_ROW_COUNT = 13


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_matrix(block: dict[str, object], augmented: bool):
    active_rows = []
    isolated_rows = []
    for equation_index, equation in enumerate(block["sparse_equations"]):
        if ISOLATED_UNKNOWN in equation:
            if set(equation) != {ISOLATED_UNKNOWN} or block["right_hand_side"][equation_index]:
                raise AssertionError("the certified isolated component changed")
            isolated_rows.append(equation_index)
            continue
        active_rows.append(equation_index)
    if len(isolated_rows) != EXPECTED_ISOLATED_ROW_COUNT:
        raise AssertionError("the isolated row count changed")

    column_map = {}
    for old in range(len(block["descriptors"])):
        if old != ISOLATED_UNKNOWN:
            column_map[old] = len(column_map)
    column_count = len(column_map) + int(augmented)
    entries = {}
    for new_row, old_row in enumerate(active_rows):
        for old_column, coefficient in block["sparse_equations"][old_row].items():
            entries[(new_row, column_map[old_column])] = coefficient
        if augmented:
            rhs = block["right_hand_side"][old_row] % CHARACTERISTIC
            if rhs:
                entries[(new_row, len(column_map))] = rhs
    result = matrix(
        GF(CHARACTERISTIC), len(active_rows), column_count, entries, sparse=True
    )
    metadata = {
        "row_count": len(active_rows),
        "column_count": len(column_map),
        "stored_nonzero_count": len(entries),
        "isolated_unknown": ISOLATED_UNKNOWN,
        "isolated_row_count": len(isolated_rows),
        "isolated_rows": isolated_rows,
    }
    del entries
    gc.collect()
    return result, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-third-colon-linbox-rank-p103.json"
        ),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    producer_path = (
        campaign
        / "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py"
    )
    structure_path = (
        campaign
        / "receipts/hsop-j2-secant-r10-third-colon-kernel-structure-two-prime.json"
    )

    # The historical p=103 baseline intentionally includes its two vanished
    # h2 coefficients.  Retaining that exact reduction is required for a fair
    # benchmark against the frozen 34,948-pivot receipt.
    block = build_character_block(
        campaign, CHARACTERISTIC, require_full_support=False
    )
    build_seconds = time.perf_counter() - started
    print(
        json.dumps(
            {
                "event": "block_built",
                "seconds": build_seconds,
                "rows": len(block["sparse_equations"]),
                "columns": len(block["descriptors"]),
                "nonzeros": block["nonzero_count"],
            },
            sort_keys=True,
        ),
        flush=True,
    )

    coefficient, coefficient_metadata = build_matrix(block, augmented=False)
    coefficient_build_seconds = time.perf_counter() - started - build_seconds
    print(
        json.dumps(
            {
                "event": "coefficient_matrix_built",
                "seconds": coefficient_build_seconds,
                **coefficient_metadata,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    rank_started = time.perf_counter()
    coefficient_rank = int(coefficient.rank(algorithm="linbox"))
    coefficient_rank_seconds = time.perf_counter() - rank_started
    print(
        json.dumps(
            {
                "event": "coefficient_rank_complete",
                "rank": coefficient_rank,
                "seconds": coefficient_rank_seconds,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    del coefficient
    gc.collect()

    augmented, augmented_metadata = build_matrix(block, augmented=True)
    augmented_build_seconds = (
        time.perf_counter()
        - started
        - build_seconds
        - coefficient_build_seconds
        - coefficient_rank_seconds
    )
    del block
    gc.collect()
    print(
        json.dumps(
            {
                "event": "augmented_matrix_built",
                "seconds": augmented_build_seconds,
                **augmented_metadata,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    rank_started = time.perf_counter()
    augmented_rank = int(augmented.rank(algorithm="linbox"))
    augmented_rank_seconds = time.perf_counter() - rank_started
    print(
        json.dumps(
            {
                "event": "augmented_rank_complete",
                "rank": augmented_rank,
                "seconds": augmented_rank_seconds,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    consistent = coefficient_rank == augmented_rank
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-linbox-rank-benchmark.v1",
        "status": (
            "PASS_LINBOX_MODULAR_MEMBERSHIP_RANK_EQUALITY"
            if consistent
            else "PASS_LINBOX_MODULAR_NONMEMBERSHIP_RANK_JUMP"
        ),
        "assurance": (
            "exact finite-field input with LinBox black-box rank decisions; no explicit multiplier vector"
        ),
        "characteristic": CHARACTERISTIC,
        "algorithm": "Sage Matrix_modn_sparse.rank(algorithm='linbox')",
        "sage_version": SAGE_VERSION,
        "component_pruning": coefficient_metadata,
        "coefficient_rank": coefficient_rank,
        "augmented_rank": augmented_rank,
        "ranks_equal": consistent,
        "nullity_after_isolated_coordinate_removal": (
            coefficient_metadata["column_count"] - coefficient_rank
        ),
        "timings": {
            "problem_block_build_seconds": build_seconds,
            "coefficient_matrix_build_seconds": coefficient_build_seconds,
            "coefficient_rank_seconds": coefficient_rank_seconds,
            "augmented_matrix_build_seconds": augmented_build_seconds,
            "augmented_rank_seconds": augmented_rank_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "inputs": {
            "producer_path": str(producer_path.relative_to(campaign)),
            "producer_sha256": sha256(producer_path),
            "structure_receipt_path": str(structure_path.relative_to(campaign)),
            "structure_receipt_sha256": sha256(structure_path),
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
        },
        "claim_boundary": (
            "Equal ranks decide only that the displayed p=103 target lies in the "
            "displayed p=103 Macaulay image under LinBox's rank algorithm. This is "
            "not an explicit multiplier certificate, a QQ identity, a colon or "
            "saturation computation, secant closure, or HC4."
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
