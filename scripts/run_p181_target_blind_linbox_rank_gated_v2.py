#!/usr/bin/env python3
"""V2 supervisor for the single licensed coefficient-support correction."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import run_p181_target_blind_linbox_rank_gated as base


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze-v2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="20260831T002")
    args = parser.parse_args()
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    base.require(freeze.get("status") == "PASS_P181_TARGET_BLIND_LINBOX_IMPLEMENTATION_FREEZE_V2", "v2 freeze absent")
    for relative, expected in freeze["implementation_sources"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"implementation drift: {relative}")
    for relative, expected in freeze["algebra_and_prior_sources"].items():
        base.require(base.file_hash(CAMPAIGN / relative) == expected, f"bound source drift: {relative}")
    outputs = {key: CAMPAIGN / value for key, value in freeze["canonical_outputs"].items()}
    base.require(not any(path.exists() for path in outputs.values()), "v2 canonical output already exists")
    staging_root = CAMPAIGN / "artifacts/staging"
    gauge_stage = staging_root / f"p181-target-blind-linbox-gauge-v2-{args.run_id}"
    benchmark_stage = staging_root / f"p181-target-blind-linbox-benchmark-v2-{args.run_id}"
    telemetry_stage = staging_root / f"p181-target-blind-linbox-telemetry-v2-{args.run_id}"
    terminal = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-terminal.v2",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": base.file_hash(FREEZE)},
        "v1_terminal_preserved": freeze["v1_terminal"],
    }
    try:
        subprocess.run(["/usr/bin/python3", str(CAMPAIGN / "scripts/extract_p181_target_blind_linbox_gauge.py"), "--output-dir", str(gauge_stage)], cwd=CAMPAIGN, check=True)
        policy = freeze["policy"]
        telemetry = base.supervise(
            ["/Users/admin/.local/bin/sage", "-python", str(CAMPAIGN / "scripts/benchmark_p181_target_blind_linbox_rank_v2.py"), "--gauge-dir", str(gauge_stage), "--output-dir", str(benchmark_stage), "--freeze", str(FREEZE)],
            telemetry_stage,
            int(policy["rank_wall_seconds_maximum"]),
            int(policy["rank_rss_bytes_maximum"]),
        )
        receipt_path = benchmark_stage / "benchmark.json"
        benchmark = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
        external = telemetry.get("external_time") or {}
        resources_pass = (
            telemetry["return_code"] == 0
            and not telemetry["rss_breach_killed"]
            and external.get("real_seconds", policy["rank_wall_seconds_maximum"] + 1) <= policy["rank_wall_seconds_maximum"]
            and external.get("maximum_rss_bytes", policy["rank_rss_bytes_maximum"] + 1) <= policy["rank_rss_bytes_maximum"]
            and external.get("process_swaps", 1) == 0
        )
        rank_pass = benchmark is not None and benchmark.get("status") == "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING"
        passed = resources_pass and rank_pass
        if benchmark is None:
            status = "FAIL_ACTUAL_COEFFICIENT_LINBOX_INTEGRITY_V2"
        elif benchmark.get("status") == "STOP_ACTUAL_COEFFICIENT_LINBOX_RANK_DEFICIT":
            status = "STOP_ACTUAL_COEFFICIENT_LINBOX_RANK_DEFICIT"
        elif not resources_pass:
            status = "STOP_ACTUAL_COEFFICIENT_LINBOX_RESOURCE_GATE"
        else:
            status = benchmark.get("status")
        terminal.update({
            "status": status,
            "telemetry": telemetry,
            "benchmark_status": benchmark.get("status") if benchmark else None,
            "completed_cases": benchmark.get("cases", []) if benchmark else json.loads((benchmark_stage / "checkpoint.json").read_text())["completed_cases"] if (benchmark_stage / "checkpoint.json").exists() else [],
            "declarations": {"target_blind": True, "no_rhs": True, "no_augmented_rank": True, "no_solve": True, "no_digit": True},
            "claim_boundary": "A PASS is exact rank/scaling evidence for the actual coefficient map only; no target-membership or HC4 conclusion follows.",
        })
        if not passed:
            raise RuntimeError(f"registered v2 terminal: {status}")
        os.rename(gauge_stage, outputs["gauge"])
        os.rename(benchmark_stage, outputs["benchmark"])
        outputs["telemetry"].parent.mkdir(parents=True, exist_ok=True)
        os.rename(telemetry_stage, outputs["telemetry"])
        terminal["promoted"] = {"gauge": base.tree_hashes(outputs["gauge"]), "benchmark": base.tree_hashes(outputs["benchmark"]), "telemetry": base.tree_hashes(outputs["telemetry"])}
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "terminal": str(outputs["terminal"]), "sha256": base.file_hash(outputs["terminal"])}))
        return 0
    except Exception as error:
        terminal.setdefault("status", "FAIL_ACTUAL_COEFFICIENT_LINBOX_INTEGRITY_V2")
        terminal["error"] = f"{type(error).__name__}: {error}"
        terminal["retained_staging"] = {str(path.relative_to(CAMPAIGN)): base.tree_hashes(path) for path in (gauge_stage, benchmark_stage, telemetry_stage) if path.exists()}
        outputs["terminal"].parent.mkdir(parents=True, exist_ok=True)
        outputs["terminal"].write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": terminal["status"], "error": terminal["error"], "terminal": str(outputs["terminal"])}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
