#!/usr/bin/env -S sage -python
"""Build and advance the frozen 16-column fourth-colon kernel experiment.

The source columns are scaled by the *existing* primitive B-row multiplier.
They never participate in a new content calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import struct
import time
from array import array
from fractions import Fraction
from pathlib import Path

import sympy as sp

import build_p173_fourth_colon_integral_lift_system as base


P = 173
P2 = P * P
RHS_COUNT = 16
SELECTED_GLOBAL = (46, 47, 57, 66, 68, 102, 155, 547,
                   763, 965, 966, 1261, 1269, 1499, 1699, 1711)
SYSTEM_DIR = base.CAMPAIGN / "artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
INTEGRAL_MATRIX = SYSTEM_DIR / "A_Z_b_Z_fixed_gauge_p173.i64csr"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def modular_fraction(value: Fraction, modulus: int) -> int:
    denominator = value.denominator % modulus
    base.require(math.gcd(denominator, P) == 1, "selected coefficient has a p-adic pole")
    return value.numerator * pow(denominator, -1, modulus) % modulus


def primitive_scale(entries: list[tuple[int, tuple[int, int]]], rhs: tuple[int, int]) -> Fraction:
    denominator = rhs[1]
    for _column, pair in entries:
        denominator = math.lcm(denominator, pair[1])
    integer_entries = [(column, pair[0] * (denominator // pair[1])) for column, pair in entries]
    integer_rhs = rhs[0] * (denominator // rhs[1])
    contents = [abs(value) for _column, value in integer_entries if value]
    if integer_rhs:
        contents.append(abs(integer_rhs))
    base.require(bool(contents), "unexpected empty primitive row")
    content = math.gcd(*contents)
    first = next((value // content for _column, value in integer_entries if value), integer_rhs // content)
    sign = -1 if first < 0 else 1
    return Fraction(sign * denominator, content)


def load_integral() -> tuple[list[int], list[int], list[int], list[int]]:
    with INTEGRAL_MATRIX.open("rb") as handle:
        base.require(handle.read(8) == b"HC4ZI173", "integral matrix magic drift")
        rows, columns, nonzeros = struct.unpack("<QQQ", handle.read(24))
        base.require((rows, columns, nonzeros) == (base.ROWS, base.LOCAL_COLUMNS, 1_487_624),
                     "integral matrix dimensions drift")
        offsets_raw = handle.read(8 * (rows + 1))
        columns_raw = handle.read(4 * nonzeros)
        values_raw = handle.read(8 * nonzeros)
        rhs_raw = handle.read(8 * rows)
        base.require(handle.read() == b"", "integral matrix trailing bytes")
    offsets = list(struct.unpack(f"<{rows + 1}Q", offsets_raw))
    column_indices = list(struct.unpack(f"<{nonzeros}I", columns_raw))
    values = list(struct.unpack(f"<{nonzeros}q", values_raw))
    rhs = list(struct.unpack(f"<{rows}q", rhs_raw))
    return offsets, column_indices, values, rhs


def reconstruct_rows():
    certificate = json.loads(base.MODULAR_CERTIFICATE.read_text(encoding="ascii"))
    pivots = [int(value) for value in certificate["pivot_unknown_indices"]]
    free = [int(value) for value in certificate["free_unknown_indices"]]
    base.require(len(pivots) == base.LOCAL_COLUMNS and len(free) == 2_239, "column partition drift")
    base.require(set(pivots).isdisjoint(free) and sorted(pivots + free) == list(range(base.GLOBAL_COLUMNS)),
                 "pivot/free partition mismatch")
    base.require(all(value in free for value in SELECTED_GLOBAL), "selected coordinate is not free")
    global_to_local = {global_coordinate: local for local, global_coordinate in enumerate(pivots)}
    global_to_c16 = {global_coordinate: local for local, global_coordinate in enumerate(SELECTED_GLOBAL)}

    equations, variables, _leading, open_factor = base.homogeneous_saturation_system()
    first, _ = base.reconstruct_quartic(base.CAMPAIGN, variables)
    second, _ = base.load_second_quartic(base.CAMPAIGN, variables)
    third, _ = base.load_third_quartic(base.CAMPAIGN, variables)
    fourth, _ = base.load_fourth_quartic(base.CAMPAIGN, variables)
    generators = list(equations) + [first, second, third]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]

    term_tables = []
    generator_weights = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [(tuple(map(int, exponents)), base.rational_pair(coefficient))
                 for exponents, coefficient in polynomial.terms()]
        base.require({sum(exponents) for exponents, _pair in terms} == {expected_degree},
                     "generator degree drift")
        weights = {base.character_weight(exponents) for exponents, _pair in terms}
        base.require(len(weights) == 1, "generator character drift")
        term_tables.append(terms)
        generator_weights.append(next(iter(weights)))

    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in base.exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, base.character_weight(monomial)), []).append(monomial)

    descriptors = []
    rows_by_monomial: dict[tuple[int, ...], dict[int, tuple[int, int]]] = {}
    for generator_index, (terms, weight, degree) in enumerate(
            zip(term_tables, generator_weights, multiplier_degrees, strict=True)):
        multiplier_weight = (2 - weight) % base.CHARACTER_MODULUS
        for multiplier in pools.get((degree, multiplier_weight), []):
            coordinate = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(left + right for left, right in zip(exponents, multiplier, strict=True))
                row = rows_by_monomial.setdefault(product, {})
                row[coordinate] = base.add_pairs(row[coordinate], pair) if coordinate in row else pair
                if row[coordinate][0] == 0:
                    del row[coordinate]

    target_expression = sp.expand(open_factor * fourth)
    target_terms = [(tuple(map(int, exponents)), base.rational_pair(coefficient))
                    for exponents, coefficient in sp.Poly(target_expression, *variables, domain=sp.QQ).terms()]
    target_map = dict(target_terms)
    for monomial in target_map:
        rows_by_monomial.setdefault(monomial, {})
    monomials = sorted(rows_by_monomial)
    hashes = {
        "generator": base.digest(tuple(generators)),
        "target": base.digest((target_expression,)),
        "descriptor": base.canonical_hash(descriptors),
        "monomial": base.canonical_hash(monomials),
    }
    base.require(hashes == base.EXPECTED_HASHES, f"algebra hash drift: {hashes}")
    base.require(len(descriptors) == base.GLOBAL_COLUMNS and len(monomials) == base.ROWS,
                 "global dimensions drift")
    return rows_by_monomial, monomials, target_map, global_to_local, global_to_c16, hashes


def export_interface(output: Path) -> dict:
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    offsets, frozen_columns, frozen_values, frozen_rhs = load_integral()
    rows_by_monomial, monomials, target_map, global_to_local, global_to_c16, hashes = reconstruct_rows()
    rhs_mod_p = bytearray(base.ROWS * RHS_COUNT)
    c_mod_p2 = array("H", [0]) * (base.ROWS * RHS_COUNT)
    sparse = []
    support = [0] * RHS_COUNT
    nonintegral = 0
    frozen_mismatches = 0

    for row_index, monomial in enumerate(monomials):
        row = rows_by_monomial[monomial]
        selected = sorted((global_to_local[coordinate], pair)
                          for coordinate, pair in row.items() if coordinate in global_to_local)
        integer_entries, integer_rhs = base.primitive_row(selected, target_map.get(monomial, (0, 1)))
        start, stop = offsets[row_index], offsets[row_index + 1]
        if ([column for column, _value in integer_entries] != frozen_columns[start:stop]
                or [value for _column, value in integer_entries] != frozen_values[start:stop]
                or integer_rhs != frozen_rhs[row_index]):
            frozen_mismatches += 1
        scale = primitive_scale(selected, target_map.get(monomial, (0, 1)))
        for coordinate, pair in row.items():
            if coordinate not in global_to_c16:
                continue
            column = global_to_c16[coordinate]
            value = scale * Fraction(*pair)
            nonintegral += value.denominator != 1
            residue_p = modular_fraction(value, P)
            residue_p2 = modular_fraction(value, P2)
            rhs_mod_p[row_index * RHS_COUNT + column] = (-residue_p) % P
            c_mod_p2[row_index * RHS_COUNT + column] = residue_p2
            support[column] += residue_p != 0
            sparse.append({
                "row": row_index,
                "column": column,
                "global_coordinate": coordinate,
                "numerator": value.numerator,
                "denominator": value.denominator,
            })

    base.require(frozen_mismatches == 0, "reconstructed B rows disagree with the frozen integral matrix")
    base.require(support == [13] * RHS_COUNT, f"selected normalized support drift: {support}")
    rhs_path = output / "rhs_minus_c16_mod173.rowmajor.u8"
    c_p2_path = output / "c16_scaled_mod29929.rowmajor.u16le"
    sparse_path = output / "c16_scaled_sparse.json"
    rhs_path.write_bytes(rhs_mod_p)
    with c_p2_path.open("xb") as handle:
        handle.write(c_mod_p2.tobytes())
    sparse_path.write_text(json.dumps({
        "schema": "hc4.fourth-colon-p173-c16-scaled-sparse.v1",
        "selected_global_coordinates": list(SELECTED_GLOBAL),
        "entries": sparse,
    }, indent=2, sort_keys=True) + "\n", encoding="ascii")
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    base.require(resources["maximum_rss_native"] < 1_500_000_000 and resources["process_swaps"] == 0,
                 "export resource gate failed")
    result = {
        "schema": "hc4.fourth-colon-p173-c16-interface.v1",
        "status": "PASS_FOURTH_COLON_P173_C16_FROZEN_ROW_INTERFACE",
        "dimensions": {"rows": base.ROWS, "pivot_columns": base.LOCAL_COLUMNS,
                       "rhs_columns": RHS_COUNT, "source_nonzeros": len(sparse)},
        "selected_global_coordinates": list(SELECTED_GLOBAL),
        "checks": {"frozen_B_row_mismatches": frozen_mismatches,
                   "support_by_column_mod173": support,
                   "nonintegral_scaled_source_entries": nonintegral,
                   "algebra_hashes": hashes},
        "inputs": {str(INTEGRAL_MATRIX.relative_to(base.CAMPAIGN)): sha256(INTEGRAL_MATRIX)},
        "outputs": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                    for path in (rhs_path, c_p2_path, sparse_path)},
        "resources": resources,
        "claim_boundary": "Exact C16 export under the frozen B-row scaling only; no kernel transfer, p-adic lift, rational syzygy, target identity, secant closure, nullcone closure, or HC4 theorem.",
    }
    receipt = output / "interface.json"
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return {"receipt": str(receipt), "sha256": sha256(receipt), **result}


def prepare_residual(interface: Path, solution: Path, output: Path) -> dict:
    started = time.perf_counter()
    offsets, columns, values, _rhs = load_integral()
    solution_bytes = solution.read_bytes()
    base.require(len(solution_bytes) == base.LOCAL_COLUMNS * RHS_COUNT, "stage-zero solution length drift")
    c_path = interface / "c16_scaled_mod29929.rowmajor.u16le"
    c_raw = c_path.read_bytes()
    base.require(len(c_raw) == 2 * base.ROWS * RHS_COUNT, "C16 p2 payload length drift")
    c_values = struct.unpack(f"<{base.ROWS * RHS_COUNT}H", c_raw)
    residual = bytearray(base.ROWS * RHS_COUNT)
    stage_zero_mismatches = 0
    digit_support = [0] * RHS_COUNT
    for row in range(base.ROWS):
        for rhs_column in range(RHS_COUNT):
            total = c_values[row * RHS_COUNT + rhs_column]
            for position in range(offsets[row], offsets[row + 1]):
                total += (values[position] % P2) * solution_bytes[columns[position] * RHS_COUNT + rhs_column]
            total %= P2
            if total % P:
                stage_zero_mismatches += 1
                continue
            digit = (-(total // P)) % P
            residual[row * RHS_COUNT + rhs_column] = digit
            digit_support[rhs_column] += digit != 0
    base.require(stage_zero_mismatches == 0, "stage-zero solution fails exact p2-aware replay")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(residual)
    result = {
        "schema": "hc4.fourth-colon-p173-c16-first-lift-residual.v1",
        "status": "PASS_FOURTH_COLON_P173_C16_FIRST_LIFT_RESIDUAL",
        "checks": {"stage_zero_replay_mismatches": stage_zero_mismatches,
                   "residual_digit_support_by_column": digit_support},
        "inputs": {"integral_matrix": sha256(INTEGRAL_MATRIX), "c16_mod_p2": sha256(c_path),
                   "stage_zero_solution": sha256(solution)},
        "output": {"path": str(output), "sha256": sha256(output), "bytes": output.stat().st_size},
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "claim_boundary": "A verified first correction RHS only; solvability and lifting through 173^2 remain to be tested.",
    }
    receipt = output.with_suffix(".json")
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return {"receipt": str(receipt), "sha256": sha256(receipt), **result}


def verify_p2(interface: Path, stage_zero: Path, correction: Path, output: Path) -> dict:
    started = time.perf_counter()
    offsets, columns, values, _rhs = load_integral()
    x0 = stage_zero.read_bytes()
    x1 = correction.read_bytes()
    base.require(len(x0) == len(x1) == base.LOCAL_COLUMNS * RHS_COUNT, "solution length drift")
    c_raw = (interface / "c16_scaled_mod29929.rowmajor.u16le").read_bytes()
    c_values = struct.unpack(f"<{base.ROWS * RHS_COUNT}H", c_raw)
    mismatches = 0
    support = [0] * RHS_COUNT
    for row in range(base.ROWS):
        for rhs_column in range(RHS_COUNT):
            total = c_values[row * RHS_COUNT + rhs_column]
            for position in range(offsets[row], offsets[row + 1]):
                coordinate = columns[position] * RHS_COUNT + rhs_column
                lifted = x0[coordinate] + P * x1[coordinate]
                total += (values[position] % P2) * lifted
            mismatches += total % P2 != 0
    for coordinate in range(base.LOCAL_COLUMNS):
        for rhs_column in range(RHS_COUNT):
            support[rhs_column] += (x0[coordinate * RHS_COUNT + rhs_column]
                                    + P * x1[coordinate * RHS_COUNT + rhs_column]) != 0
    base.require(mismatches == 0, "p2 all-row replay failed")
    result = {
        "schema": "hc4.fourth-colon-p173-c16-p2-replay.v1",
        "status": "PASS_FOURTH_COLON_P173_C16_TWO_DIGIT_KERNEL_BATCH",
        "checks": {"p2_replay_mismatches": mismatches, "lifted_support_by_column": support},
        "inputs": {"integral_matrix": sha256(INTEGRAL_MATRIX), "stage_zero_solution": sha256(stage_zero),
                   "first_correction": sha256(correction)},
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "claim_boundary": "Certified lifting of the selected 16 characteristic-173 kernel directions through 173^2 only; no rational syzygy, h4 membership, colon equality, secant closure, nullcone closure, or HC4 theorem.",
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return {"receipt": str(output), "sha256": sha256(output), **result}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--output-dir", type=Path, required=True)
    residual = subparsers.add_parser("residual")
    residual.add_argument("--interface-dir", type=Path, required=True)
    residual.add_argument("--solution", type=Path, required=True)
    residual.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify-p2")
    verify.add_argument("--interface-dir", type=Path, required=True)
    verify.add_argument("--stage-zero", type=Path, required=True)
    verify.add_argument("--correction", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "export":
        result = export_interface(arguments.output_dir if arguments.output_dir.is_absolute()
                                  else base.CAMPAIGN / arguments.output_dir)
    elif arguments.command == "residual":
        result = prepare_residual(arguments.interface_dir, arguments.solution, arguments.output)
    else:
        result = verify_p2(arguments.interface_dir, arguments.stage_zero, arguments.correction, arguments.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
