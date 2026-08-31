#!/usr/bin/env python3
"""Supervise and promote the frozen p181^72 residual-114 chart attempt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-residual-114-p181-72digit-implementation-freeze.json"
EXACT_STATUS = "PASS_P181_72DIGIT_EXACT_RESIDUAL_114_RATIONAL_CHART"
INCOMPLETE_STATUS = "PASS_P181_72DIGIT_INCOMPLETE_RESIDUAL_114_HEIGHT_BOUND"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_RESIDUAL_114_P181_72DIGIT_IMPLEMENTATION_FREEZE", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical residual-114 p181^72 output exists")
    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"residual-114-p181-72digit-{arguments.run_id}"
    telemetry_stage = staging / f"residual-114-p181-72digit-telemetry-{arguments.run_id}"
    policy = freeze["policy"]
    terminal: dict[str, object] = {
        "schema": "hc4.third-colon-residual-114-p181-72digit-terminal.v1",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)},
    }
    try:
        telemetry = base.supervise(
            [
                "/usr/bin/python3",
                str(CAMPAIGN / "scripts/lift_p181_residual_114_quotient_chart_to_72digits.py"),
                "--output-dir",
                str(artifact_stage),
            ],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        external = telemetry.get("external_time") or {}
        compliant = (
            not telemetry["rss_breach_killed"]
            and external.get("real_seconds", policy["wall_seconds_maximum"] + 1) <= policy["wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", policy["rss_bytes_maximum"] + 1) <= policy["rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
        )
        receipt_path = artifact_stage / "lift.json"
        producer = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
        status = "FAIL_RESIDUAL_114_P181_72DIGIT_INTEGRITY"
        if not compliant:
            status = "STOP_RESIDUAL_114_P181_72DIGIT_RESOURCE"
        elif telemetry["return_code"] == 0 and producer is not None:
            producer_status = producer.get("status")
            corrections_ok = (
                len(producer.get("corrections", [])) == 71
                and [record.get("digit_index") for record in producer["corrections"]] == list(range(1, 72))
                and all(record.get("modular_mismatches") == 0 and record.get("divisibility_mismatches") == 0 for record in producer["corrections"])
            )
            terminal_ok = (
                producer.get("terminal", {}).get("digits") == 72
                and producer.get("terminal", {}).get("integer_invariant_mismatches") == 0
            )
            exact_replay = producer.get("exact_replay") or {}
            reductions = exact_replay.get("five_fibre_reductions") or {}
            exact_ok = (
                producer_status == EXACT_STATUS
                and producer.get("reconstruction", {}).get("unresolved") == 0
                and exact_replay.get("exact_scalar_mismatches") == 0
                and set(reductions) == {"181", "173", "197", "2147483647", "2147483629"}
                and all(record.get("denominator_is_unit") and record.get("mismatch_count") == 0 for record in reductions.values())
                and producer.get("rational_chart", {}).get("path") == "rational_chart.json"
            )
            incomplete_ok = (
                producer_status == INCOMPLETE_STATUS
                and (
                    producer.get("reconstruction", {}).get("unresolved", 0) > 0
                    or exact_replay.get("exact_scalar_mismatches", 0) > 0
                    or any(not record.get("denominator_is_unit") or record.get("mismatch_count") != 0 for record in reductions.values())
                )
            )
            if corrections_ok and terminal_ok and (exact_ok or incomplete_ok):
                status = producer_status
        terminal.update({
            "status": status,
            "producer_status": producer.get("status") if producer else None,
            "telemetry": telemetry,
            "claim_boundary": "An exact PASS proves only B*T=C for the fixed rational Koszul quotient chart. An incomplete PASS is only a 181^72 height bound. Neither proves QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4.",
        })
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {
            "artifact": base.tree_hashes(outputs["artifact"]),
            "telemetry": base.tree_hashes(outputs["telemetry"]),
        }
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if status in {EXACT_STATUS, INCOMPLETE_STATUS} else 3 if status.endswith("_RESOURCE") else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_RESIDUAL_114_P181_72DIGIT_INTEGRITY")
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
