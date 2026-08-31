#!/usr/bin/env python3
"""Run the frozen staged augmented-nullspace synthetic solve experiment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-implementation-freeze.json"
STAGES = (4096, 8192, 16384, 35881)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(
        freeze.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_IMPLEMENTATION_FREEZE",
        "implementation freeze absent",
    )
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical augmented-nullspace output already exists")

    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"p181-augmented-nullspace-synthetic-solve-{args.run_id}"
    telemetry_stage = staging / f"p181-augmented-nullspace-synthetic-solve-telemetry-{args.run_id}"
    artifact_stage.mkdir(parents=True, exist_ok=False)
    telemetry_stage.mkdir(parents=True, exist_ok=False)
    terminal = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-synthetic-solve.v1",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)},
        "stage_order": list(STAGES),
        "stages": [],
    }

    try:
        driver_path = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_solve_driver"
        csr_path = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
        for columns in STAGES:
            spec = freeze["stages"][str(columns)]
            solution = artifact_stage / f"solution-{columns}.u8"
            stage_telemetry_path = telemetry_stage / f"columns-{columns}"
            telemetry = base.supervise(
                [
                    str(driver_path),
                    "--csr", str(csr_path),
                    "--columns", str(columns),
                    "--solution-output", str(solution),
                ],
                stage_telemetry_path,
                int(spec["wall_seconds_maximum"]),
                int(spec["rss_bytes_maximum"]),
            )
            external = telemetry.get("external_time") or {}
            resources_pass = (
                telemetry["return_code"] == 0
                and not telemetry["rss_breach_killed"]
                and external.get("real_seconds", spec["wall_seconds_maximum"] + 1) <= spec["wall_seconds_maximum"]
                and external.get("maximum_rss_bytes", spec["rss_bytes_maximum"] + 1) <= spec["rss_bytes_maximum"]
                and external.get("process_swaps", 1) == 0
            )
            stage_record = {"columns": columns, "telemetry": telemetry}
            if not resources_pass:
                stage_record["status"] = "STOP_RESOURCE"
                terminal["stages"].append(stage_record)
                terminal["status"] = "STOP_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_RESOURCE"
                terminal["stopped_at_columns"] = columns
                break

            stdout_path = stage_telemetry_path / "benchmark.stdout.txt"
            lines = [line for line in stdout_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            base.require(len(lines) == 1, f"ambiguous native stdout at {columns} columns")
            driver = json.loads(lines[0])
            integrity_pass = (
                driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_SYNTHETIC_SOLVE"
                and driver.get("mode") == "synthetic_known_solution"
                and driver.get("rows") == 85_651
                and driver.get("columns") == columns
                and driver.get("coefficient_nonzeros") == spec["coefficient_nonzeros"]
                and driver.get("replay_mismatches") == 0
                and driver.get("known_solution_mismatches") == 0
                and int(driver.get("last_null_coordinate", 0)) in range(1, 181)
                and solution.is_file()
                and solution.stat().st_size == columns
                and base.file_hash(solution) == spec["expected_solution_sha256"]
            )
            stage_record.update({
                "status": "PASS" if integrity_pass else "FAIL_INTEGRITY",
                "driver": driver,
                "solution": {
                    "path": str(solution.relative_to(CAMPAIGN)),
                    "bytes": solution.stat().st_size if solution.exists() else None,
                    "sha256": base.file_hash(solution) if solution.exists() else None,
                },
            })
            terminal["stages"].append(stage_record)
            if not integrity_pass:
                terminal["status"] = "FAIL_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_INTEGRITY"
                terminal["stopped_at_columns"] = columns
                break
        else:
            terminal["status"] = "PASS_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_SCALING"

        terminal["declarations"] = {
            "synthetic_rhs_only": True,
            "third_candidate_not_read": True,
            "target_rhs_not_read": True,
            "existing_multiplier_vectors_not_read": True,
            "no_target_membership_test": True,
            "no_mod181_squared": True,
            "no_p_adic_digit": True,
        }
        terminal["claim_boundary"] = "A full PASS certifies only reusable exact explicit-solve capability for synthetic known-vector right-hand sides on the actual coefficient map. It proves no target membership, QQ identity, p-adic digit, colon, saturation, secant closure, nullcone containment, or HC4."
        base.require(
            terminal["status"] == "PASS_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_SCALING",
            f"registered terminal: {terminal['status']}",
        )
        (artifact_stage / "scout.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0
    except Exception as error:
        terminal.setdefault("status", "FAIL_ACTUAL_COEFFICIENT_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {
            str(path.relative_to(CAMPAIGN)): base.tree_hashes(path)
            for path in (artifact_stage, telemetry_stage)
            if path.exists()
        }
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

