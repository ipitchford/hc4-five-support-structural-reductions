#!/usr/bin/env -S sage -python
"""Exact LinBox rank scaling on the actual target-free p181 coefficient map."""

from __future__ import annotations

import argparse
import gc
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
from sage.all import GF, matrix, vector
from sage.env import SAGE_VERSION

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import load_second_quartic
from certify_j2_secant_r10_z12_macaulay import CHARACTER_MODULUS, character_weight, exact_exponent_tuples
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
PREFIXES = (4_096, 8_192, 16_384, 35_881)
EXPECTED = {
    "rows": 85_651,
    "global_columns": 38_048,
    "global_nonzeros": 1_473_071,
    "selected_columns": 35_881,
    "selected_nonzeros": 1_354_540,
    "descriptor_sha256": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomial_sha256": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generator_sha256": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
    "selected_column_stream_sha256": "cc5545feb4addbae085b17423b9209fd55def54e7ba21c941aa36b6b62c9d80e",
    "row_offset_stream_sha256": "0c639f77facef51e17d0af1736c0b802e045c5eed5179e13c35503b81fa389e7",
    "pivot_stream_sha256": "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")).hexdigest()


def read_pivots(path: Path) -> list[int]:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != EXPECTED["pivot_stream_sha256"] or len(payload) != 35_881 * 4:
        raise ValueError("sealed pivot stream drift")
    return [item[0] for item in struct.iter_unpack("<I", payload)]


def rational_pair(value: object) -> tuple[int, int]:
    rational = sp.Rational(value)
    return int(rational.p), int(rational.q)


