#!/usr/bin/env python3
"""Supervise and promote the amended solver-free p^6 recovery."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-six-digit-recovery-implementation-freeze-v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T005")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_SUPPORT18_SIX_DIGIT_RECOVERY_FREEZE_V2", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical support18 recovery output exists")
    stage = CAMPAIGN / "artifacts/staging" / f"p181-support18-six-digit-recovery-{arguments.run_id}"
    telemetry_stage = CAMPAIGN / "artifacts/staging" / f"p181-support18-six-digit-recovery-telemetry-{arguments.run_id}"
    terminal = {"schema": "hc4.third-colon-p181-support18-six-digit-recovery-terminal.v2", "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)}}
    try:
        policy = freeze["policy"]
        telemetry = base.supervise(
            ["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/recover_p181_support18_six_digit_extension_v2.py"), "--output-dir", str(stage)],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        receipt = json.loads((stage / "recovery.json").read_text(encoding="utf-8")) if (stage / "recovery.json").exists() else None
        external = telemetry.get("external_time") or {}
        passed = telemetry["return_code"] == 0 and not telemetry["rss_breach_killed"] and external.get("real_seconds", 10**9) <= policy["wall_seconds_maximum"] and external.get("maximum_rss_bytes", 10**12) <= policy["rss_bytes_maximum"] and external.get("process_swaps", 1) == 0 and receipt and receipt.get("status") == "PASS_P181_SUPPORT18_SIX_DIGIT_LIFT_RECOVERED_V2"
        status = "PASS_P181_SUPPORT18_SIX_DIGIT_LIFT_RECOVERED_V2" if passed else "FAIL_P181_SUPPORT18_SIX_DIGIT_RECOVERY_INTEGRITY_V2"
        terminal.update({"status": status, "telemetry": telemetry, "claim_boundary": "A PASS recovers only the finite p6 lift for 18 fixed source-kernel directions; it is not a rational or target-membership result."})
        os.rename(stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if passed else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_SUPPORT18_SIX_DIGIT_RECOVERY_INTEGRITY_V2")
        terminal["error"] = f"{type(error).__name__}: {error}"
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
