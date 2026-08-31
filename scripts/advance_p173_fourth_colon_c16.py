#!/usr/bin/env -S sage -python
"""Advance, reconstruct, and exactly replay the frozen fourth-colon C16 batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import time
from fractions import Fraction
from pathlib import Path

import build_p173_fourth_colon_c16_interface as c16
import build_p173_fourth_colon_integral_lift_system as base


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_digits(paths: list[Path]) -> list[bytes]:
    expected = base.LOCAL_COLUMNS * c16.RHS_COUNT
    payloads = [path.read_bytes() for path in paths]
    base.require(all(len(payload) == expected for payload in payloads), "digit payload length drift")
    return payloads


def load_source(interface: Path) -> dict[tuple[int, int], Fraction]:
    document = json.loads((interface / "c16_scaled_sparse.json").read_text(encoding="ascii"))
    base.require(document.get("selected_global_coordinates") == list(c16.SELECTED_GLOBAL),
                 "source selection drift")
    result = {}
    for entry in document["entries"]:
        key = (int(entry["row"]), int(entry["column"]))
        base.require(key not in result, "duplicate source entry")
        result[key] = Fraction(int(entry["numerator"]), int(entry["denominator"]))
    base.require(len(result) == 208, "source sparsity drift")
    return result


def accumulated(digits: list[bytes]) -> list[int]:
    total = [0] * (base.LOCAL_COLUMNS * c16.RHS_COUNT)
    place = 1
    for payload in digits:
        for index, value in enumerate(payload):
            total[index] += place * value
        place *= c16.P
    return total


def prepare_next(interface: Path, digit_paths: list[Path], output: Path) -> dict:
    started = time.perf_counter()
    digits = load_digits(digit_paths)
    height = len(digits)
    base.require(2 <= height <= 3, "next-digit preparation is frozen for heights 2 and 3")
    current_modulus = c16.P ** height
    next_modulus = current_modulus * c16.P
    vector = accumulated(digits)
    source = load_source(interface)
    offsets, columns, values, _rhs = c16.load_integral()
    rhs = bytearray(base.ROWS * c16.RHS_COUNT)
    current_mismatches = 0
    support = [0] * c16.RHS_COUNT
    for row in range(base.ROWS):
        for rhs_column in range(c16.RHS_COUNT):
            source_value = source.get((row, rhs_column), Fraction(0))
            total = c16.modular_fraction(source_value, next_modulus)
            for position in range(offsets[row], offsets[row + 1]):
                total += (values[position] % next_modulus) * vector[
                    columns[position] * c16.RHS_COUNT + rhs_column]
            total %= next_modulus
            if total % current_modulus:
                current_mismatches += 1
                continue
            digit = (-(total // current_modulus)) % c16.P
            rhs[row * c16.RHS_COUNT + rhs_column] = digit
            support[rhs_column] += digit != 0
    base.require(current_mismatches == 0, f"height-{height} accumulated replay failed")
    output.write_bytes(rhs)
    result = {
        "schema": "hc4.fourth-colon-p173-c16-next-residual.v1",
        "status": f"PASS_FOURTH_COLON_P173_C16_HEIGHT_{height}_RESIDUAL",
        "height": height,
        "checks": {"current_height_replay_mismatches": current_mismatches,
                   "next_residual_support_by_column": support},
        "inputs": {"integral_matrix": sha256(c16.INTEGRAL_MATRIX),
                   "source_sparse": sha256(interface / "c16_scaled_sparse.json"),
                   "digits": [{"path": str(path), "sha256": sha256(path)} for path in digit_paths]},
        "output": {"path": str(output), "sha256": sha256(output), "bytes": output.stat().st_size},
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "claim_boundary": f"Verified height-{height} residual only; the next digit, rational reconstruction, exact source syzygies, h4 membership, colon equality, secant closure, nullcone closure, and HC4 remain open.",
    }
    receipt = output.with_suffix(".json")
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return {"receipt": str(receipt), "receipt_sha256": sha256(receipt), **result}


def rational_reconstruction(residue: int, modulus: int) -> Fraction | None:
    residue %= modulus
    if residue == 0:
        return Fraction(0)
    bound = math.isqrt((modulus - 1) // 2)
    old_r, r = modulus, residue
    old_t, t = 0, 1
    while r > bound:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_t, t = t, old_t - quotient * t
    numerator, denominator = r, t
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if (denominator == 0 or abs(numerator) > bound or denominator > bound
            or math.gcd(abs(numerator), denominator) != 1
            or (numerator - residue * denominator) % modulus != 0):
        return None
    return Fraction(numerator, denominator)


def reconstruct_and_replay(interface: Path, digit_paths: list[Path], output: Path) -> dict:
    started = time.perf_counter()
    digits = load_digits(digit_paths)
    height = len(digits)
    base.require(height == 4, "equal-height reconstruction is frozen at exactly four digits")
    modulus = c16.P ** height
    bound = math.isqrt((modulus - 1) // 2)
    residues = accumulated(digits)
    rational = []
    unresolved = []
    for index, residue in enumerate(residues):
        candidate = rational_reconstruction(residue, modulus)
        rational.append(candidate)
        if candidate is None:
            unresolved.append(index)
    source = load_source(interface)
    offsets, columns, values, _rhs = c16.load_integral()
    modular_mismatches = 0
    for row in range(base.ROWS):
        for rhs_column in range(c16.RHS_COUNT):
            total = c16.modular_fraction(source.get((row, rhs_column), Fraction(0)), modulus)
            for position in range(offsets[row], offsets[row + 1]):
                total += (values[position] % modulus) * residues[
                    columns[position] * c16.RHS_COUNT + rhs_column]
            modular_mismatches += total % modulus != 0
    base.require(modular_mismatches == 0, "four-digit modular replay failed")

    exact_mismatches = None
    exact_nonzero = None
    candidate_path = output.with_name("rational-candidates.json")
    if not unresolved:
        exact_mismatches = 0
        exact_nonzero = [0] * c16.RHS_COUNT
        for coordinate in range(base.LOCAL_COLUMNS):
            for rhs_column in range(c16.RHS_COUNT):
                exact_nonzero[rhs_column] += rational[
                    coordinate * c16.RHS_COUNT + rhs_column] != 0
        for row in range(base.ROWS):
            totals = [source.get((row, rhs_column), Fraction(0))
                      for rhs_column in range(c16.RHS_COUNT)]
            for position in range(offsets[row], offsets[row + 1]):
                coefficient = values[position]
                coordinate = columns[position] * c16.RHS_COUNT
                for rhs_column in range(c16.RHS_COUNT):
                    value = rational[coordinate + rhs_column]
                    if value:
                        totals[rhs_column] += coefficient * value
            exact_mismatches += sum(total != 0 for total in totals)
        sparse_candidates = []
        for coordinate in range(base.LOCAL_COLUMNS):
            for rhs_column in range(c16.RHS_COUNT):
                value = rational[coordinate * c16.RHS_COUNT + rhs_column]
                if value:
                    sparse_candidates.append({"pivot_coordinate": coordinate, "column": rhs_column,
                                              "numerator": value.numerator,
                                              "denominator": value.denominator})
        candidate_path.write_text(json.dumps({
            "schema": "hc4.fourth-colon-p173-c16-rational-candidates.v1",
            "modulus": modulus,
            "height_bound": bound,
            "selected_global_coordinates": list(c16.SELECTED_GLOBAL),
            "entries": sparse_candidates,
        }, indent=2, sort_keys=True) + "\n", encoding="ascii")

    passed = not unresolved and exact_mismatches == 0
    result = {
        "schema": "hc4.fourth-colon-p173-c16-p4-reconstruction.v1",
        "status": ("PASS_FOURTH_COLON_P173_C16_EXACT_RATIONAL_KERNEL_BATCH"
                   if passed else "STOP_FOURTH_COLON_P173_C16_P4_EQUAL_HEIGHT_RECONSTRUCTION"),
        "height": height,
        "modulus": modulus,
        "height_bound": bound,
        "checks": {"p4_replay_mismatches": modular_mismatches,
                   "resolved_coordinates": len(rational) - len(unresolved),
                   "unresolved_coordinates": len(unresolved),
                   "first_unresolved_indices": unresolved[:64],
                   "exact_replay_mismatches": exact_mismatches,
                   "exact_nonzero_support_by_column": exact_nonzero},
        "inputs": {"integral_matrix": sha256(c16.INTEGRAL_MATRIX),
                   "source_sparse": sha256(interface / "c16_scaled_sparse.json"),
                   "digits": [{"path": str(path), "sha256": sha256(path)} for path in digit_paths]},
        "output": ({"path": str(candidate_path), "sha256": sha256(candidate_path),
                    "bytes": candidate_path.stat().st_size} if candidate_path.exists() else None),
        "resources": {"wall_seconds": time.perf_counter() - started,
                      "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)},
        "claim_boundary": ("Exact rational source-kernel syzygies for the selected 16 columns only; no h4 membership, colon equality, saturation, secant closure, full nullcone closure, quartic Hessian conjecture, or Jacobian conjecture follows."
                           if passed else "The frozen four-digit equal-height reconstruction hierarchy stopped; this does not prove that rational kernel syzygies do not exist at larger height or under another justified reconstruction architecture."),
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    return {"receipt": str(output), "receipt_sha256": sha256(output), **result}


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    next_parser = subparsers.add_parser("next-residual")
    next_parser.add_argument("--interface-dir", type=Path, required=True)
    next_parser.add_argument("--digits", type=Path, nargs="+", required=True)
    next_parser.add_argument("--output", type=Path, required=True)
    reconstruct = subparsers.add_parser("reconstruct-p4")
    reconstruct.add_argument("--interface-dir", type=Path, required=True)
    reconstruct.add_argument("--digits", type=Path, nargs=4, required=True)
    reconstruct.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "next-residual":
        result = prepare_next(arguments.interface_dir, arguments.digits, arguments.output)
    else:
        result = reconstruct_and_replay(arguments.interface_dir, arguments.digits, arguments.output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
