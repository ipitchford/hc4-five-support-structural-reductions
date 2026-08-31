#!/usr/bin/env -S sage -python
"""Assemble and verify the canonical residual-114 modular kernel section."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import struct
import time
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from sage.all import GF, Matrix


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
PIVOT_COLUMNS = 35_881
GLOBAL_COLUMNS = 38_048
RHS_COLUMNS = 114
NONZEROS = 1_354_540
CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
QUOTIENT = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
EXACT_CHART = CAMPAIGN / "artifacts/third-colon-residual-114-p181-72digit-chart-v1/rational_chart.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_csr():
    payload = CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, PIVOT_COLUMNS, NONZEROS), "CSR dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy()
    cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy()
    cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype=np.uint8, count=nonzeros, offset=cursor).astype(np.int64)
    cursor += nonzeros
    require(cursor == len(payload), "CSR trailing bytes")
    return csr_matrix((values, indices, offsets), shape=(ROWS, PIVOT_COLUMNS), dtype=np.int64)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    artifact = arguments.artifact_dir if arguments.artifact_dir.is_absolute() else CAMPAIGN / arguments.artifact_dir
    output = artifact / "section.json"
    require(not output.exists(), "section verification output exists")
    rhs_receipt = json.loads((artifact / "rhs/rhs.json").read_text(encoding="utf-8"))
    require(rhs_receipt.get("status") == "PASS_SOURCE_CLEAN_P181_CANONICAL_RESIDUAL_114_RHS", "RHS builder status drift")
    driver_lines = [line for line in (artifact / "driver.stdout.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    require(len(driver_lines) == 1, "driver stdout cardinality drift")
    driver = json.loads(driver_lines[0])
    require(driver.get("status") == "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION", "driver PASS drift")
    require(driver.get("mode") == "actual_114_rhs" and driver.get("augmented_nullity") == RHS_COLUMNS, "driver dimensions drift")
    rhs_payload = (artifact / "rhs/minus_A_S_row_major.u8").read_bytes()
    solution_payload = (artifact / "pivot_section_row_major.u8").read_bytes()
    require(len(rhs_payload) == ROWS * RHS_COLUMNS, "RHS byte length drift")
    require(len(solution_payload) == PIVOT_COLUMNS * RHS_COLUMNS, "solution byte length drift")
    rhs = np.frombuffer(rhs_payload, dtype=np.uint8).reshape(ROWS, RHS_COLUMNS).astype(np.int64)
    solution = np.frombuffer(solution_payload, dtype=np.uint8).reshape(PIVOT_COLUMNS, RHS_COLUMNS).astype(np.int64)
    coefficient = read_csr()
    product = coefficient @ solution
    replay_mismatches = int(np.count_nonzero((product - rhs) % P))
    require(replay_mismatches == 0, "independent sparse 114-RHS replay failed")

    pivots = [item[0] for item in struct.iter_unpack("<I", GAUGE.read_bytes())]
    quotient = json.loads(QUOTIENT.read_text(encoding="utf-8"))
    free = list(map(int, quotient["ordered_free_absolute_coordinates"]))
    koszul_pivots = list(map(int, quotient["ordered_pivot_absolute_coordinates_discovery_order"]))
    complement = list(map(int, quotient["ordered_complement_absolute_coordinates"]))
    require(len(pivots) == PIVOT_COLUMNS and len(free) == 2_167 and len(koszul_pivots) == 2_053 and len(complement) == RHS_COLUMNS, "coordinate dimensions drift")
    require(sorted(pivots + free) == list(range(GLOBAL_COLUMNS)), "main gauge coverage drift")
    full = np.zeros((GLOBAL_COLUMNS, RHS_COLUMNS), dtype=np.uint8)
    full[np.asarray(pivots, dtype=np.int64), :] = solution.astype(np.uint8)
    for column, absolute in enumerate(complement):
        full[absolute, column] = 1
    require(int(np.count_nonzero(full[np.asarray(koszul_pivots, dtype=np.int64), :])) == 0, "section is nonzero on Koszul pivots")
    complement_block = full[np.asarray(complement, dtype=np.int64), :]
    require(np.array_equal(complement_block, np.eye(RHS_COLUMNS, dtype=np.uint8)), "section complement is not identity")
    other_free = sorted(set(free) - set(koszul_pivots) - set(complement))
    require(not other_free, "free-coordinate partition drift")

    exact_chart = json.loads(EXACT_CHART.read_text(encoding="utf-8"))
    denominator = int(exact_chart["global_denominator"])
    require(denominator % P != 0, "exact chart denominator nonunit at p181")
    inverse = pow(denominator % P, -1, P)
    numerator_matrix = [[int(value) for value in row] for row in exact_chart["integer_numerator_matrix_row_major"]]
    transition = np.asarray([[value % P * inverse % P for value in row] for row in numerator_matrix], dtype=np.int64)
    pivot_free_block = full[np.asarray(koszul_pivots, dtype=np.int64), :].astype(np.int64)
    quotient_coordinates = (complement_block.T.astype(np.int64) - pivot_free_block.T @ transition) % P
    require(np.array_equal(quotient_coordinates, np.eye(RHS_COLUMNS, dtype=np.int64)), "quotient coordinates are not identity")

    b_records = quotient["B_sparse_integer_rows"]
    b_entries = {}
    for row, records in enumerate(b_records):
        for column, value in records:
            residue = int(value) % P
            if residue:
                b_entries[(row, int(column))] = residue
    b_matrix = Matrix(GF(P), 2_053, 2_053, b_entries, sparse=True)
    b_rank = int(b_matrix.rank())
    require(b_rank == 2_053, "independent Koszul pivot block rank drift")
    combined_free_rank = b_rank + RHS_COLUMNS
    require(combined_free_rank == 2_167, "combined free restriction rank drift")
    full_path = artifact / "full_residual_section_row_major.u8"
    full_path.write_bytes(full.tobytes(order="C"))
    support_counts = np.count_nonzero(full, axis=0).astype(int).tolist()
    receipt = {
        "schema": "hc4.third-colon-p181-canonical-residual-114-section.v1",
        "status": "PASS_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION",
        "inputs": {"csr_sha256": file_hash(CSR), "gauge_sha256": file_hash(GAUGE), "quotient_chart_sha256": file_hash(QUOTIENT), "exact_rational_chart_sha256": file_hash(EXACT_CHART), "rhs_receipt_sha256": file_hash(artifact / "rhs/rhs.json"), "rhs_sha256": file_hash(artifact / "rhs/minus_A_S_row_major.u8"), "driver_stdout_sha256": file_hash(artifact / "driver.stdout.txt")},
        "driver": driver,
        "dimensions": {"main_coefficient_matrix": [ROWS, PIVOT_COLUMNS], "pivot_section": [PIVOT_COLUMNS, RHS_COLUMNS], "full_section": [GLOBAL_COLUMNS, RHS_COLUMNS]},
        "coefficient_replay": {"scalar_comparisons": ROWS * RHS_COLUMNS, "mismatch_count": replay_mismatches},
        "quotient_replay": {"quotient_matrix_shape": [RHS_COLUMNS, RHS_COLUMNS], "identity_mismatch_count": int(np.count_nonzero(quotient_coordinates - np.eye(RHS_COLUMNS, dtype=np.int64))), "transition_mod181_sha256": canonical_hash(transition.astype(int).tolist())},
        "kernel_completion": {"Koszul_rank_on_P": b_rank, "residual_section_rank_on_S": RHS_COLUMNS, "combined_free_restriction_rank": combined_free_rank, "main_matrix_rank_mod181": PIVOT_COLUMNS, "deduced_full_kernel_dimension_mod181": 2_167},
        "section": {"pivot_path": "pivot_section_row_major.u8", "pivot_sha256": file_hash(artifact / "pivot_section_row_major.u8"), "full_path": full_path.name, "full_sha256": file_hash(full_path), "full_nonzero_count": int(np.count_nonzero(full)), "column_support_counts": support_counts},
        "resources": {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "declarations": {"target_multiplier_not_read": True, "legacy_residual_kernel_not_read": True, "quotient_section_fixed_to_identity": True, "no_QQ_lift": True},
        "claim_boundary": "This PASS proves only the canonical residual-114 section and full encoded kernel decomposition over GF(181). It does not lift residual syzygies to QQ, prove QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(output), "sha256": file_hash(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
