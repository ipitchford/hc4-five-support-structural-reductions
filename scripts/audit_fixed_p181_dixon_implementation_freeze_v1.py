#!/usr/bin/env python3
"""Fail-closed audit of the accidentally installed v1 implementation freeze."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1-failed-audit.json"
EXPECTED_FREEZE_SHA256 = "8b313ec2354c7afe21a041260a2dbc6bc6b167855a94b14fa21031c9538d1568"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if digest(FREEZE) != EXPECTED_FREEZE_SHA256:
        raise ValueError("v1 implementation freeze drift")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    changed_sources = {
        relative: {"expected": expected, "observed": digest(CAMPAIGN / relative)}
        for relative, expected in freeze["implementation_sources"].items()
        if digest(CAMPAIGN / relative) != expected
    }
    if changed_sources:
        raise ValueError(f"a v1 source changed before the failure audit: {changed_sources}")
    wrapper_text = (CAMPAIGN / "scripts/run_fixed_p181_dixon_8digit_gated.py").read_text(encoding="utf-8")
    required_runtime_keys = ["phase1_telemetry", "phase2_telemetry"]
    absent = [key for key in required_runtime_keys if key not in freeze["canonical_paths"]]
    referenced = [key for key in required_runtime_keys if f'paths["{key}"]' in wrapper_text]
    if absent != required_runtime_keys or referenced != required_runtime_keys:
        raise ValueError("the expected frozen interface defect was not reproduced")
    prospective = [
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v1",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v1.json",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v1",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v1",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v1.json",
    ]
    existing = [relative for relative in prospective if (CAMPAIGN / relative).exists()]
    if existing:
        raise ValueError(f"prospective computation ran before audit: {existing}")
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1-failure-audit.v1",
        "status": "FAIL_PREEXECUTION_IMPLEMENTATION_INTERFACE_V1",
        "implementation_freeze": {"path": str(FREEZE.relative_to(CAMPAIGN)), "sha256": EXPECTED_FREEZE_SHA256},
        "frozen_source_hashes_still_match": True,
        "defect": {
            "missing_canonical_path_keys": absent,
            "wrapper_references_missing_keys": referenced,
            "first_failure_if_executed": "KeyError before preprocessing spawn",
        },
        "prospective_output_absence": {"checked": prospective, "existing": existing},
        "declarations": {
            "no_preprocessing_launched": True,
            "no_factorization_launched": True,
            "no_arithmetic_modulo_181_squared": True,
            "v1_freeze_inadmissible_for_execution": True,
        },
        "claim_boundary": "This is a pre-execution implementation-interface failure. It contains no algebraic or p-adic evidence and licenses no computation under v1.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
