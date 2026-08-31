#!/usr/bin/env python3
"""Supervise the frozen full-size explicit-target augmented-nullspace solve."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-explicit-target-solve-implementation-freeze.json"


def parse_driver_stdout(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    try:
        return json.loads(lines[0])
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(
        freeze.get("status") == "PASS_P181_EXPLICIT_TARGET_SOLVE_IMPLEMENTATION_FREEZE",
        "implementation freeze absent",
    )
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical explicit-target output exists")

    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"p181-explicit-target-solve-{arguments.run_id}"
    telemetry_stage = staging / f"p181-explicit-target-solve-telemetry-{arguments.run_id}"
    artifact_stage.mkdir(parents=True, exist_ok=False)
    solution = artifact_stage / "solution_mod181.u8"
    policy = freeze["policy"]
    terminal: dict[str, object] = {
        "schema": "hc4.decimic-j2-secant-r10-p181-explicit-target-augmented-nullspace-solve.v1",
        "implementation_freeze": {
            "path": str(FREEZE.relative_to(CAMPAIGN)),
            "sha256": base.file_hash(FREEZE),
        },
    }
    try:
        driver_path = CAMPAIGN / "artifacts/bin/linbox_augmented_nullspace_mod181_target_driver"
        csr_path = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
        rhs_path = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-rhs-v1/target_rhs_mod181.u8"
        telemetry = base.supervise(
            [
                str(driver_path),
                "--csr", str(csr_path),
                "--rhs", str(rhs_path),
                "--solution-output", str(solution),
            ],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        external = telemetry.get("external_time") or {}
        resource_compliant = (
            not telemetry["rss_breach_killed"]
            and external.get("real_seconds", policy["wall_seconds_maximum"] + 1) <= policy["wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", policy["rss_bytes_maximum"] + 1) <= policy["rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
        )
        driver = parse_driver_stdout(telemetry_stage / "benchmark.stdout.txt")
        if not resource_compliant:
            status = "STOP_P181_EXPLICIT_TARGET_SOLVE_RESOURCE"
        elif (
            telemetry["return_code"] == 4
            and driver is not None
            and driver.get("status") == "STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD181"
            and driver.get("mode") == "explicit_target"
            and driver.get("augmented_nullity") == 0
            and not solution.exists()
        ):
            status = "STOP_P181_EXPLICIT_TARGET_OUTSIDE_COLUMN_SPACE"
        elif (
            telemetry["return_code"] == 0
            and driver is not None
            and driver.get("status") == "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_EXPLICIT_TARGET_SOLVE"
            and driver.get("mode") == "explicit_target"
            and driver.get("rows") == 85_651
            and driver.get("columns") == 35_881
            and driver.get("coefficient_nonzeros") == 1_354_540
            and driver.get("augmented_nullity") == 1
            and driver.get("replay_mismatches") == 0
            and int(driver.get("last_null_coordinate", 0)) in range(1, 181)
            and solution.is_file()
            and solution.stat().st_size == 35_881
            and all(value < 181 for value in solution.read_bytes())
        ):
            status = "PASS_P181_EXPLICIT_TARGET_AUGMENTED_NULLSPACE_SOLVE"
        else:
            status = "FAIL_P181_EXPLICIT_TARGET_SOLVE_INTEGRITY"

        terminal.update(
            {
                "status": status,
                "driver": driver,
                "telemetry": telemetry,
                "solution": {
                    "path": str(solution.relative_to(CAMPAIGN)) if solution.exists() else None,
                    "bytes": solution.stat().st_size if solution.exists() else None,
                    "sha256": base.file_hash(solution) if solution.exists() else None,
                },
                "inputs": {
                    "csr_sha256": base.file_hash(csr_path),
                    "rhs_sha256": base.file_hash(rhs_path),
                },
                "declarations": {
                    "explicit_Mh3_target_used": True,
                    "existing_multiplier_or_solution_not_read": True,
                    "quarantined_dixon_data_not_read": True,
                    "no_mod181_squared": True,
                    "no_rational_reconstruction": True,
                },
                "claim_boundary": (
                    "A PASS proves only the explicit M*h3 identity over GF(181) in the fixed zero-free gauge. "
                    "It is not a QQ identity, p-adic lift, colon or saturation equality, secant closure, "
                    "nullcone containment, or HC4 theorem."
                ),
            }
        )
        (artifact_stage / "scout.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {
            "artifact": base.tree_hashes(outputs["artifact"]),
            "telemetry": base.tree_hashes(outputs["telemetry"]),
        }
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        if status == "PASS_P181_EXPLICIT_TARGET_AUGMENTED_NULLSPACE_SOLVE":
            return 0
        if status == "STOP_P181_EXPLICIT_TARGET_OUTSIDE_COLUMN_SPACE":
            return 4
        if status == "STOP_P181_EXPLICIT_TARGET_SOLVE_RESOURCE":
            return 3
        return 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_EXPLICIT_TARGET_SOLVE_INTEGRITY")
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
