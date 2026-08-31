#!/usr/bin/env python3
"""Audit the exact tangent j2 certificate across all six first-jet strata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


R10_BRANCH_FILES = {
    "degree_6": "receipts/hsop-j2-tangent-r10-degree_6-slimgb-exact.json",
    "degree_5": "receipts/hsop-j2-tangent-r10-degree_5-modstd-exact.json",
    "degree_4": "receipts/hsop-j2-tangent-r10-degree_4-slimgb-exact.json",
    "degree_3": "receipts/hsop-j2-tangent-r10-degree_3-slimgb-exact.json",
    "A_zero": "receipts/hsop-j2-tangent-r10-A_zero-slimgb-exact.json",
}


def load_exact_unit(path: Path, expected_status: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != expected_status:
        raise AssertionError(f"{path.name} does not have status {expected_status}")
    calculation = data.get("calculation")
    if not isinstance(calculation, dict) or not calculation.get("is_unit"):
        raise AssertionError(f"{path.name} is not an exact unit calculation")
    if calculation.get("timed_out") or calculation.get("return_code") != 0:
        raise AssertionError(f"{path.name} did not terminate cleanly")
    if calculation.get("unit_remainder") != "0" or calculation.get("basis_size") != "1":
        raise AssertionError(f"{path.name} does not display a one-element unit basis")
    if "BASIS_FIRST\n1\n" not in calculation.get("stdout_tail", ""):
        raise AssertionError(f"{path.name} does not display basis element 1")
    if data.get("characteristic", 0) != 0:
        raise AssertionError(f"{path.name} is not a characteristic-zero receipt")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-all-strata.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent

    torus_path = campaign / "receipts/residual-orbit-torus.json"
    torus = json.loads(torus_path.read_text(encoding="utf-8"))
    if torus.get("status") != "PASS":
        raise AssertionError("the residual-orbit torus receipt is not passing")
    expected_indices = list(range(5, 11))
    if torus["tangent_unipotent"]["exhaustive_first_nonzero_indices_under_j2_nonzero"] != expected_indices:
        raise AssertionError("the tangent first-jet cover is not exactly r=5,...,10")

    stratum_files = {
        5: "receipts/hsop-j2-tangent-r5-compatibility-exact.json",
        6: "receipts/hsop-j2-tangent-r6-coefficient-slice-exact.json",
        7: "receipts/hsop-j2-tangent-r7-coefficient-slice-exact.json",
        8: "receipts/hsop-j2-tangent-r8-coefficient-slice-exact.json",
        9: "receipts/hsop-j2-tangent-r9-coefficient-slice-exact.json",
    }
    stratum_data = {}
    evidence_sha256 = {}
    for top_index, relative in stratum_files.items():
        path = campaign / relative
        expected_status = (
            "PASS_EXACT_TANGENT_R5_EMPTY"
            if top_index == 5
            else "PASS_EXACT_TANGENT_STRATUM_EMPTY"
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != expected_status or data.get("top_index") != top_index:
            raise AssertionError(f"the r={top_index} receipt is not passing")
        if top_index == 5:
            if not all(
                branch["exact_unit"]
                and branch["calculation"]["basis_size"] == "1"
                and "BASIS_FIRST\n1\n" in branch["calculation"]["stdout_tail"]
                for branch in data["branch_results"].values()
            ):
                raise AssertionError("an r=5 compatibility branch is not exact unit")
        else:
            load_exact_unit(path, expected_status)
        stratum_data[str(top_index)] = {
            "receipt": relative,
            "status": expected_status,
            "algorithm": (
                "rank-stratified Singular qstd"
                if top_index == 5
                else data["algorithm"]
            ),
        }
        evidence_sha256[relative] = hashlib.sha256(path.read_bytes()).hexdigest()

    r10_data = {}
    common_A = set()
    common_C = set()
    for branch_name, relative in R10_BRANCH_FILES.items():
        path = campaign / relative
        data = load_exact_unit(path, "PASS_EXACT_TANGENT_R10_DEGREE_BRANCH_UNIT")
        if data.get("branch") != branch_name or data.get("top_index") != 10:
            raise AssertionError(f"the {branch_name} receipt is mismatched")
        common_A.add(data["A_sha256"])
        common_C.add(data["C_sha256"])
        r10_data[branch_name] = {
            "receipt": relative,
            "algorithm": data["algorithm"],
            "A_degree": data["A_degree"],
        }
        evidence_sha256[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    if len(common_A) != 1 or len(common_C) != 1:
        raise AssertionError("the r=10 branch receipts do not share one A,C system")
    if set(r10_data) != set(R10_BRANCH_FILES):
        raise AssertionError("the r=10 degree cover is incomplete")

    result = {
        "schema": "hc4-decimic-j2-tangent-all-strata-audit-v1",
        "status": "PASS_EXACT_TANGENT_J2_RADICAL_CONTAINMENT",
        "claim": "j2 lies in the radical of the tangent residual-orbit normal-layer ideal",
        "characteristic": 0,
        "first_nonzero_jet_indices": expected_indices,
        "strata_5_through_9": stratum_data,
        "stratum_10_degree_branches": r10_data,
        "r10_common_A_sha256": next(iter(common_A)),
        "r10_common_C_sha256": next(iter(common_C)),
        "torus_and_unipotent_cover_verified": True,
        "evidence_sha256": evidence_sha256,
        "source_sha256": {
            "scripts/audit_j2_tangent_all_strata.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                torus_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this is an exact computer-assisted tangent-orbit j2 certificate; "
            "the secant j2 containment, the other seven HSOP invariants, the full "
            "nullcone containment, and HC4 remain open"
        ),
    }
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
