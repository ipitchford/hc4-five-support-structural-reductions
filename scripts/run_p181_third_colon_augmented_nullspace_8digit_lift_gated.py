#!/usr/bin/env python3
"""Supervise and promote the frozen eight-digit augmented-nullspace lift."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-8digit-lift-implementation-freeze-v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_IMPLEMENTATION_FREEZE_V2", "implementation freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical eight-digit output exists")
    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"p181-augmented-nullspace-8digit-lift-{arguments.run_id}"
    telemetry_stage = staging / f"p181-augmented-nullspace-8digit-lift-telemetry-{arguments.run_id}"
    policy = freeze["policy"]
    terminal: dict[str, object] = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-8digit-lift-terminal.v1",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)},
    }
    try:
        telemetry = base.supervise(
            [
                "/usr/bin/python3",
                str(CAMPAIGN / "scripts/lift_p181_third_colon_augmented_nullspace_8digits.py"),
                "--output-dir", str(artifact_stage),
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
        lift_path = artifact_stage / "lift.json"
        lift = json.loads(lift_path.read_text(encoding="utf-8")) if lift_path.exists() else None
        if not resource_compliant:
            status = "STOP_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_RESOURCE"
        elif (
            telemetry["return_code"] == 4
            and lift is not None
            and lift.get("status") == "STOP_P181_LIFT_CORRECTION_OUTSIDE_COLUMN_SPACE"
        ):
            status = lift["status"]
        elif (
            telemetry["return_code"] == 0
            and lift is not None
            and lift.get("status") in {
                "PASS_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT",
                "PASS_P181_8DIGIT_LIFT_AND_EXACT_RATIONAL_SYSTEM_REPLAY",
            }
            and len(lift.get("corrections", [])) == 7
            and all(record.get("divisibility_mismatches") == 0 for record in lift["corrections"])
            and lift.get("terminal_modulus") == "1151936657823500641"
        ):
            status = lift["status"]
        else:
            status = "FAIL_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_INTEGRITY"
        terminal.update(
            {
                "status": status,
                "producer_status": lift.get("status") if lift else None,
                "completed_corrections": len(lift.get("corrections", [])) if lift else 0,
                "telemetry": telemetry,
                "declarations": {
                    "fixed_p181": True,
                    "maximum_total_digits": 8,
                    "quarantined_dixon_bundle_not_read": True,
                    "no_ninth_digit": True,
                },
                "claim_boundary": (
                    "A PASS without exact rational replay is finite eight-digit p-adic evidence only. Any exact "
                    "integral-system replay still requires independent symbolic replay; no colon, saturation, "
                    "secant, nullcone, or HC4 theorem follows."
                ),
            }
        )
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {
            "artifact": base.tree_hashes(outputs["artifact"]),
            "telemetry": base.tree_hashes(outputs["telemetry"]),
        }
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if status.startswith("PASS_") else 4 if status == "STOP_P181_LIFT_CORRECTION_OUTSIDE_COLUMN_SPACE" else 3 if status.endswith("_RESOURCE") else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_AUGMENTED_NULLSPACE_8DIGIT_LIFT_INTEGRITY")
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
