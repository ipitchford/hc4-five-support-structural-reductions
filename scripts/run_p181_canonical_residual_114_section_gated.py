#!/usr/bin/env python3
"""Supervise and promote the frozen canonical residual-114 modular section."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-canonical-residual-114-section-implementation-freeze.json"
PASS = "PASS_P181_CANONICAL_RESIDUAL_114_MODULAR_KERNEL_SECTION"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T001")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_CANONICAL_RESIDUAL_114_SECTION_IMPLEMENTATION_FREEZE", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound file drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical residual-114 section output exists")
    staging = CAMPAIGN / "artifacts/staging"
    artifact_stage = staging / f"p181-canonical-residual-114-section-{arguments.run_id}"
    telemetry_stage = staging / f"p181-canonical-residual-114-section-telemetry-{arguments.run_id}"
    policy = freeze["policy"]
    terminal = {"schema": "hc4.third-colon-p181-canonical-residual-114-section-terminal.v1", "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)}}
    try:
        telemetry = base.supervise(
            ["/usr/bin/python3", str(CAMPAIGN / "scripts/produce_p181_canonical_residual_114_section.py"), "--output-dir", str(artifact_stage)],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        external = telemetry.get("external_time") or {}
        compliant = not telemetry["rss_breach_killed"] and external.get("real_seconds", policy["wall_seconds_maximum"] + 1) <= policy["wall_seconds_maximum"] and external.get("maximum_rss_bytes", policy["rss_bytes_maximum"] + 1) <= policy["rss_bytes_maximum"] and external.get("process_swaps", 1) == 0
        producer_path = artifact_stage / "producer.json"
        producer = json.loads(producer_path.read_text(encoding="utf-8")) if producer_path.exists() else None
        section_path = artifact_stage / "section.json"
        section = json.loads(section_path.read_text(encoding="utf-8")) if section_path.exists() else None
        if not compliant:
            status = "STOP_P181_CANONICAL_RESIDUAL_114_SECTION_RESOURCE"
        elif telemetry["return_code"] == 4 and producer is not None and str(producer.get("status", "")).startswith("STOP_"):
            status = producer["status"]
        elif telemetry["return_code"] == 0 and producer is not None and section is not None and producer.get("status") == PASS and section.get("status") == PASS and section.get("coefficient_replay", {}).get("mismatch_count") == 0 and section.get("quotient_replay", {}).get("identity_mismatch_count") == 0 and section.get("kernel_completion", {}).get("combined_free_restriction_rank") == 2167:
            status = PASS
        else:
            status = "FAIL_P181_CANONICAL_RESIDUAL_114_SECTION_INTEGRITY"
        terminal.update({"status": status, "producer_status": producer.get("status") if producer else None, "telemetry": telemetry, "claim_boundary": "A PASS proves only the canonical residual-114 section and full encoded kernel decomposition over GF(181). It does not lift residual syzygies to QQ, prove QQ target membership, a colon, saturation, secant closure, nullcone containment, or HC4."})
        os.rename(artifact_stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if status == PASS else 4 if status.startswith("STOP_") else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_CANONICAL_RESIDUAL_114_SECTION_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): base.tree_hashes(path) for path in (artifact_stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
