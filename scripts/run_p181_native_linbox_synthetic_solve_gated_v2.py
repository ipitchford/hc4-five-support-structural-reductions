#!/usr/bin/env python3
"""Supervise the amended native LinBox synthetic-known-vector solve scout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-native-linbox-synthetic-solve-implementation-freeze-v2.json"
EXPECTED_SOLUTION_SHA256 = "ebcf2e6338e5eb81ba7b9fd58f8c9366a8b5ddb48c27cef7fcd34e9c27663d28"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T002")
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(
        freeze.get("status") == "PASS_P181_NATIVE_LINBOX_SYNTHETIC_SOLVE_IMPLEMENTATION_FREEZE_V2",
        "v2 implementation freeze absent",
    )
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical v2 synthetic-solve output already exists")
    staging_root = CAMPAIGN / "artifacts/staging"
    output_stage = staging_root / f"p181-native-linbox-synthetic-solve-v2-{args.run_id}"
    telemetry_stage = staging_root / f"p181-native-linbox-synthetic-solve-v2-telemetry-{args.run_id}"
    output_stage.mkdir(parents=True, exist_ok=False)
    solution = output_stage / "solution.u8"
    terminal = {
        "schema": "hc4.decimic-j2-secant-r10-p181-native-linbox-synthetic-solve.v2",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)},
        "supersedes_only_as_experiment": {
            "path": "receipts/hsop-j2-secant-r10-p181-native-linbox-synthetic-solve-v1.json",
            "sha256": "575fe96b1e176ff02f927a279908d55152f5a1868a5d154e6fd86c9459318581",
            "status": "FAIL_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE_INTEGRITY",
        },
    }
    try:
        policy = freeze["policy"]
        telemetry = base.supervise(
            [
                str(CAMPAIGN / "artifacts/bin/linbox_sparse_mod181_solve_driver"),
                "--csr",
                str(CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"),
                "--solution-output",
                str(solution),
            ],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        stdout_path = telemetry_stage / "benchmark.stdout.txt"
        lines = [line for line in stdout_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        base.require(len(lines) == 1, "native driver emitted ambiguous stdout")
        driver = json.loads(lines[0])
        external = telemetry.get("external_time") or {}
        resources_pass = (
            telemetry["return_code"] == 0
            and not telemetry["rss_breach_killed"]
            and external.get("real_seconds", policy["wall_seconds_maximum"] + 1) <= policy["wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", policy["rss_bytes_maximum"] + 1) <= policy["rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
        )
        integrity_pass = (
            driver.get("status") == "PASS_LINBOX_SPARSE_MOD181_EXPLICIT_SOLVE"
            and driver.get("mode") == "synthetic_known_solution"
            and driver.get("rows") == 85_651
            and driver.get("columns") == 35_881
            and driver.get("nonzeros") == 1_354_540
            and driver.get("replay_mismatches") == 0
            and driver.get("known_solution_mismatches") == 0
            and solution.is_file()
            and solution.stat().st_size == 35_881
            and base.file_hash(solution) == EXPECTED_SOLUTION_SHA256
        )
        if not resources_pass:
            status = "STOP_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE_RESOURCE"
        elif not integrity_pass:
            status = "FAIL_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE_INTEGRITY"
        else:
            status = "PASS_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE"
        terminal.update({
            "status": status,
            "driver": driver,
            "telemetry": telemetry,
            "solution": {
                "bytes": solution.stat().st_size if solution.exists() else None,
                "sha256": base.file_hash(solution) if solution.exists() else None,
            },
            "declarations": {
                "synthetic_rhs_only": True,
                "third_candidate_not_read": True,
                "target_rhs_not_read": True,
                "no_target_membership_test": True,
                "no_mod181_squared": True,
                "no_p_adic_digit": True,
                "v1_resource_gates_unchanged": True,
            },
            "claim_boundary": "A PASS certifies only reusable native explicit-solve capability on a synthetic known-vector RHS for the actual coefficient matrix. It proves no target membership, QQ identity, colon, saturation, secant closure, nullcone containment, or HC4.",
        })
        base.require(status == "PASS_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE", f"registered terminal: {status}")
        (output_stage / "scout.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.rename(output_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0
    except Exception as error:
        terminal.setdefault("status", "FAIL_ACTUAL_COEFFICIENT_NATIVE_LINBOX_SYNTHETIC_SOLVE_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {
            str(path.relative_to(CAMPAIGN)): base.tree_hashes(path)
            for path in (output_stage, telemetry_stage)
            if path.exists()
        }
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

