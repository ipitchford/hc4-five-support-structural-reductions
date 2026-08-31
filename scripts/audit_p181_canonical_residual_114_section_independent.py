#!/usr/bin/env -S sage -python
"""Independent source-level audit of the canonical residual-114 section."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import resource
import struct
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

import audit_j2_secant_r10_third_colon_residual_114_quotient_independent as quotient_audit


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
ROWS = 85_651
PIVOT_COLUMNS = 35_881
GLOBAL_COLUMNS = 38_048
FREE_COLUMNS = 2_167
KOSZUL_COLUMNS = 2_053
RESIDUAL_COLUMNS = 114
RAW_NONZEROS = 1_473_071
SCALED_NONZEROS = 1_354_540
WALL_CAP_SECONDS = 300.0
RSS_CAP_BYTES = 1_500_000_000

ARTIFACT = CAMPAIGN / "artifacts/third-colon-p181-canonical-residual-114-section-v1"
CSR = CAMPAIGN / "artifacts/third-colon-p181-source-clean-integral-lift-system-v1/A_Z_mod181_fixed_gauge.csr"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
QUOTIENT = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
EXACT_CHART = CAMPAIGN / "artifacts/third-colon-residual-114-p181-72digit-chart-v1/rational_chart.json"
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-canonical-residual-114-section-terminal.json"
RANK_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json"
QUOTIENT_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-residual-114-p181-72digit-independent-audit.json"
PREREGISTRATION = CAMPAIGN / "research/THIRD_COLON_P181_CANONICAL_RESIDUAL_114_SECTION_INDEPENDENT_AUDIT_PREREGISTRATION.md"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-canonical-residual-114-section-independent-audit.json"

EXPECTED = {
    "artifact_section": "b14d3efe3bf398c1bce3cd7df4d74bb23d0aaf465973eef986c21f355fee90b6",
    "full_section": "ae141f98bdacc4733273f51fbdfa1c544f4a2cc156aa05e210e993f8aa567a83",
    "pivot_section": "82db902a065b721deb146ed12655be2c00c7f1523be58218a7278e30cb3be997",
    "rhs": "c443f3da8435c81778e3ec3832dacec7977dede6986dea8ab328309f48edf2c5",
    "terminal": "6830efb1836cdddbf1c920d1d9e80893e570248206b3f72c00adf699fc904dc1",
    "csr": "eb419a8348852cb784f308ebd32eef682c731bafe77533e3b37ff5241b2228cc",
    "gauge": "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2",
    "quotient": "7ad12483dd5c8429defc3e0c5c8138ded3d344969075ae4afdb15d39d2fb9a74",
    "exact_chart": "914a21ab8c8556dec7b75737d076472a997a3ccd9d187279e046921ceac813fe",
    "rank_audit": "c6bec6f72d7ba5c0792cfe439383d1795ae82160c570148e1b7899807bd81c37",
    "quotient_audit": "5b70ce49520102483370ba57fde5c97e8c2632267a748cc4611ae69a8429e762",
    "descriptors": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomials": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generators": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def native_rss_bytes() -> int:
    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw if platform.system() == "Darwin" else raw * 1024


def guard(started: float, stage: str) -> None:
    elapsed = time.perf_counter() - started
    require(elapsed < WALL_CAP_SECONDS, f"wall cap reached during {stage}: {elapsed:.6f}s")
    require(native_rss_bytes() < RSS_CAP_BYTES, f"RSS cap reached during {stage}: {native_rss_bytes()}")
    require(int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap) == 0, f"process swapped during {stage}")


def reconstruct_coefficient_rows(started: float):
    """Second implementation of the full coefficient-only Macaulay block."""
    sys.path.insert(0, str(CAMPAIGN / "scripts"))
    from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system

    equations, variables, _leading, _open = homogeneous_saturation_system()
    require(len(equations) == 17 and len(variables) == 18, "cubic system dimensions drift")
    cubic_terms = [quotient_audit.rational_terms(equation, variables) for equation in equations]
    h_terms, h = quotient_audit.load_quartic(
        CAMPAIGN / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h_rational_terms", variables, 189, 4,
    )
    h2_terms, h2 = quotient_audit.load_quartic(
        CAMPAIGN / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "terms", variables, 211, 3,
    )
    generator_terms = cubic_terms + [h_terms, h2_terms]
    generator_expressions = list(equations) + [h, h2]
    degrees = [3] * 17 + [4, 4]
    characters = []
    for terms, degree in zip(generator_terms, degrees, strict=True):
        require({sum(exponents) for exponents, _coefficient in terms} == {degree}, "generator degree drift")
        observed = {quotient_audit.character(exponents) for exponents, _coefficient in terms}
        require(len(observed) == 1, "generator character drift")
        characters.append(next(iter(observed)))
    require(quotient_audit.expression_hash(generator_expressions) == EXPECTED["generators"], "generator hash drift")

    pools = {}
    for degree in (4, 5):
        for monomial in quotient_audit.exponent_tuples(18, degree):
            pools.setdefault((degree, quotient_audit.character(monomial)), []).append(monomial)
    descriptors = []
    row_maps = {}
    for generator_index, (terms, degree, weight) in enumerate(zip(generator_terms, degrees, characters, strict=True)):
        for multiplier in pools[(8 - degree, (3 - weight) % 12)]:
            coordinate = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, coefficient in terms:
                monomial = quotient_audit.add_exponents(multiplier, exponents)
                row = row_maps.setdefault(monomial, {})
                require(coordinate not in row, "within-column coefficient collision")
                row[coordinate] = coefficient
        guard(started, "coefficient descriptor reconstruction")
    monomials = sorted(row_maps)
    rows = [row_maps[monomial] for monomial in monomials]
    require(len(descriptors) == GLOBAL_COLUMNS, "descriptor count drift")
    require(len(rows) == ROWS, "row count drift")
    require(sum(map(len, rows)) == RAW_NONZEROS, "raw coefficient support drift")
    require(canonical_hash(descriptors) == EXPECTED["descriptors"], "descriptor hash drift")
    require(canonical_hash(monomials) == EXPECTED["monomials"], "monomial hash drift")
    return rows, descriptors, monomials


def fraction_mod(value: Fraction) -> int:
    require(value.denominator % P != 0, "nonunit raw coefficient denominator")
    return value.numerator % P * pow(value.denominator % P, -1, P) % P


def raw_modular_matrix(rows):
    offsets = np.empty(ROWS + 1, dtype=np.int64)
    indices = np.empty(RAW_NONZEROS, dtype=np.int32)
    values = np.empty(RAW_NONZEROS, dtype=np.int64)
    cursor = 0
    offsets[0] = 0
    for row_index, row in enumerate(rows):
        for coordinate, coefficient in sorted(row.items()):
            indices[cursor] = coordinate
            values[cursor] = fraction_mod(coefficient)
            cursor += 1
        offsets[row_index + 1] = cursor
    require(cursor == RAW_NONZEROS, "raw modular support drift")
    return csr_matrix((values, indices, offsets), shape=(ROWS, GLOBAL_COLUMNS), dtype=np.int64)


def read_scaled_csr():
    payload = CSR.read_bytes()
    require(payload[:8] == b"HC4AC181", "scaled CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (ROWS, PIVOT_COLUMNS, SCALED_NONZEROS), "scaled CSR dimensions drift")
    cursor = 32
    offsets = np.frombuffer(payload, dtype="<u8", count=rows + 1, offset=cursor).copy()
    cursor += 8 * (rows + 1)
    indices = np.frombuffer(payload, dtype="<u4", count=nonzeros, offset=cursor).copy()
    cursor += 4 * nonzeros
    values = np.frombuffer(payload, dtype=np.uint8, count=nonzeros, offset=cursor).copy()
    cursor += nonzeros
    require(cursor == len(payload), "scaled CSR trailing bytes")
    return offsets, indices, values


def rebuild_rhs(rows, pivots, selected):
    offsets, scaled_indices, scaled_values = read_scaled_csr()
    pivot_position = {absolute: local for local, absolute in enumerate(pivots)}
    selected_position = {absolute: local for local, absolute in enumerate(selected)}
    rhs = bytearray(ROWS * RESIDUAL_COLUMNS)
    pivot_comparisons = 0
    normalization_mismatches = 0
    for row_index, row in enumerate(rows):
        observed = {
            int(scaled_indices[position]): int(scaled_values[position])
            for position in range(int(offsets[row_index]), int(offsets[row_index + 1]))
        }
        raw_pivots = []
        for absolute, coefficient in row.items():
            local = pivot_position.get(absolute)
            if local is not None:
                residue = fraction_mod(coefficient)
                if residue:
                    raw_pivots.append((local, residue))
        require(raw_pivots and len(raw_pivots) == len(observed), f"pivot support drift at row {row_index}")
        anchor_local, anchor_raw = raw_pivots[0]
        require(anchor_local in observed, f"normalization anchor missing at row {row_index}")
        scale = observed[anchor_local] * pow(anchor_raw, -1, P) % P
        require(scale != 0, f"zero row scale at row {row_index}")
        for local, raw_value in raw_pivots:
            normalization_mismatches += int(observed.get(local) != scale * raw_value % P)
            pivot_comparisons += 1
        for absolute, coefficient in row.items():
            local = selected_position.get(absolute)
            if local is not None:
                rhs[row_index * RESIDUAL_COLUMNS + local] = (-scale * fraction_mod(coefficient)) % P
    require(pivot_comparisons == SCALED_NONZEROS, "pivot comparison count drift")
    require(normalization_mismatches == 0, "source-clean normalization mismatch")
    return bytes(rhs), pivot_comparisons, normalization_mismatches


def main() -> int:
    started = time.perf_counter()
    require(not OUTPUT.exists(), "independent audit output exists")
    bound = {
        "artifact_section": ARTIFACT / "section.json",
        "full_section": ARTIFACT / "full_residual_section_row_major.u8",
        "pivot_section": ARTIFACT / "pivot_section_row_major.u8",
        "rhs": ARTIFACT / "rhs/minus_A_S_row_major.u8",
        "terminal": TERMINAL,
        "csr": CSR,
        "gauge": GAUGE,
        "quotient": QUOTIENT,
        "exact_chart": EXACT_CHART,
        "rank_audit": RANK_AUDIT,
        "quotient_audit": QUOTIENT_AUDIT,
    }
    for name, path in bound.items():
        require(file_hash(path) == EXPECTED[name], f"bound hash drift: {name}")
    section_receipt = json.loads((ARTIFACT / "section.json").read_text(encoding="utf-8"))
    require(section_receipt.get("status") == "PASS_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION", "section PASS drift")
    require(json.loads(TERMINAL.read_text(encoding="utf-8")).get("status") == section_receipt["status"], "terminal PASS drift")

    full_payload = (ARTIFACT / "full_residual_section_row_major.u8").read_bytes()
    require(len(full_payload) == GLOBAL_COLUMNS * RESIDUAL_COLUMNS, "full section length drift")
    full = np.frombuffer(full_payload, dtype=np.uint8).reshape(GLOBAL_COLUMNS, RESIDUAL_COLUMNS)
    require(np.all(full < P), "full section residue drift")

    rows, descriptors, monomials = reconstruct_coefficient_rows(started)
    raw_matrix = raw_modular_matrix(rows)
    action = (raw_matrix @ full.astype(np.int64)) % P
    raw_action_mismatches = int(np.count_nonzero(action))
    raw_action_hash = hashlib.sha256(action.astype(np.uint8).tobytes(order="C")).hexdigest()
    require(raw_action_mismatches == 0, "direct raw-source kernel action failed")
    del raw_matrix, action
    guard(started, "direct raw-source kernel replay")

    gauge_payload = GAUGE.read_bytes()
    require(len(gauge_payload) == 4 * PIVOT_COLUMNS, "gauge length drift")
    main_pivots = [item[0] for item in struct.iter_unpack("<I", gauge_payload)]
    require(len(set(main_pivots)) == PIVOT_COLUMNS, "main gauge duplicate")
    quotient = json.loads(QUOTIENT.read_text(encoding="utf-8"))
    selected = list(map(int, quotient["ordered_complement_absolute_coordinates"]))
    rebuilt_rhs, pivot_comparisons, normalization_mismatches = rebuild_rhs(rows, main_pivots, selected)
    saved_rhs = (ARTIFACT / "rhs/minus_A_S_row_major.u8").read_bytes()
    rhs_byte_mismatches = sum(left != right for left, right in zip(rebuilt_rhs, saved_rhs, strict=True))
    require(rhs_byte_mismatches == 0 and hashlib.sha256(rebuilt_rhs).hexdigest() == EXPECTED["rhs"], "independent RHS rebuild failed")
    guard(started, "independent RHS reconstruction")

    quotient_audit.WALL_CAP_SECONDS = WALL_CAP_SECONDS
    quotient_audit.RSS_CAP_BYTES = RSS_CAP_BYTES
    integer_koszul = quotient_audit.reconstruct_koszul(CAMPAIGN, started)
    free, _bindings = quotient_audit.load_free_sources(CAMPAIGN)
    restricted, _absolute_to_local = quotient_audit.restrict_rows(integer_koszul, free)
    p_local, pivot_telemetry = quotient_audit.select_p181_pivots(restricted, started)
    s_local = sorted(set(range(FREE_COLUMNS)) - set(p_local))
    p_absolute = [free[index] for index in p_local]
    s_absolute = [free[index] for index in s_local]
    require(p_absolute == list(map(int, quotient["ordered_pivot_absolute_coordinates_discovery_order"])), "independent P coordinate drift")
    require(s_absolute == selected, "independent S coordinate drift")
    require(pivot_telemetry["rank"] == KOSZUL_COLUMNS and len(s_local) == RESIDUAL_COLUMNS, "independent Koszul chart dimensions drift")

    p_block = full[np.asarray(p_absolute, dtype=np.int64), :].astype(np.int64)
    s_block = full[np.asarray(s_absolute, dtype=np.int64), :].astype(np.int64)
    p_nonzeros = int(np.count_nonzero(p_block))
    s_identity_mismatches = int(np.count_nonzero(s_block - np.eye(RESIDUAL_COLUMNS, dtype=np.int64)))
    require(p_nonzeros == 0 and s_identity_mismatches == 0, "residual P/S normalization failed")

    exact = json.loads(EXACT_CHART.read_text(encoding="utf-8"))
    denominator = int(exact["global_denominator"])
    require(denominator % P != 0, "exact chart denominator nonunit at p181")
    inverse = pow(denominator % P, -1, P)
    transition = np.asarray([
        [int(value) % P * inverse % P for value in row]
        for row in exact["integer_numerator_matrix_row_major"]
    ], dtype=np.int64)
    quotient_coordinates = (s_block.T - p_block.T @ transition) % P
    quotient_identity_mismatches = int(np.count_nonzero(quotient_coordinates - np.eye(RESIDUAL_COLUMNS, dtype=np.int64)))
    require(quotient_identity_mismatches == 0, "independent quotient identity failed")

    rank_audit = json.loads(RANK_AUDIT.read_text(encoding="utf-8"))
    require(rank_audit.get("status") == "PASS_INDEPENDENT_ACTUAL_COEFFICIENT_LINBOX_RANK_SCALING_AUDIT", "bound rank audit PASS drift")
    rank_records = {int(record["columns"]): int(record["rank"]) for record in rank_audit["rank_results"]}
    main_rank = rank_records.get(PIVOT_COLUMNS)
    require(main_rank == PIVOT_COLUMNS, "bound main rank drift")
    deduced_kernel_dimension = GLOBAL_COLUMNS - main_rank
    combined_rank = KOSZUL_COLUMNS + RESIDUAL_COLUMNS
    require(combined_rank == FREE_COLUMNS == deduced_kernel_dimension, "kernel completion dimension drift")

    support_counts = np.count_nonzero(full, axis=0).astype(int).tolist()
    require(support_counts == list(map(int, section_receipt["section"]["column_support_counts"])), "support census drift")
    resources = {
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_bytes": native_rss_bytes(),
        "process_swaps": int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap),
    }
    require(resources["wall_seconds"] < WALL_CAP_SECONDS, "terminal wall cap breach")
    require(resources["maximum_rss_bytes"] < RSS_CAP_BYTES, "terminal RSS cap breach")
    require(resources["process_swaps"] == 0, "terminal swap breach")

    receipt = {
        "schema": "hc4.third-colon-p181-canonical-residual-114-section-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION",
        "bound_hashes": {name: file_hash(path) for name, path in bound.items()},
        "preregistration": {"path": str(PREREGISTRATION.relative_to(CAMPAIGN)), "sha256": file_hash(PREREGISTRATION)},
        "source_reconstruction": {
            "generator_count": 19,
            "descriptor_count": len(descriptors),
            "row_count": len(monomials),
            "raw_nonzero_count": sum(map(len, rows)),
            "descriptor_sha256": canonical_hash(descriptors),
            "monomial_sha256": canonical_hash(monomials),
        },
        "direct_kernel_replay": {
            "matrix_shape": [ROWS, GLOBAL_COLUMNS],
            "section_shape": [GLOBAL_COLUMNS, RESIDUAL_COLUMNS],
            "scalar_comparisons": ROWS * RESIDUAL_COLUMNS,
            "mismatch_count": raw_action_mismatches,
            "residual_matrix_sha256": raw_action_hash,
        },
        "rhs_reconstruction": {
            "pivot_scalar_comparisons": pivot_comparisons,
            "normalization_mismatch_count": normalization_mismatches,
            "byte_comparisons": len(saved_rhs),
            "byte_mismatch_count": rhs_byte_mismatches,
            "rebuilt_rhs_sha256": hashlib.sha256(rebuilt_rhs).hexdigest(),
        },
        "koszul_reconstruction": {
            "primitive_row_count": len(integer_koszul),
            "primitive_nonzero_count": sum(map(len, integer_koszul)),
            "restricted_pivot_rank": pivot_telemetry["rank"],
            "pivot_telemetry": pivot_telemetry,
            "P_absolute_sha256": canonical_hash(p_absolute),
            "S_absolute_sha256": canonical_hash(s_absolute),
        },
        "section_normalization": {
            "P_nonzero_count": p_nonzeros,
            "S_identity_mismatch_count": s_identity_mismatches,
            "quotient_identity_mismatch_count": quotient_identity_mismatches,
            "transition_mod181_sha256": canonical_hash(transition.astype(int).tolist()),
            "column_support_counts": support_counts,
            "support_minimum": min(support_counts),
            "support_median": float(np.median(np.asarray(support_counts))),
            "support_maximum": max(support_counts),
        },
        "kernel_completion": {
            "independent_Koszul_rank_on_P": KOSZUL_COLUMNS,
            "independent_residual_rank_on_S": RESIDUAL_COLUMNS,
            "block_triangular_combined_rank": combined_rank,
            "bound_main_matrix_rank": main_rank,
            "deduced_full_kernel_dimension_mod181": deduced_kernel_dimension,
            "exhaustion_uses_separately_bound_rank_receipt": True,
        },
        "resources": resources,
        "declarations": {
            "producer_not_imported_or_executed": True,
            "rhs_builder_not_imported_or_executed": True,
            "linbox_driver_not_executed": True,
            "section_verifier_not_imported_or_executed": True,
            "raw_rational_coefficient_action_rebuilt": True,
            "primitive_Koszul_rows_rebuilt": True,
            "no_QQ_residual_lift": True,
            "target_multiplier_not_read": True,
        },
        "claim_boundary": "This PASS independently certifies the 114 canonical residual kernel sections and, conditional on the separately bound exact modular-rank receipt, the full 2167-dimensional encoded kernel over GF(181). It does not lift a residual syzygy to QQ, prove QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
