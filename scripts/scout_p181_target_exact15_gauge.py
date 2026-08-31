#!/usr/bin/env -S sage -python
"""Measure target-height change under the deterministic exact-15 gauge."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path

import reconstruct_p181_sparse4_exact_rational as rr_base


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
MODULUS = P**18
COLUMNS = 35_881
SPARSE4 = CAMPAIGN / "artifacts/third-colon-p181-sparse4-exact-rational-replay-v1/rational_sparse4_pairs_row_major.json"
EXACT11 = CAMPAIGN / "artifacts/third-colon-p181-support18-exact11-rational-replay-v1/rational_exact11_pairs_row_major.json"
TARGET = CAMPAIGN / "artifacts/third-colon-p181-fixed-block-denominator-18digit-test-v1/X_mod_181_power_18.json"
RESIDUAL_INDICES = (43, 35, 46, 48, 95, 59, 56, 1, 58, 30, 74, 112, 57, 109, 47)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rational_matrix_modulus():
    left = json.loads(SPARSE4.read_text(encoding="utf-8"))
    right = json.loads(EXACT11.read_text(encoding="utf-8"))
    require(len(left) == len(right) == COLUMNS, "certificate row count drift")
    matrix = []
    for row in range(COLUMNS):
        pairs = left[row] + right[row]
        require(len(pairs) == len(RESIDUAL_INDICES), "certificate column count drift")
        modular_row = []
        for numerator, denominator in pairs:
            numerator = int(numerator)
            denominator = int(denominator)
            require(math.gcd(denominator, P) == 1, "nonunit syzygy denominator")
            modular_row.append(numerator % MODULUS * pow(denominator % MODULUS, -1, MODULUS) % MODULUS)
        matrix.append(modular_row)
    return matrix


def row_pivots(matrix, order):
    basis = []
    selected = []
    for row_index in order:
        vector = [value % P for value in matrix[row_index]]
        for pivot_column, basis_vector in basis:
            factor = vector[pivot_column]
            if factor:
                vector = [(value - factor * base_value) % P for value, base_value in zip(vector, basis_vector, strict=True)]
        pivot = next((column for column, value in enumerate(vector) if value), None)
        if pivot is None:
            continue
        inverse = pow(vector[pivot], -1, P)
        vector = [value * inverse % P for value in vector]
        for position, (old_pivot, old_vector) in enumerate(basis):
            factor = old_vector[pivot]
            if factor:
                basis[position] = (old_pivot, [(value - factor * new_value) % P for value, new_value in zip(old_vector, vector, strict=True)])
        basis.append((pivot, vector))
        basis.sort(key=lambda item: item[0])
        selected.append(row_index)
        if len(selected) == len(RESIDUAL_INDICES):
            break
    require(len(selected) == len(RESIDUAL_INDICES), "exact15 main-coordinate row rank below 15")
    return selected


def solve_unit_system(matrix, rhs):
    size = len(rhs)
    augmented = [[int(matrix[row][column]) % MODULUS for column in range(size)] + [int(rhs[row]) % MODULUS] for row in range(size)]
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column] % P), None)
        require(pivot is not None, "nonunit pivot in exact15 gauge solve")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        inverse = pow(augmented[column][column], -1, MODULUS)
        augmented[column] = [value * inverse % MODULUS for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [(value - factor * pivot_value) % MODULUS for value, pivot_value in zip(augmented[row], augmented[column], strict=True)]
    return [augmented[row][-1] for row in range(size)]


def census(values):
    pairs = [rr_base.rr(value, MODULUS) for value in values]
    unresolved = [index for index, pair in enumerate(pairs) if pair is None]
    resolved = [pair for pair in pairs if pair is not None]
    nonzero = [index for index, pair in enumerate(pairs) if pair is not None and pair[0] != 0]
    zeros = [index for index, pair in enumerate(pairs) if pair == (0, 1)]
    return pairs, unresolved, nonzero, zeros, {
        "coordinate_count": len(values),
        "unresolved_count": len(unresolved),
        "resolved_nonzero_count": len(nonzero),
        "resolved_zero_count": len(zeros),
        "maximum_absolute_numerator": max((abs(pair[0]) for pair in resolved), default=0),
        "maximum_denominator": max((pair[1] for pair in resolved), default=0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    started = time.perf_counter()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    target = [int(value) % MODULUS for value in json.loads(TARGET.read_text(encoding="utf-8"))]
    require(len(target) == COLUMNS, "target length drift")
    section = rational_matrix_modulus()
    baseline_pairs, unresolved, nonzero, zeros, baseline = census(target)
    order = unresolved + nonzero + zeros
    require(len(set(order)) == COLUMNS, "pivot candidate ordering drift")
    pivot_rows = row_pivots(section, order)
    pivot_matrix = [section[row] for row in pivot_rows]
    parameters = solve_unit_system(pivot_matrix, [(-target[row]) % MODULUS for row in pivot_rows])
    adjusted = [(target[row] + sum(section[row][column] * parameters[column] for column in range(len(parameters)))) % MODULUS for row in range(COLUMNS)]
    pivot_nonzeros = sum(adjusted[row] != 0 for row in pivot_rows)
    require(pivot_nonzeros == 0, "selected target pivots did not vanish")
    _pairs, _unresolved, _nonzero, _zeros, adjusted_main = census(adjusted)
    _parameter_pairs, _pu, _pn, _pz, adjusted_residual = census(parameters)
    adjusted_all = dict(adjusted_main)
    adjusted_all["coordinate_count"] += adjusted_residual["coordinate_count"]
    adjusted_all["unresolved_count"] += adjusted_residual["unresolved_count"]
    adjusted_all["resolved_nonzero_count"] += adjusted_residual["resolved_nonzero_count"]
    adjusted_all["resolved_zero_count"] += adjusted_residual["resolved_zero_count"]
    adjusted_all["maximum_absolute_numerator"] = max(adjusted_main["maximum_absolute_numerator"], adjusted_residual["maximum_absolute_numerator"])
    adjusted_all["maximum_denominator"] = max(adjusted_main["maximum_denominator"], adjusted_residual["maximum_denominator"])
    adjusted_path = output / "adjusted_main_residues_mod_181_power_18.json"
    parameters_path = output / "residual_parameters_mod_181_power_18.json"
    adjusted_path.write_text(json.dumps([str(value) for value in adjusted], separators=(",", ":")) + "\n", encoding="ascii")
    parameters_path.write_text(json.dumps([str(value) for value in parameters], separators=(",", ":")) + "\n", encoding="ascii")
    resources = {"wall_seconds": time.perf_counter() - started, "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}
    require(resources["wall_seconds"] < 120 and resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0, "scout resource gate failed")
    improvement = baseline["unresolved_count"] - adjusted_all["unresolved_count"]
    status = "PASS_FAVORABLE_P181_TARGET_EXACT15_GAUGE_SCOUT" if improvement > 0 else "PASS_NONIMPROVING_P181_TARGET_EXACT15_GAUGE_SCOUT"
    receipt = {
        "schema": "hc4.third-colon-p181-target-exact15-gauge-scout.v1",
        "status": status,
        "inputs": {"target_p18_sha256": digest(TARGET), "sparse4_pairs_sha256": digest(SPARSE4), "exact11_pairs_sha256": digest(EXACT11)},
        "selection": {"residual_local_indices": list(RESIDUAL_INDICES), "pivot_rows": pivot_rows, "candidate_order_counts": {"baseline_unresolved": len(unresolved), "baseline_resolved_nonzero": len(nonzero), "baseline_resolved_zero": len(zeros)}, "rule": "first rank-increasing rows over GF(181), unresolved then resolved-nonzero then zero"},
        "gauge": {"parameter_count": len(parameters), "selected_pivot_nonzero_count_after_adjustment": pivot_nonzeros, "parameter_residues": [str(value) for value in parameters]},
        "height_census": {"equal_height_bound": math.isqrt((MODULUS - 1) // 2), "baseline_main": baseline, "adjusted_main": adjusted_main, "adjusted_residual_parameters": adjusted_residual, "adjusted_full_35896": adjusted_all, "unresolved_count_improvement": improvement},
        "outputs": {path.name: {"sha256": digest(path), "bytes": path.stat().st_size} for path in (adjusted_path, parameters_path)},
        "resources": resources,
        "declarations": {"single_deterministic_gauge": True, "no_alternative_minor_search": True, "solver_not_executed": True, "exact_target_replay_not_attempted": True},
        "claim_boundary": "This scout measures target-height change under one deterministic exact15 gauge. It does not prove rational target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "gauge-scout.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": status, "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
