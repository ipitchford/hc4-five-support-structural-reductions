#!/usr/bin/env python3
"""Audit the exact tangent V2-highest nullcone certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from certify_nullcone_v2_tangent_r10_convolution_branch import branch_system
from scout_decimic_nullcone_hsop import digest, f_coefficients
from scout_nullcone_cubic_families import raw_coefficient_family
from scout_nullcone_v2_tangent_top_stratum import stratum


TOP_FILES = {
    index: f"receipts/nullcone-v2-tangent-top-r{index}-qq-slimgb.json"
    for index in range(5, 10)
}

R10_FILES = {
    "A_zero": ("inverse", "receipts/nullcone-v2-tangent-r10-Azero-qq-slimgb-direct.json"),
    "degree_0": ("inverse", "receipts/nullcone-v2-tangent-r10-degree0-qq-slimgb-direct.json"),
    "degree_1": ("inverse", "receipts/nullcone-v2-tangent-r10-degree1-qq-slimgb-direct.json"),
    "degree_2": ("inverse", "receipts/nullcone-v2-tangent-r10-degree2-qq-slimgb-direct.json"),
    "degree_3": ("inverse", "receipts/nullcone-v2-tangent-r10-degree3-qq-slimgb-direct.json"),
    "degree_4": ("inverse", "receipts/nullcone-v2-tangent-r10-degree4-qq-slimgb-direct.json"),
    "degree_5": ("inverse", "receipts/nullcone-v2-tangent-r10-degree5-qq-slimgb-direct.json"),
    "degree_6": (
        "normalize",
        "receipts/nullcone-v2-tangent-r10-degree6-qq-slimgb-direct-normalize.json",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exact_unit(path: Path, expected_status: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    calculation = data.get("calculation")
    if data.get("status") != expected_status:
        raise AssertionError(f"{path.name}: unexpected status")
    if data.get("characteristic") != 0 or data.get("unipotent_used") is not False:
        raise AssertionError(f"{path.name}: invalid characteristic or unipotent use")
    if not isinstance(calculation, dict) or (
        not calculation.get("is_unit")
        or calculation.get("timed_out")
        or calculation.get("return_code") != 0
        or calculation.get("basis_size") != "1"
        or calculation.get("unit_remainder") != "0"
        or "BASIS_SIZE\n1\n" not in calculation.get("stdout_tail", "")
    ):
        raise AssertionError(f"{path.name}: not a clean exact unit")
    return data


def torus_weight(expression: sp.Expr, weights: list[int]) -> int:
    weight_map = dict(zip(f_coefficients, weights, strict=True))
    values = {
        sum(
            term.as_powers_dict().get(symbol, 0) * weight_map[symbol]
            for symbol in f_coefficients
        )
        for term in sp.Add.make_args(sp.expand(expression))
    }
    if len(values) != 1:
        raise AssertionError(f"target is not torus homogeneous: {values}")
    return int(next(iter(values)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v2-tangent-highest-all-strata.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent

    torus_path = campaign / "receipts/residual-orbit-torus.json"
    torus = json.loads(torus_path.read_text(encoding="utf-8"))
    if torus.get("status") != "PASS":
        raise AssertionError("residual-orbit torus audit is not passing")
    weights = torus["tangent"]["coefficient_weights"]
    target = raw_coefficient_family("V2")
    target_weight = torus_weight(target, weights)
    if target_weight != 0 or weights[10] != -16:
        raise AssertionError("the V2/f10 torus weights do not support the mixed cover")
    if sp.expand(target.subs({f_coefficients[index]: 0 for index in range(5, 11)})) != 0:
        raise AssertionError("V2 does not force a top index in 5,...,10")

    evidence_sha256 = {"receipts/residual-orbit-torus.json": sha256(torus_path)}
    top_cells: dict[str, object] = {}
    for top_index, relative in TOP_FILES.items():
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_V2_HIGHEST_RADICAL_ON_COVER_STRATUM")
        if data.get("top_index") != top_index or data.get("family") != "V2":
            raise AssertionError(f"{path.name}: mismatched top cell")
        equations, auxiliary, _, _, reduced_target, _, _ = stratum(top_index)
        if data.get("normal_equation_stream_sha256") != digest(tuple(equations)):
            raise AssertionError(f"{path.name}: normal equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(auxiliary)):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("target_sha256") != digest((reduced_target,)):
            raise AssertionError(f"{path.name}: target does not replay")
        top_cells[str(top_index)] = {
            "receipt": relative,
            "algorithm": data["algorithm"],
            "target_sha256": data["target_sha256"],
        }
        evidence_sha256[relative] = sha256(path)

    r10_cells: dict[str, object] = {}
    for branch, (top_mode, relative) in R10_FILES.items():
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_V2_TANGENT_R10_CONVOLUTION_BRANCH")
        if data.get("branch") != branch or data.get("top_index") != 10:
            raise AssertionError(f"{path.name}: mismatched r=10 branch")
        rebuilt = branch_system(branch, top_mode)
        if data.get("equation_stream_sha256") != digest(tuple(rebuilt["equations"])):
            raise AssertionError(f"{path.name}: equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(rebuilt["auxiliary"])):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("A_sha256") != digest((rebuilt["A"],)):
            raise AssertionError(f"{path.name}: A(t) does not replay")
        if data.get("C_sha256") != digest((rebuilt["C"],)):
            raise AssertionError(f"{path.name}: C(t) does not replay")
        if data.get("target_sha256") != digest((rebuilt["target"],)):
            raise AssertionError(f"{path.name}: target does not replay")
        if top_mode == "normalize" and branch != "degree_6":
            raise AssertionError("top normalization escaped the sole degree-six branch")
        r10_cells[branch] = {
            "receipt": relative,
            "top_mode": top_mode,
            "algorithm": data["algorithm"],
            "A_degree": data["A_degree"],
            "equation_stream_sha256": data["equation_stream_sha256"],
        }
        evidence_sha256[relative] = sha256(path)
    expected = {"A_zero"} | {f"degree_{degree}" for degree in range(7)}
    if set(r10_cells) != expected:
        raise AssertionError("the r=10 A-degree cover is incomplete")

    result = {
        "schema": "hc4.decimic-nullcone-v2-tangent-highest-all-strata.v1",
        "status": "PASS_EXACT_TANGENT_V2_HIGHEST_RADICAL_CONTAINMENT",
        "claim": (
            "the V2 highest-weight coefficient lies in the radical of the tangent "
            "residual-orbit normal-layer ideal"
        ),
        "characteristic": 0,
        "target_torus_weight": target_weight,
        "target_open_localized_not_normalized": True,
        "top_index_cover": list(range(5, 11)),
        "top_cells_5_through_9": top_cells,
        "r10_degree_cover": ["A_zero"] + [f"degree_{degree}" for degree in range(7)],
        "r10_cells": r10_cells,
        "degree_6_top_normalization": {
            "coefficient": "f10",
            "torus_weight": weights[10],
            "V2_weight": target_weight,
            "valid_over_algebraic_closure": True,
        },
        "unipotent_used": False,
        "evidence_sha256": evidence_sha256,
        "source_sha256": {
            "scripts/audit_nullcone_v2_tangent_highest.py": sha256(script_path),
            "scripts/scout_nullcone_v2_tangent_top_stratum.py": sha256(
                campaign / "scripts/scout_nullcone_v2_tangent_top_stratum.py"
            ),
            "scripts/certify_nullcone_v2_tangent_r10_convolution_branch.py": sha256(
                campaign / "scripts/certify_nullcone_v2_tangent_r10_convolution_branch.py"
            ),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero certificate for "
            "one highest-weight cubic V2 coordinate on the tangent normal layer; "
            "stabilizer propagation, quartic families, the secant orbit, polynomial-"
            "level lifting, and HC4 remain separate"
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
