#!/usr/bin/env sage-python
"""Construct a lower-height modular gauge by swapping the p181 dense core.

Replay the frozen 35,300 sparse pivots from the portable p181 gauge, rebuild
the exact 5,417 x 2,316 dense residual, and exchange all 581 old dense pivots
with a deterministic full-rank set of 581 old dense-free columns.  Acceptance
requires an exact replay of the original 85,651-row finite-field system.

This script proves only a new modular representation of the same identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import GF, Matrix, vector

from certify_j2_secant_r10_colon_identity_sparse_macaulay import (
    sparse_eliminate,
    verify_sparse_system,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    CERTIFICATE_SCHEMA,
    build_character_block,
    canonical_hash,
)
from scout_decimic_nullcone_hsop import digest


CHARACTERISTIC = 181
TOTAL_PIVOT_COUNT = 35881
SPARSE_PREFIX_COUNT = 35300
DENSE_PIVOT_COUNT = 581
EXPECTED_EQUATION_COUNT = 85651
EXPECTED_UNKNOWN_COUNT = 38048
EXPECTED_RETAINED_ROW_COUNT = 50340
EXPECTED_RETAINED_ZERO_ROW_COUNT = 44923
EXPECTED_ACTIVE_ROW_COUNT = 5417
EXPECTED_ACTIVE_UNKNOWN_COUNT = 2316
EXPECTED_DENSE_FREE_COUNT = 1735
EXPECTED_GLOBAL_FREE_COUNT = 2167


def file_sha256(path: Path) -> str:
    digest_value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest_value.update(chunk)
    return digest_value.hexdigest()


def validate_source(
    source_path: Path,
    receipt_path: Path,
    block: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, str]]:
    source = json.loads(source_path.read_text(encoding="ascii"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected = {
        "row_descriptor_sha256": canonical_hash(block["descriptors"]),
        "monomial_stream_sha256": canonical_hash(block["monomials"]),
        "generator_stream_sha256": digest(tuple(block["generators"])),
        "target_sha256": digest((block["target_expression"],)),
    }
    if source.get("schema") != CERTIFICATE_SCHEMA:
        raise ValueError("source artifact schema changed")
    if int(source.get("characteristic", -1)) != CHARACTERISTIC:
        raise ValueError("source artifact is not the frozen p181 gauge")
    for key, value in expected.items():
        if source.get(key) != value:
            raise ValueError(f"source {key} changed")
    if source.get("variable_names") != [str(item) for item in block["variables"]]:
        raise ValueError("source variable order changed")
    if source.get("generator_degrees") != block["generator_degrees"]:
        raise ValueError("source generator degrees changed")
    if source.get("multiplier_degrees") != block["multiplier_degrees"]:
        raise ValueError("source multiplier degrees changed")

    pivots = list(map(int, source.get("pivot_unknown_indices", [])))
    free = list(map(int, source.get("free_unknown_indices", [])))
    coordinate_vector = list(map(int, source.get("coordinate_vector", [])))
    universe = set(range(EXPECTED_UNKNOWN_COUNT))
    if (
        len(pivots) != TOTAL_PIVOT_COUNT
        or len(set(pivots)) != TOTAL_PIVOT_COUNT
        or len(free) != EXPECTED_GLOBAL_FREE_COUNT
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != universe
        or source.get("pivot_unknown_indices_sha256") != canonical_hash(pivots)
        or source.get("free_unknown_indices_sha256") != canonical_hash(free)
        or len(coordinate_vector) != EXPECTED_UNKNOWN_COUNT
        or source.get("coordinate_vector_sha256")
        != canonical_hash(coordinate_vector)
    ):
        raise ValueError("source pivot/free/vector profile changed")
    source_sha = file_sha256(source_path)
    certificate_record = receipt.get("certificate") or {}
    replay = receipt.get("same_process_sparse_replay") or {}
    if (
        receipt.get("status") != "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
        or certificate_record.get("sha256") != source_sha
        or certificate_record.get("byte_count") != source_path.stat().st_size
        or replay.get("identity_zero") is not True
        or int(replay.get("mismatch_count", -1)) != 0
    ):
        raise ValueError("source receipt is not an exact passing p181 replay")
    return source, receipt, expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--prefix-timeout", type=float, default=600.0)
    parser.add_argument("--certificate-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not 60 <= arguments.prefix_timeout <= 900:
        parser.error("--prefix-timeout must lie between 60 and 900 seconds")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    source_path = arguments.source.resolve()
    receipt_path = arguments.source_receipt.resolve()
    certificate_output = arguments.certificate_output.resolve()
    output = arguments.output.resolve()

    build_started = time.perf_counter()
    block = build_character_block(campaign, CHARACTERISTIC)
    build_seconds = time.perf_counter() - build_started
    if (
        len(block["sparse_equations"]) != EXPECTED_EQUATION_COUNT
        or len(block["descriptors"]) != EXPECTED_UNKNOWN_COUNT
    ):
        raise AssertionError("frozen third-colon dimensions changed")
    source, source_receipt, expected_hashes = validate_source(
        source_path, receipt_path, block
    )
    old_pivots = list(map(int, source["pivot_unknown_indices"]))
    old_free = list(map(int, source["free_unknown_indices"]))
    sparse_prefix = old_pivots[:SPARSE_PREFIX_COUNT]
    old_dense_pivots = old_pivots[SPARSE_PREFIX_COUNT:]
    if len(old_dense_pivots) != DENSE_PIVOT_COUNT:
        raise AssertionError("frozen dense-pivot suffix changed")

    pristine_equations = [dict(item) for item in block["sparse_equations"]]
    pristine_rhs = list(block["right_hand_side"])
    prefix_started = time.perf_counter()
    prefix = sparse_eliminate(
        block["sparse_equations"],
        block["right_hand_side"],
        EXPECTED_UNKNOWN_COUNT,
        CHARACTERISTIC,
        time.perf_counter() + arguments.prefix_timeout,
        prescribed_pivots=sparse_prefix,
    )
    prefix_seconds = time.perf_counter() - prefix_started
    prefix_terminal = prefix.get("fixed_gauge_failure") or {}
    if (
        prefix.get("timed_out") is not False
        or int(prefix.get("completed_prescribed_pivots", -1))
        != SPARSE_PREFIX_COUNT
        or int(prefix.get("pivot_count", -1)) != SPARSE_PREFIX_COUNT
        or [int(item[0]) for item in prefix["pivot_records"]] != sparse_prefix
        or prefix.get("inconsistent_equation") is not None
        or prefix.get("completed") is not False
        or prefix.get("consistent") is not False
        or prefix_terminal.get("prescribed_position") != SPARSE_PREFIX_COUNT
        or prefix_terminal.get("reason")
        != "nonzero coefficient row remains after all prescribed pivots"
        or not isinstance(prefix_terminal.get("equation_index"), int)
        or int(prefix_terminal.get("remaining_term_count", 0)) <= 0
    ):
        raise AssertionError("frozen 35,300-pivot prefix did not replay")

    retained_rows = [
        index
        for index, equation in enumerate(block["sparse_equations"])
        if equation is not None
    ]
    retained_empty_rows = [
        index
        for index, equation in enumerate(block["sparse_equations"])
        if equation is not None and not equation
    ]
    if any(
        block["right_hand_side"][index] % CHARACTERISTIC
        for index in retained_empty_rows
    ):
        raise AssertionError("prefix replay retained an inconsistent empty row")
    active_rows = [
        (index, equation)
        for index, equation in enumerate(block["sparse_equations"])
        if equation
    ]
    active_unknowns = sorted(
        {
            unknown
            for _index, equation in active_rows
            for unknown in equation
        }
    )
    if (
        len(retained_rows) != EXPECTED_RETAINED_ROW_COUNT
        or len(retained_empty_rows) != EXPECTED_RETAINED_ZERO_ROW_COUNT
        or len(active_rows) != EXPECTED_ACTIVE_ROW_COUNT
        or len(retained_empty_rows) + len(active_rows) != len(retained_rows)
        or len(active_unknowns) != EXPECTED_ACTIVE_UNKNOWN_COUNT
    ):
        raise AssertionError(
            "frozen dense residual changed: "
            f"retained={len(retained_rows)}, zero={len(retained_empty_rows)}, "
            f"rows={len(active_rows)}, unknowns={len(active_unknowns)}"
        )

    field = GF(CHARACTERISTIC)
    local_column = {unknown: index for index, unknown in enumerate(active_unknowns)}
    dense_started = time.perf_counter()
    augmented = Matrix(
        field,
        EXPECTED_ACTIVE_ROW_COUNT,
        EXPECTED_ACTIVE_UNKNOWN_COUNT + 1,
        sparse=False,
    )
    row_build_started = time.perf_counter()
    for local_row, (source_row, equation) in enumerate(active_rows):
        dense_row = [0] * (EXPECTED_ACTIVE_UNKNOWN_COUNT + 1)
        for unknown, coefficient in equation.items():
            dense_row[local_column[unknown]] = coefficient
        dense_row[-1] = block["right_hand_side"][source_row]
        augmented.set_row(local_row, dense_row)
    row_build_seconds = time.perf_counter() - row_build_started
    echelon_started = time.perf_counter()
    augmented.echelonize()
    echelon_seconds = time.perf_counter() - echelon_started
    rhs_column = EXPECTED_ACTIVE_UNKNOWN_COUNT
    augmented_pivots = tuple(map(int, augmented.pivots()))
    if rhs_column in augmented_pivots:
        raise AssertionError("dense residual is inconsistent at p181")
    dense_pivot_columns = list(augmented_pivots)
    dense_pivot_unknowns = [active_unknowns[index] for index in dense_pivot_columns]
    if (
        len(dense_pivot_unknowns) != DENSE_PIVOT_COUNT
        or dense_pivot_unknowns != old_dense_pivots
    ):
        raise AssertionError("rebuilt dense pivot suffix changed")
    if any(
        not augmented.row(row).is_zero()
        for row in range(DENSE_PIVOT_COUNT, EXPECTED_ACTIVE_ROW_COUNT)
    ):
        raise AssertionError("post-rank dense residual contains a nonzero row")
    dense_free_columns = [
        index
        for index in range(EXPECTED_ACTIVE_UNKNOWN_COUNT)
        if index not in set(dense_pivot_columns)
    ]
    dense_free_unknowns = [active_unknowns[index] for index in dense_free_columns]
    if (
        len(dense_free_unknowns) != EXPECTED_DENSE_FREE_COUNT
        or set(dense_free_unknowns) != set(old_free) & set(active_unknowns)
    ):
        raise AssertionError("rebuilt dense-free profile changed")

    tail = Matrix(
        field,
        DENSE_PIVOT_COUNT,
        EXPECTED_DENSE_FREE_COUNT,
        lambda row, column: augmented[row, dense_free_columns[column]],
    )
    dense_rhs = vector(
        field,
        [augmented[row, rhs_column] for row in range(DENSE_PIVOT_COUNT)],
    )
    tail_rank_started = time.perf_counter()
    tail_pivot_columns = list(map(int, tail.pivots()))
    tail_rank_seconds = time.perf_counter() - tail_rank_started
    if len(tail_pivot_columns) != DENSE_PIVOT_COUNT:
        raise AssertionError(
            f"dense tail rank is {len(tail_pivot_columns)}, expected 581"
        )
    selected_unknowns = [dense_free_unknowns[index] for index in tail_pivot_columns]
    selected_matrix = tail.matrix_from_columns(tail_pivot_columns)
    selected_determinant = int(selected_matrix.det())
    if selected_determinant == 0:
        raise AssertionError("selected dense-tail basis is singular")
    selected_solution = selected_matrix.solve_right(dense_rhs)
    selected_local_position = {
        column: index for index, column in enumerate(tail_pivot_columns)
    }
    if tail * vector(
        field,
        [
            selected_solution[selected_local_position[index]]
            if index in selected_local_position
            else 0
            for index in range(EXPECTED_DENSE_FREE_COUNT)
        ],
    ) != dense_rhs:
        raise AssertionError("selected dense-free solution failed the tail system")
    dense_seconds = time.perf_counter() - dense_started

    values = [0] * EXPECTED_UNKNOWN_COUNT
    for unknown, coefficient in zip(selected_unknowns, selected_solution, strict=True):
        values[unknown] = int(coefficient)
    sparse_records = prefix["pivot_records"]
    for pivot_unknown, constant, record_tail in reversed(sparse_records):
        values[pivot_unknown] = (
            int(constant)
            + sum(
                int(coefficient) * values[int(unknown)]
                for unknown, coefficient in record_tail
            )
        ) % CHARACTERISTIC

    old_dense_set = set(old_dense_pivots)
    selected_set = set(selected_unknowns)
    old_free_set = set(old_free)
    if (
        selected_set - old_free_set
        or any(values[index] for index in old_dense_pivots)
        or any(values[index] for index in old_free_set - selected_set)
    ):
        raise AssertionError("dense-pivot swap did not impose the declared gauge")
    new_pivots = sparse_prefix + selected_unknowns
    new_free = sorted(old_dense_set | (old_free_set - selected_set))
    if (
        len(new_pivots) != TOTAL_PIVOT_COUNT
        or len(set(new_pivots)) != TOTAL_PIVOT_COUNT
        or len(new_free) != EXPECTED_GLOBAL_FREE_COUNT
        or set(new_pivots) & set(new_free)
        or set(new_pivots) | set(new_free) != set(range(EXPECTED_UNKNOWN_COUNT))
        or any(values[index] for index in new_free)
    ):
        raise AssertionError("new pivot/free profile is not a zero-free gauge")

    replay = verify_sparse_system(
        pristine_equations,
        pristine_rhs,
        values,
        CHARACTERISTIC,
    )
    if (
        replay.get("identity_zero") is not True
        or int(replay.get("mismatch_count", -1)) != 0
    ):
        raise AssertionError("new p181 gauge failed pristine exact replay")

    support = []
    for unknown_index, coefficient in enumerate(values):
        if coefficient:
            generator_index, multiplier = block["descriptors"][unknown_index]
            support.append(
                {
                    "unknown_index": unknown_index,
                    "generator_position": generator_index,
                    "multiplier_exponents": list(multiplier),
                    "coefficient": int(coefficient),
                }
            )
    pivot_hash = canonical_hash(new_pivots)
    free_hash = canonical_hash(new_free)
    vector_hash = canonical_hash(values)
    source_sha = file_sha256(source_path)
    shared_solver_path = (
        campaign / "scripts/certify_j2_secant_r10_colon_identity_sparse_macaulay.py"
    )
    producer_path = (
        campaign / "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py"
    )
    second_loader_path = (
        campaign
        / "scripts/certify_j2_secant_r10_second_colon_identity_sparse_macaulay.py"
    )
    certificate = {
        "schema": CERTIFICATE_SCHEMA,
        "characteristic": CHARACTERISTIC,
        "variable_names": [str(item) for item in block["variables"]],
        "character_modulus": 12,
        "character_weights": list(source["character_weights"]),
        "target_character_weight": block["target_weight"],
        "generator_count": len(block["generators"]),
        "normal_cubic_generator_count": len(block["normal_equations"]),
        "generator_degrees": block["generator_degrees"],
        "multiplier_degrees": block["multiplier_degrees"],
        "generator_character_weights": block["generator_weights"],
        "generator_stream_sha256": expected_hashes["generator_stream_sha256"],
        "target_sha256": expected_hashes["target_sha256"],
        "first_quartic": block["first_metadata"],
        "second_quartic": block["second_metadata"],
        "third_quartic": block["third_metadata"],
        "row_descriptor_sha256": expected_hashes["row_descriptor_sha256"],
        "monomial_stream_sha256": expected_hashes["monomial_stream_sha256"],
        "deterministic_gauge": (
            "all 581 old dense pivots and every unselected old free coordinate "
            "set to zero; 581 lexicographic pivot columns of the dense tail promoted"
        ),
        "pivot_unknown_indices": new_pivots,
        "pivot_unknown_indices_sha256": pivot_hash,
        "free_unknown_indices": new_free,
        "free_unknown_indices_sha256": free_hash,
        # This constructor changes the free-coordinate set.  Keep gauge_source
        # null so downstream consumers do not mistake the construction input
        # for a preserved-free-set transfer source.
        "gauge_source": None,
        "construction_source": {
            "path": str(source_path),
            "sha256": source_sha,
            "receipt_path": str(receipt_path),
            "receipt_sha256": file_sha256(receipt_path),
            "characteristic": CHARACTERISTIC,
            "pivot_unknown_set_sha256": canonical_hash(sorted(old_pivots)),
            "free_unknown_indices_sha256": canonical_hash(old_free),
            "pivot_count": len(old_pivots),
            "free_unknown_count": len(old_free),
            "removed_free_column_nonzeros": 0,
            "policy": "exact 581-dense-pivot exchange after frozen sparse-prefix replay",
        },
        "coordinate_vector": values,
        "coordinate_vector_sha256": vector_hash,
        "solution_support": support,
        "source_dependencies": {
            str(script_path.relative_to(campaign)): file_sha256(script_path),
            str(producer_path.relative_to(campaign)): file_sha256(producer_path),
            str(shared_solver_path.relative_to(campaign)): file_sha256(shared_solver_path),
            str(second_loader_path.relative_to(campaign)): file_sha256(second_loader_path),
        },
        "claim_boundary": (
            "Exact identity M*h3 in (F_1,...,F_17,h,h2) over GF(181) only; "
            "not a QQ identity, colon, saturation, secant closure, or HC4 certificate."
        ),
    }
    certificate_text = json.dumps(certificate, indent=2, sort_keys=True) + "\n"
    certificate_output.parent.mkdir(parents=True, exist_ok=True)
    certificate_output.write_text(certificate_text, encoding="ascii")
    certificate_record = {
        "path": str(certificate_output),
        "sha256": hashlib.sha256(certificate_text.encode("ascii")).hexdigest(),
        "byte_count": len(certificate_text.encode("ascii")),
    }

    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.third-colon-dense-pivot-swap-constructor.v1",
        "status": "PASS_EXACT_MODULAR_THIRD_COLON_DENSE_PIVOT_SWAP",
        "assurance": "exact finite-field polynomial identity in a redesigned gauge",
        "characteristic": CHARACTERISTIC,
        "source": {
            "artifact": str(source_path),
            "artifact_sha256": source_sha,
            "receipt": str(receipt_path),
            "receipt_sha256": file_sha256(receipt_path),
            "receipt_status": source_receipt["status"],
        },
        "frozen_dimensions": {
            "equation_count": EXPECTED_EQUATION_COUNT,
            "unknown_count": EXPECTED_UNKNOWN_COUNT,
            "total_pivot_count": TOTAL_PIVOT_COUNT,
            "global_free_count": EXPECTED_GLOBAL_FREE_COUNT,
            "sparse_prefix_count": SPARSE_PREFIX_COUNT,
            "sparse_prefix_sha256": canonical_hash(sparse_prefix),
            "sparse_prefix_terminal_marker": prefix_terminal,
            "retained_row_count": len(retained_rows),
            "retained_zero_row_count": len(retained_empty_rows),
            "retained_zero_row_indices_sha256": canonical_hash(retained_empty_rows),
            "dense_residual_rows": EXPECTED_ACTIVE_ROW_COUNT,
            "dense_residual_unknowns": EXPECTED_ACTIVE_UNKNOWN_COUNT,
            "old_dense_pivot_count": DENSE_PIVOT_COUNT,
            "old_dense_pivot_indices_sha256": canonical_hash(old_dense_pivots),
            "old_dense_active_free_count": EXPECTED_DENSE_FREE_COUNT,
            "old_inactive_free_count": EXPECTED_GLOBAL_FREE_COUNT
            - EXPECTED_DENSE_FREE_COUNT,
        },
        "dense_swap": {
            "tail_shape": [DENSE_PIVOT_COUNT, EXPECTED_DENSE_FREE_COUNT],
            "tail_rank": len(tail_pivot_columns),
            "tail_matrix_sha256": canonical_hash(
                [[int(entry) for entry in row] for row in tail.rows()]
            ),
            "dense_rhs_sha256": canonical_hash([int(entry) for entry in dense_rhs]),
            "selected_old_free_count": len(selected_unknowns),
            "selected_old_free_local_columns": tail_pivot_columns,
            "selected_old_free_local_columns_sha256": canonical_hash(
                tail_pivot_columns
            ),
            "selected_old_free_indices": selected_unknowns,
            "selected_old_free_indices_sha256": canonical_hash(selected_unknowns),
            "selected_basis_determinant_mod_181": selected_determinant,
            "selected_basis_rank": DENSE_PIVOT_COUNT,
            "selected_old_free_nonzero_value_count": sum(
                bool(values[index]) for index in selected_unknowns
            ),
            "selected_old_free_zero_value_count": sum(
                not values[index] for index in selected_unknowns
            ),
            "zeroed_old_dense_pivot_count": len(old_dense_pivots),
            "zeroed_old_dense_pivot_indices_sha256": canonical_hash(old_dense_pivots),
            "new_pivot_unknown_indices_sha256": pivot_hash,
            "new_free_unknown_indices_sha256": free_hash,
            "new_coordinate_vector_sha256": vector_hash,
        },
        "replay": replay,
        "solution_support_count": len(support),
        "certificate": certificate_record,
        "timings": {
            "block_build_seconds": build_seconds,
            "sparse_prefix_replay_seconds": prefix_seconds,
            "dense_row_build_seconds": row_build_seconds,
            "dense_echelon_seconds": echelon_seconds,
            "tail_rank_seconds": tail_rank_seconds,
            "dense_total_seconds": dense_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "source_sha256": {
            str(script_path.relative_to(campaign)): file_sha256(script_path),
            str(producer_path.relative_to(campaign)): file_sha256(producer_path),
            str(shared_solver_path.relative_to(campaign)): file_sha256(shared_solver_path),
            str(second_loader_path.relative_to(campaign)): file_sha256(second_loader_path),
        },
        "claim_boundary": (
            "A PASS proves only the displayed identity over GF(181) in the new "
            "gauge. Transfer primes and exact QQ convolution remain separate gates."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "certificate": certificate_record,
                "dense_swap": result["dense_swap"],
                "replay": replay,
                "timings": result["timings"],
                "resources": result["resources"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
