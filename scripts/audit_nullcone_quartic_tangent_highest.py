#!/usr/bin/env python3
"""Audit an exact tangent quartic highest-coordinate cover."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from certify_nullcone_quartic_tangent_r10_convolution_branch import branch_system
from scout_decimic_nullcone_hsop import digest, f_coefficients
from scout_nullcone_quartic_tangent_top_stratum import FAMILIES, load_family, stratum


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(family: str) -> str:
    return family.lower().replace("_", "-")


def load_exact_unit(path: Path, status: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    calculation = data.get("calculation")
    if data.get("status") != status:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    family_slug = slug(arguments.family)
    target, profile, dictionary_path = load_family(campaign, arguments.family)
    if int(profile["tangent_torus_weight"]) == 0:
        raise AssertionError("the highest-coordinate open cannot be target-normalized")
    if sp.expand(target.subs({f_coefficients[index]: 0 for index in range(5, 11)})) != 0:
        raise AssertionError("the quartic target does not force a top index in 5,...,10")

    evidence_sha256 = {str(dictionary_path.relative_to(campaign)): sha256(dictionary_path)}
    top_cells = {}
    for top_index in range(5, 10):
        relative = f"receipts/nullcone-{family_slug}-tangent-top-r{top_index}-qq-slimgb.json"
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_QUARTIC_HIGHEST_RADICAL_ON_COVER_STRATUM")
        if data.get("family") != arguments.family or data.get("top_index") != top_index:
            raise AssertionError(f"{path.name}: mismatched top cell")
        rebuilt = stratum(arguments.family, top_index)
        if data.get("normal_equation_stream_sha256") != digest(tuple(rebuilt["equations"])):
            raise AssertionError(f"{path.name}: equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(rebuilt["auxiliary"])):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("target_sha256") != digest((rebuilt["target"],)):
            raise AssertionError(f"{path.name}: target does not replay")
        top_cells[str(top_index)] = {"receipt": relative, "algorithm": data["algorithm"]}
        evidence_sha256[relative] = sha256(path)

    r10_paths = {
        "A_zero": ("target", f"receipts/nullcone-{family_slug}-tangent-r10-Azero-qq-slimgb-direct.json"),
        **{
            f"degree_{degree}": (
                "target",
                f"receipts/nullcone-{family_slug}-tangent-r10-degree{degree}-qq-slimgb-direct.json",
            )
            for degree in range(6)
        },
        "degree_6": (
            "top",
            f"receipts/nullcone-{family_slug}-tangent-r10-degree6-qq-slimgb-direct-top-gauge.json",
        ),
    }
    r10_cells = {}
    for branch, (gauge, relative) in r10_paths.items():
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_QUARTIC_TANGENT_R10_CONVOLUTION_BRANCH")
        if data.get("family") != arguments.family or data.get("branch") != branch:
            raise AssertionError(f"{path.name}: mismatched r=10 cell")
        rebuilt = branch_system(arguments.family, branch, gauge)
        if data.get("equation_stream_sha256") != digest(tuple(rebuilt["equations"])):
            raise AssertionError(f"{path.name}: equations do not replay")
        if data.get("auxiliary_stream_sha256") != digest(tuple(rebuilt["auxiliary"])):
            raise AssertionError(f"{path.name}: auxiliary equations do not replay")
        if data.get("A_sha256") != digest((rebuilt["A"],)):
            raise AssertionError(f"{path.name}: A(t) does not replay")
        if data.get("C_sha256") != digest((rebuilt["C"],)):
            raise AssertionError(f"{path.name}: C(t) does not replay")
        if data.get("target_sha256") != digest((rebuilt["top"]["target"],)):
            raise AssertionError(f"{path.name}: target does not replay")
        r10_cells[branch] = {
            "receipt": relative,
            "torus_gauge": gauge,
            "algorithm": data["algorithm"],
            "A_degree": data["A_degree"],
        }
        evidence_sha256[relative] = sha256(path)
    expected = {"A_zero"} | {f"degree_{degree}" for degree in range(7)}
    if set(r10_cells) != expected:
        raise AssertionError("the r=10 degree cover is incomplete")

    result = {
        "schema": "hc4.decimic-nullcone-quartic-tangent-highest-all-strata.v1",
        "status": "PASS_EXACT_TANGENT_QUARTIC_HIGHEST_RADICAL_CONTAINMENT",
        "claim": (
            f"the {arguments.family} highest-weight quartic coefficient lies in the "
            "radical of the tangent residual-orbit normal-layer ideal"
        ),
        "family": arguments.family,
        "family_order": profile["order"],
        "characteristic": 0,
        "target_torus_weight": profile["tangent_torus_weight"],
        "top_index_cover": list(range(5, 11)),
        "top_cells_5_through_9": top_cells,
        "r10_degree_cover": ["A_zero"] + [f"degree_{degree}" for degree in range(7)],
        "r10_cells": r10_cells,
        "degree_6_top_gauge": {
            "normalized_coefficient": "f10",
            "coefficient_torus_weight": -16,
            "target_localized": True,
        },
        "unipotent_used": False,
        "evidence_sha256": evidence_sha256,
        "source_sha256": {
            "scripts/audit_nullcone_quartic_tangent_highest.py": sha256(script_path),
            "scripts/scout_nullcone_quartic_tangent_top_stratum.py": sha256(
                campaign / "scripts/scout_nullcone_quartic_tangent_top_stratum.py"
            ),
            "scripts/certify_nullcone_quartic_tangent_r10_convolution_branch.py": sha256(
                campaign / "scripts/certify_nullcone_quartic_tangent_r10_convolution_branch.py"
            ),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero highest-coordinate "
            "certificate for one quartic family on the tangent normal layer; "
            "stabilizer propagation, other quartic families, secant, and HC4 remain separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output or Path(
        f"receipts/nullcone-{family_slug}-tangent-highest-all-strata.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
