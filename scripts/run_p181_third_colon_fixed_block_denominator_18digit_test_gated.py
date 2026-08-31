#!/usr/bin/env python3
"""Supervise the frozen two-digit fixed-denominator falsification test."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-fixed-block-denominator-18digit-test-implementation-freeze.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_FIXED_BLOCK_DENOMINATOR_18DIGIT_TEST_IMPLEMENTATION_FREEZE", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical 18-digit test output exists")
    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"p181-fixed-block-denominator-18digit-test-{arguments.run_id}"
    telemetry_stage = staging / f"p181-fixed-block-denominator-18digit-test-telemetry-{arguments.run_id}"
    policy = freeze["policy"]
    terminal: dict[str, object] = {"schema": "hc4.decimic-j2-secant-r10-p181-fixed-block-denominator-18digit-test-terminal.v1", "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)}}
    try:
        telemetry = base.supervise(["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/test_p181_third_colon_fixed_block_denominators_at_18digits.py"), "--output-dir", str(artifact_stage)], telemetry_stage, int(policy["wall_seconds_maximum"]), int(policy["rss_bytes_maximum"]))
        external = telemetry.get("external_time") or {}
        compliant = not telemetry["rss_breach_killed"] and external.get("real_seconds", policy["wall_seconds_maximum"] + 1) <= policy["wall_seconds_maximum"] and external.get("maximum_rss_bytes", policy["rss_bytes_maximum"] + 1) <= policy["rss_bytes_maximum"] and external.get("process_swaps", 1) == 0
        path = artifact_stage / "test.json"
        producer = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if not compliant:
            status = "STOP_P181_FIXED_BLOCK_DENOMINATOR_18DIGIT_TEST_RESOURCE"
        elif telemetry["return_code"] == 4 and producer is not None and producer.get("status") == "STOP_P181_18DIGIT_TEST_CORRECTION_OUTSIDE_COLUMN_SPACE":
            status = producer["status"]
        elif telemetry["return_code"] == 0 and producer is not None and producer.get("status") in {"PASS_P181_18DIGIT_FIXED_DENOMINATOR_EXACT_RATIONAL_SYSTEM_REPLAY", "PASS_P181_18DIGIT_FIXED_DENOMINATOR_MODEL_FALSIFICATION"} and len(producer.get("corrections", [])) == 2 and producer.get("terminal_integer_invariant_mismatches") == 0:
            status = producer["status"]
        else:
            status = "FAIL_P181_FIXED_BLOCK_DENOMINATOR_18DIGIT_TEST_INTEGRITY"
        terminal.update({"status": status, "producer_status": producer.get("status") if producer else None, "telemetry": telemetry, "claim_boundary": "A model-falsification PASS preserves only the exact finite p181^18 lift and rejects the frozen denominator models. Any exact rational-system replay still requires independent symbolic replay."})
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if status.startswith("PASS_") else 4 if status.endswith("OUTSIDE_COLUMN_SPACE") else 3 if status.endswith("_RESOURCE") else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_FIXED_BLOCK_DENOMINATOR_18DIGIT_TEST_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): base.tree_hashes(path) for path in (artifact_stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
