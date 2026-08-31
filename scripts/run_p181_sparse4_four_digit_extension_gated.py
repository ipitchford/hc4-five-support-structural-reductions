#!/usr/bin/env python3
"""Supervise and promote the frozen sparse-four p^4 extension."""

from __future__ import annotations

import argparse, json, os
from pathlib import Path
import run_p181_target_blind_linbox_rank_gated as base

CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-sparse4-four-digit-extension-implementation-freeze.json"

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--run-id",default="20260831T003"); args=parser.parse_args()
    freeze=json.loads(FREEZE.read_text()); base.require(freeze.get("status")=="PASS_P181_SPARSE4_FOUR_DIGIT_EXTENSION_FREEZE","freeze absent")
    for rel,want in freeze["bound_files"].items(): base.require(base.file_hash(CAMPAIGN/rel)==want,f"bound drift: {rel}")
    outputs={k:CAMPAIGN/v for k,v in freeze["canonical_outputs"].items()}; base.require(not any(p.exists() for p in outputs.values()),"canonical output exists")
    stage=CAMPAIGN/"artifacts/staging"/f"p181-sparse4-four-digit-{args.run_id}"; telemetry_stage=CAMPAIGN/"artifacts/staging"/f"p181-sparse4-four-digit-telemetry-{args.run_id}"
    terminal={"schema":"hc4.third-colon-p181-sparse4-four-digit-extension-terminal.v1","implementation_freeze":{"path":str(FREEZE.relative_to(CAMPAIGN)),"sha256":base.file_hash(FREEZE)}}
    try:
        policy=freeze["policy"]; telemetry=base.supervise(["/Users/admin/.local/bin/sage","-python",str(CAMPAIGN/"scripts/extend_p181_sparse4_to_four_digits.py"),"--output-dir",str(stage)],telemetry_stage,int(policy["wall_seconds_maximum"]),int(policy["rss_bytes_maximum"]))
        receipt=json.loads((stage/"extension.json").read_text()) if (stage/"extension.json").exists() else None; producer_status=receipt.get("status") if receipt else None; ext=telemetry.get("external_time") or {}
        compliant=not telemetry["rss_breach_killed"] and ext.get("real_seconds",10**9)<=policy["wall_seconds_maximum"] and ext.get("maximum_rss_bytes",10**12)<=policy["rss_bytes_maximum"] and ext.get("process_swaps",1)==0
        allowed={"STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE","PASS_P181_SPARSE4_FOUR_DIGIT_LIFT","PASS_P181_SPARSE4_FOUR_DIGIT_EXACT_RATIONAL_REPLAY"}
        status=producer_status if compliant and producer_status in allowed and telemetry["return_code"] in (0,4) else "STOP_P181_SPARSE4_FOUR_DIGIT_RESOURCE" if not compliant else "FAIL_P181_SPARSE4_FOUR_DIGIT_INTEGRITY"
        terminal.update({"status":status,"extension_status":producer_status,"telemetry":telemetry,"claim_boundary":"A finite p4 PASS concerns four fixed residual columns only; no general QQ, colon, saturation, secant, nullcone, or HC4 conclusion follows."})
        os.rename(stage,outputs["artifact"]); outputs["telemetry"].parent.mkdir(parents=True,exist_ok=True); os.rename(telemetry_stage,outputs["telemetry"]); terminal["promoted"]={"artifact":base.tree_hashes(outputs["artifact"]),"telemetry":base.tree_hashes(outputs["telemetry"])}; outputs["terminal"].write_text(json.dumps(terminal,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"status":status,"terminal":str(outputs["terminal"]),"sha256":base.file_hash(outputs["terminal"])})); return 0 if status.startswith("PASS_") else 4 if status.startswith("STOP_") else 2
    except Exception as error:
        terminal.setdefault("status","FAIL_P181_SPARSE4_FOUR_DIGIT_INTEGRITY"); terminal["error"]=f"{type(error).__name__}: {error}"; terminal["retained_staging"]={str(p.relative_to(CAMPAIGN)):base.tree_hashes(p) for p in (stage,telemetry_stage) if p.exists()}; outputs["terminal"].parent.mkdir(parents=True,exist_ok=True); outputs["terminal"].write_text(json.dumps(terminal,indent=2,sort_keys=True)+"\n"); print(json.dumps({"status":terminal["status"],"error":terminal["error"]})); return 2

if __name__=="__main__": raise SystemExit(main())
