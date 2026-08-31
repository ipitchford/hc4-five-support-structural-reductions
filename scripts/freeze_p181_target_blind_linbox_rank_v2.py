#!/usr/bin/env python3
"""Freeze v2 after the sole licensed row-support correction."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze-v2.json"
V1_FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze.json"
V1_FREEZE_SHA256 = "a87bb8f98c3c6b89ab01df2cc1f5757ddc04fa363dfee5482932f817fc1f195b"
V1_TERMINAL = "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal.json"
V1_TERMINAL_SHA256 = "71de230e2166a8eaeff9e125fd2ef6d40527b0f5334fe19c39f4da288427f6c1"
AMENDMENT = "research/THIRD_COLON_P181_TARGET_BLIND_LINBOX_RANK_PREREGISTRATION_AMENDMENT_01.md"
AMENDMENT_SHA256 = "051b1357c413dea6c05aad525f1fa91ffbf673890513638fd7662b1b8216be6e"
V2_SOURCES = (
    "scripts/benchmark_p181_target_blind_linbox_rank_v2.py",
    "scripts/run_p181_target_blind_linbox_rank_gated_v2.py",
    "scripts/freeze_p181_target_blind_linbox_rank_v2.py",
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if file_hash(V1_FREEZE) != V1_FREEZE_SHA256 or file_hash(CAMPAIGN / V1_TERMINAL) != V1_TERMINAL_SHA256:
        raise ValueError("v1 terminal chain drift")
    if file_hash(CAMPAIGN / AMENDMENT) != AMENDMENT_SHA256:
        raise ValueError("v2 amendment drift")
    v1 = json.loads(V1_FREEZE.read_text(encoding="utf-8"))
    for relative, expected in v1["implementation_sources"].items():
        if file_hash(CAMPAIGN / relative) != expected:
            raise ValueError(f"v1 implementation source drift: {relative}")
    for relative, expected in v1["algebra_and_prior_sources"].items():
        if file_hash(CAMPAIGN / relative) != expected:
            raise ValueError(f"algebra/prior source drift: {relative}")
    implementation = dict(v1["implementation_sources"])
    implementation.update({relative: file_hash(CAMPAIGN / relative) for relative in V2_SOURCES})
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-implementation-freeze.v2",
        "status": "PASS_P181_TARGET_BLIND_LINBOX_IMPLEMENTATION_FREEZE_V2",
        "preregistration": v1["preregistration"],
        "amendment": {"path": AMENDMENT, "sha256": AMENDMENT_SHA256},
        "v1_implementation_freeze": {"path": str(V1_FREEZE.relative_to(CAMPAIGN)), "sha256": V1_FREEZE_SHA256},
        "v1_terminal": {"path": V1_TERMINAL, "sha256": V1_TERMINAL_SHA256, "classification": "FAIL_PRE_RANK_ROW_DOMAIN_INTEGRITY_V1"},
        "implementation_sources": implementation,
        "algebra_and_prior_sources": v1["algebra_and_prior_sources"],
        "toolchain": v1["toolchain"],
        "policy": v1["policy"],
        "sole_change": "sorted nonempty coefficient-support rows replace the full ambient character block",
        "canonical_outputs": {
            "gauge": "artifacts/third-colon-p181-target-blind-linbox-gauge-v2",
            "benchmark": "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2",
            "telemetry": "receipts/telemetry/third-colon-p181-target-blind-linbox-v2",
            "terminal": "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal-v2.json",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("xb") as handle:
        handle.write((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
