#!/usr/bin/env python3
"""Audit the exact tangent V6-highest nullcone certificate.

The proof cover has two layers.  First, V6 != 0 is normalized to V6 = 1 by
the residual tangent torus and split by the largest nonzero coefficient f_r,
r=5,...,10.  Second, the r=10 cell is split by A(t)=0 or deg A=d for
d=0,...,6.  Every terminal cell must carry a clean characteristic-zero unit
ideal receipt built from the currently reconstructed equations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from certify_nullcone_v6_tangent_r10_convolution_branch import branch_system
from scout_decimic_nullcone_hsop import digest, f_coefficients
from scout_nullcone_cubic_families import raw_coefficient_family
from scout_nullcone_v6_tangent_top_stratum import stratum


TOP_FILES = {
    5: "receipts/nullcone-v6-tangent-top-r5-qq-modstd.json",
    6: "receipts/nullcone-v6-tangent-top-r6-qq-slimgb.json",
    7: "receipts/nullcone-v6-tangent-top-r7-qq-slimgb.json",
    8: "receipts/nullcone-v6-tangent-top-r8-qq-slimgb.json",
    9: "receipts/nullcone-v6-tangent-top-r9-qq-slimgb.json",
}

R10_FILES = {
    "A_zero": ("eliminate", "receipts/nullcone-v6-tangent-r10-A_zero-qq-slimgb.json"),
    "degree_0": ("eliminate", "receipts/nullcone-v6-tangent-r10-degree0-qq-slimgb.json"),
    "degree_1": ("eliminate", "receipts/nullcone-v6-tangent-r10-degree1-qq-slimgb.json"),
    "degree_2": ("eliminate", "receipts/nullcone-v6-tangent-r10-degree2-qq-slimgb.json"),
    "degree_3": ("direct", "receipts/nullcone-v6-tangent-r10-degree3-qq-slimgb-direct.json"),
    "degree_4": ("direct", "receipts/nullcone-v6-tangent-r10-degree4-qq-slimgb-direct.json"),
    "degree_5": ("direct", "receipts/nullcone-v6-tangent-r10-degree5-qq-slimgb-direct.json"),
    "degree_6": ("keep", "receipts/nullcone-v6-tangent-r10-degree6-qq-slimgb-keep.json"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exact_unit(path: Path, status: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    calculation = data.get("calculation")
    if data.get("status") != status:
        raise AssertionError(f"{path.name}: unexpected status")
    if data.get("characteristic") != 0 or data.get("unipotent_used") is not False:
        raise AssertionError(f"{path.name}: not a valid characteristic-zero no-unipotent cell")
    if not isinstance(calculation, dict):
        raise AssertionError(f"{path.name}: missing calculation")
    if (
        not calculation.get("is_unit")
        or calculation.get("timed_out")
        or calculation.get("return_code") != 0
        or calculation.get("basis_size") != "1"
        or calculation.get("unit_remainder") != "0"
    ):
        raise AssertionError(f"{path.name}: not a clean exact unit calculation")
    if "BASIS_SIZE\n1\n" not in calculation.get("stdout_tail", ""):
        raise AssertionError(f"{path.name}: unit basis was not displayed")
    return data


def verify_torus_weight(target: sp.Expr, coefficient_weights: list[int]) -> int:
    weights = dict(zip(f_coefficients, coefficient_weights, strict=True))
    term_weights = {
        sum(
            monomial.as_powers_dict().get(symbol, 0) * weights[symbol]
            for symbol in f_coefficients
        )
        for monomial in sp.Add.make_args(sp.expand(target))
    }
    if len(term_weights) != 1:
        raise AssertionError(f"V6 is not torus homogeneous: {sorted(term_weights)}")
    return next(iter(term_weights))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v6-tangent-highest-all-strata.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent

    torus_path = campaign / "receipts/residual-orbit-torus.json"
    torus = json.loads(torus_path.read_text(encoding="utf-8"))
    if torus.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    coefficient_weights = torus["tangent"]["coefficient_weights"]
    target = raw_coefficient_family("V6")
    target_weight = verify_torus_weight(target, coefficient_weights)
    if target_weight == 0:
        raise AssertionError("V6 has zero tangent torus weight and cannot be normalized")
    below_r5 = sp.expand(
        target.subs({f_coefficients[index]: 0 for index in range(5, 11)})
    )
    if below_r5 != 0:
        raise AssertionError("V6 does not force a largest nonzero index in 5,...,10")

    evidence_sha256: dict[str, str] = {"receipts/residual-orbit-torus.json": sha256(torus_path)}
    top_cells: dict[str, object] = {}
    common_target = set()
    for top_index, relative in TOP_FILES.items():
        path = campaign / relative
        data = load_exact_unit(path, "EXACT_HIGHEST_WEIGHT_RADICAL_ON_COVER_STRATUM")
        if data.get("top_index") != top_index or data.get("family") != "V6":
            raise AssertionError(f"{path.name}: mismatched cover cell")
        equations, auxiliary, _, _, reduced_target, _ = stratum(top_index)
        if data.get("normal_equation_stream_sha256") != digest(tuple(equations)):
            raise AssertionError(f"{path.name}: normal equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(auxiliary)):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("target_sha256") != digest((reduced_target,)):
            raise AssertionError(f"{path.name}: target does not replay")
        common_target.add(data["source_sha256"]["scripts/scout_nullcone_cubic_families.py"])
        top_cells[str(top_index)] = {
            "receipt": relative,
            "algorithm": data["algorithm"],
            "normal_equation_stream_sha256": data["normal_equation_stream_sha256"],
        }
        evidence_sha256[relative] = sha256(path)
    if len(common_target) != 1:
        raise AssertionError("top cells do not share one frozen V6 source")

    r10_cells: dict[str, object] = {}
    common_A: set[str] = set()
    common_C: set[str] = set()
    for branch, (mode, relative) in R10_FILES.items():
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_V6_TANGENT_R10_CONVOLUTION_BRANCH")
        if data.get("branch") != branch or data.get("top_index") != 10:
            raise AssertionError(f"{path.name}: mismatched r=10 branch")
        rebuilt = branch_system(branch, mode)
        if data.get("equation_stream_sha256") != digest(tuple(rebuilt["equations"])):
            raise AssertionError(f"{path.name}: equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(rebuilt["auxiliary"])):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("A_sha256") != digest((rebuilt["A"],)):
            raise AssertionError(f"{path.name}: A(t) does not replay")
        if data.get("C_sha256") != digest((rebuilt["C"],)):
            raise AssertionError(f"{path.name}: C(t) does not replay")
        common_A.add(data["A_sha256"])
        common_C.add(data["C_sha256"])
        r10_cells[branch] = {
            "receipt": relative,
            "mode": mode,
            "algorithm": data["algorithm"],
            "A_degree": data["A_degree"],
            "equation_stream_sha256": data["equation_stream_sha256"],
        }
        evidence_sha256[relative] = sha256(path)
    expected_branches = {"A_zero"} | {f"degree_{degree}" for degree in range(7)}
    if set(r10_cells) != expected_branches or len(common_A) != 1 or len(common_C) != 1:
        raise AssertionError("the r=10 A-degree cover is incomplete or inconsistent")

    result = {
        "schema": "hc4.decimic-nullcone-v6-tangent-highest-all-strata.v1",
        "status": "PASS_EXACT_TANGENT_V6_HIGHEST_RADICAL_CONTAINMENT",
        "claim": (
            "the V6 highest-weight coefficient lies in the radical of the tangent "
            "residual-orbit normal-layer ideal"
        ),
        "characteristic": 0,
        "target_torus_weight": int(target_weight),
        "torus_normalization_verified": True,
        "top_index_cover": list(range(5, 11)),
        "top_cells_5_through_9": top_cells,
        "r10_degree_cover": ["A_zero"] + [f"degree_{degree}" for degree in range(7)],
        "r10_cells": r10_cells,
        "r10_common_A_sha256": next(iter(common_A)),
        "r10_common_C_sha256": next(iter(common_C)),
        "unipotent_used": False,
        "excluded_noncovering_telemetry": [
            "receipts/nullcone-v6-tangent-r5-*",
            "receipts/nullcone-v6-tangent-r6-*",
            "receipts/nullcone-v6-tangent-r7-*",
        ],
        "evidence_sha256": evidence_sha256,
        "source_sha256": {
            "scripts/audit_nullcone_v6_tangent_highest.py": sha256(script_path),
            "scripts/scout_nullcone_v6_tangent_top_stratum.py": sha256(
                campaign / "scripts/scout_nullcone_v6_tangent_top_stratum.py"
            ),
            "scripts/certify_nullcone_v6_tangent_r10_convolution_branch.py": sha256(
                campaign / "scripts/certify_nullcone_v6_tangent_r10_convolution_branch.py"
            ),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero certificate for "
            "one highest-weight cubic covariant coordinate on the tangent normal layer; "
            "the remaining V6 coordinates, V2, quartic families, the secant orbit, "
            "polynomial-level lifting, and HC4 remain open"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