def add_pairs(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    result = Fraction(left[0], left[1]) + Fraction(right[0], right[1])
    return result.numerator, result.denominator


def build_target_free_csr(pivots: list[int]):
    started = time.perf_counter()
    equations, variables, _leading_form, _open_factor = homogeneous_saturation_system()
    first, _ = reconstruct_quartic(CAMPAIGN, variables)
    second, _ = load_second_quartic(CAMPAIGN, variables)
    generators = list(equations) + [first, second]
    generator_degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - value for value in generator_degrees]
    polynomial_terms = []
    generator_weights = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [(tuple(map(int, exponents)), rational_pair(coefficient)) for exponents, coefficient in polynomial.terms()]
        weights = {character_weight(exponents) for exponents, _ in terms}
        degrees = {sum(exponents) for exponents, _ in terms}
        if len(weights) != 1 or degrees != {expected_degree}:
            raise ValueError("generator left the frozen degree/character block")
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
    if len(generators) != 19 or generator_weights[-2:] != [4, 3]:
        raise ValueError("generator family drift")

    pools = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    monomials = sorted(
        monomial for monomial in exact_exponent_tuples(len(variables), 8)
        if character_weight(monomial) == 3
    )
    monomial_to_row = {monomial: index for index, monomial in enumerate(monomials)}
    rows: list[dict[int, tuple[int, int]]] = [dict() for _ in monomials]
    descriptors = []
    collision_additions = 0
    for generator_index, (terms, generator_weight, multiplier_degree) in enumerate(
        zip(polynomial_terms, generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (3 - generator_weight) % CHARACTER_MODULUS
        for multiplier in pools.get((multiplier_degree, multiplier_weight), []):
            column = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(left + right for left, right in zip(exponents, multiplier, strict=True))
                row = rows[monomial_to_row[product]]
                if column in row:
                    collision_additions += 1
                    combined = add_pairs(row[column], pair)
                    if combined[0]:
                        row[column] = combined
                    else:
                        del row[column]
                else:
                    row[column] = pair

    structural = {
        "descriptor_sha256": canonical_hash(descriptors),
        "monomial_sha256": canonical_hash(monomials),
        "generator_sha256": digest(tuple(generators)),
    }
    for key, value in structural.items():
        if value != EXPECTED[key]:
            raise ValueError(f"{key} drift")
    if len(rows) != EXPECTED["rows"] or len(descriptors) != EXPECTED["global_columns"]:
        raise ValueError("coefficient block dimensions drift")
    if sum(map(len, rows)) != EXPECTED["global_nonzeros"]:
        raise ValueError("global coefficient support drift")

    global_to_local = {global_column: local for local, global_column in enumerate(pivots)}
    offsets = array("Q", [0])
    columns = array("I")
    residues = array("B")
    maximum_integer_bit_length = 0
    nonunit_rows = 0
    for row in rows:
        selected = []
        denominators = [pair[1] for pair in row.values()]
        denominator_lcm = math.lcm(*denominators)
        integer_entries = [(column, pair[0] * (denominator_lcm // pair[1])) for column, pair in sorted(row.items())]
        content = math.gcd(*(abs(value) for _column, value in integer_entries if value))
        integer_entries = [(column, value // content) for column, value in integer_entries if value]
        if integer_entries[0][1] < 0:
            integer_entries = [(column, -value) for column, value in integer_entries]
        if content % P == 0 or denominator_lcm % P == 0:
            nonunit_rows += 1
        for global_column, value in integer_entries:
            local = global_to_local.get(global_column)
            if local is not None:
                residue = value % P
                if residue == 0:
                    raise ValueError("selected coefficient vanished modulo 181")
                selected.append((local, residue))
            maximum_integer_bit_length = max(maximum_integer_bit_length, abs(value).bit_length())
        for local, residue in sorted(selected):
            columns.append(local)
            residues.append(residue)
        offsets.append(len(columns))
    if nonunit_rows:
        raise ValueError(f"{nonunit_rows} coefficient-only row scalings are nonunits")
    if len(columns) != EXPECTED["selected_nonzeros"]:
        raise ValueError("selected support count drift")
    packed_columns = b"".join(struct.pack("<I", value) for value in columns)
    packed_offsets = b"".join(struct.pack("<Q", value) for value in offsets)
    if hashlib.sha256(packed_columns).hexdigest() != EXPECTED["selected_column_stream_sha256"]:
        raise ValueError("selected column stream drift")
    if hashlib.sha256(packed_offsets).hexdigest() != EXPECTED["row_offset_stream_sha256"]:
        raise ValueError("row offset stream drift")
    metadata = {
        **structural,
        "rows": len(rows),
        "global_columns": len(descriptors),
        "global_nonzeros": sum(map(len, rows)),
        "selected_columns": len(pivots),
        "selected_nonzeros": len(columns),
        "collision_additions": collision_additions,
        "maximum_primitive_coefficient_bit_length": maximum_integer_bit_length,
        "nonunit_row_scalings": nonunit_rows,
        "selected_column_stream_sha256": EXPECTED["selected_column_stream_sha256"],
        "row_offset_stream_sha256": EXPECTED["row_offset_stream_sha256"],
        "residue_stream_sha256": hashlib.sha256(residues.tobytes()).hexdigest(),
        "build_seconds": time.perf_counter() - started,
    }
    del rows, descriptors, generators, polynomial_terms, pools, monomial_to_row
    gc.collect()
    return offsets, columns, residues, metadata


def sparse_matrix_from_csr(offsets, columns, residues, width: int):
    entries = {}
    for row in range(EXPECTED["rows"]):
        for position in range(offsets[row], offsets[row + 1]):
            column = columns[position]
            if column < width:
                entries[(row, column)] = residues[position]
    result = matrix(GF(P), EXPECTED["rows"], width, entries, sparse=True)
    nonzeros = len(entries)
    del entries
    gc.collect()
    return result, nonzeros


def benchmark_case(offsets, columns, residues, width: int) -> dict[str, object]:
    build_started = time.perf_counter()
    coefficient, nonzeros = sparse_matrix_from_csr(offsets, columns, residues, width)
    build_seconds = time.perf_counter() - build_started
    output_hash = hashlib.sha256()
    matvec_started = time.perf_counter()
    field = GF(P)
    for repetition in range(16):
        probe = vector(field, [((repetition + 1) * (column + 1) + 17) % P for column in range(width)])
        product = coefficient * probe
        output_hash.update(bytes(int(value) for value in product))
    matvec_seconds = time.perf_counter() - matvec_started
    rank_started = time.perf_counter()
    observed_rank = int(coefficient.rank(algorithm="linbox"))
    rank_seconds = time.perf_counter() - rank_started
    del coefficient
    gc.collect()
    return {
        "columns": width,
        "rows": EXPECTED["rows"],
        "nonzeros": nonzeros,
        "matrix_build_seconds": build_seconds,
        "sixteen_matvec_seconds": matvec_seconds,
        "matvec_output_sha256": output_hash.hexdigest(),
        "linbox_rank": observed_rank,
        "linbox_rank_seconds": rank_seconds,
        "full_column_rank": observed_rank == width,
        "maximum_rss_native_after_case": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gauge-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    freeze_path = args.freeze if args.freeze.is_absolute() else CAMPAIGN / args.freeze
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    source_relative = str(Path(__file__).resolve().relative_to(CAMPAIGN))
    if freeze.get("status") != "PASS_P181_TARGET_BLIND_LINBOX_IMPLEMENTATION_FREEZE" or freeze["implementation_sources"].get(source_relative) != file_hash(Path(__file__).resolve()):
        raise ValueError("implementation freeze mismatch")
    gauge = args.gauge_dir if args.gauge_dir.is_absolute() else CAMPAIGN / args.gauge_dir
    gauge_receipt = json.loads((gauge / "gauge.json").read_text(encoding="utf-8"))
    if gauge_receipt.get("status") != "PASS_EXTRACTED_P181_PIVOT_GAUGE_ONLY":
        raise ValueError("sealed gauge missing")
    pivots = read_pivots(gauge / "C_piv.u32le")
    started = time.perf_counter()
    offsets, columns, residues, construction = build_target_free_csr(pivots)
    csr_path = output / "A_C_mod181_target_free.csr"
    with csr_path.open("wb") as handle:
        handle.write(b"HC4AC181")
        handle.write(struct.pack("<QQQ", EXPECTED["rows"], EXPECTED["selected_columns"], len(columns)))
        handle.write(offsets.tobytes())
        handle.write(columns.tobytes())
        handle.write(residues.tobytes())
    cases = []
    for width in PREFIXES:
        case = benchmark_case(offsets, columns, residues, width)
        cases.append(case)
        checkpoint = {"status": "PARTIAL_TARGET_BLIND_RANK_CALIBRATION_ONLY", "completed_cases": cases}
        (output / "checkpoint.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"event": "rank_case_complete", **case}, sort_keys=True), flush=True)
        if not case["full_column_rank"]:
            break
    passed = len(cases) == len(PREFIXES) and all(case["full_column_rank"] for case in cases)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-rank.v1",
        "status": "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING" if passed else "STOP_ACTUAL_COEFFICIENT_LINBOX_RANK_DEFICIT",
        "characteristic": P,
        "sage_version": SAGE_VERSION,
        "algorithm": "Sage Matrix_modn_sparse.rank(algorithm='linbox')",
        "construction": construction,
        "cases": cases,
        "csr_artifact": {"path": csr_path.name, "sha256": file_hash(csr_path), "bytes": csr_path.stat().st_size},
        "inputs": {"gauge_receipt_sha256": file_hash(gauge / "gauge.json"), "implementation_freeze_sha256": file_hash(freeze_path)},
        "resources": {"maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, "wall_seconds": time.perf_counter() - started},
        "declarations": {
            "third_candidate_not_imported_or_constructed": True,
            "rhs_not_imported_constructed_or_read": True,
            "known_solution_not_read": True,
            "no_augmented_rank": True,
            "no_solve": True,
            "no_p_adic_digit": True,
        },
        "claim_boundary": "This is exact rank and scaling evidence for the actual target-free coefficient map only. It is not target membership, a multiplier, a QQ identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    receipt_path = output / "benchmark.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path)}, sort_keys=True), flush=True)
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
