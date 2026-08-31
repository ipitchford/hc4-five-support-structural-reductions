#!/usr/bin/env python3
"""Supervise and promote the frozen sparse-four p^2 lift."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-sparse4-two-digit-lift-implementation-freeze.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_SPARSE4_TWO_DIGIT_LIFT_IMPLEMENTATION_FREEZE", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical sparse-four output exists")
    artifact_stage = CAMPAIGN / "artifacts/staging" / f"p181-sparse4-two-digit-{arguments.run_id}"
    telemetry_stage = CAMPAIGN / "artifacts/staging" / f"p181-sparse4-two-digit-telemetry-{arguments.run_id}"
    policy = freeze["policy"]
    terminal = {"schema": "hc4.third-colon-p181-sparse4-two-digit-lift-terminal.v1", "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)}}
    try:
        telemetry = base.supervise(
            ["/usr/bin/python3", str(CAMPAIGN / "scripts/produce_p181_sparse4_two_digit_lift.py"), "--output-dir", str(artifact_stage)],
            telemetry_stage, int(policy["wall_seconds_maximum"]), int(policy["rss_bytes_maximum"]),
        )
        external = telemetry.get("external_time") or {}
        compliant = not telemetry["rss_breach_killed"] and external.get("real_seconds", 10**9) <= policy["wall_seconds_maximum"] and external.get("maximum_rss_bytes", 10**12) <= policy["rss_bytes_maximum"] and external.get("process_swaps", 1) == 0
        producer = json.loads((artifact_stage / "producer.json").read_text(encoding="utf-8")) if (artifact_stage / "producer.json").exists() else None
        producer_status = producer.get("status") if producer else None
        allowed = {"STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE", "PASS_P181_SPARSE4_TWO_DIGIT_LIFT", "PASS_P181_SPARSE4_TWO_DIGIT_EXACT_RATIONAL_REPLAY"}
        if not compliant:
            status = "STOP_P181_SPARSE4_TWO_DIGIT_RESOURCE"
        elif producer_status in allowed and telemetry["return_code"] in (0, 4):
            status = producer_status
        else:
            status = "FAIL_P181_SPARSE4_TWO_DIGIT_INTEGRITY"
        terminal.update({"status": status, "producer_status": producer_status, "telemetry": telemetry, "claim_boundary": "A two-digit PASS is finite p-adic evidence for four fixed canonical residual sections. It is not a general QQ identity, colon, saturation, secant, nullcone, or HC4 theorem."})
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if status.startswith("PASS_") else 4 if status.startswith("STOP_") else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_SPARSE4_TWO_DIGIT_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): base.tree_hashes(path) for path in (artifact_stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
