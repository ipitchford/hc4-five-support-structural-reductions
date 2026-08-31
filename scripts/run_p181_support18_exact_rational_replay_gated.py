#!/usr/bin/env python3
"""Supervise and promote the frozen next-18 exact rational replay."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-exact-rational-replay-implementation-freeze.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T003")
    arguments = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_SUPPORT18_EXACT_RATIONAL_REPLAY_FREEZE", "freeze absent")
    for relative, expected in freeze["bound_files"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "canonical support18 exact output exists")
    stage = CAMPAIGN / "artifacts/staging" / f"support18-exact-{arguments.run_id}"
    telemetry_stage = CAMPAIGN / "artifacts/staging" / f"support18-exact-telemetry-{arguments.run_id}"
    terminal = {"schema": "hc4.third-colon-p181-support18-exact-rational-terminal.v1", "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)}}
    try:
        policy = freeze["policy"]
        telemetry = base.supervise(
            ["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/reconstruct_p181_support18_exact_rational.py"), "--output-dir", str(stage)],
            telemetry_stage,
            int(policy["wall_seconds_maximum"]),
            int(policy["rss_bytes_maximum"]),
        )
        receipt = json.loads((stage / "replay.json").read_text(encoding="utf-8")) if (stage / "replay.json").exists() else None
        external = telemetry.get("external_time") or {}
        passed = (
            telemetry["return_code"] == 0
            and not telemetry["rss_breach_killed"]
            and external.get("real_seconds", 10**9) <= policy["wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", 10**12) <= policy["rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
            and receipt
            and receipt.get("status") == "PASS_P181_SUPPORT18_EXACT_RATIONAL_SYSTEM_REPLAY"
        )
        status = "PASS_P181_SUPPORT18_EXACT_RATIONAL_SYSTEM_REPLAY" if passed else "FAIL_P181_SUPPORT18_EXACT_RATIONAL_REPLAY_INTEGRITY"
        terminal.update({"status": status, "telemetry": telemetry, "claim_boundary": "A PASS proves 18 rational source syzygies and raises the rational quotient lower bound to 22; it is not target membership, colon, saturation, secant, nullcone, or HC4."})
        os.rename(stage, outputs["artifact"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"artifact": base.tree_hashes(outputs["artifact"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": status, "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0 if passed else 2
    except Exception as error:
        terminal.setdefault("status", "FAIL_P181_SUPPORT18_EXACT_RATIONAL_REPLAY_INTEGRITY")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): base.tree_hashes(path) for path in (stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
